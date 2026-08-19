"""FastAPI backend for hearbeat analysis."""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from hearbeat.config import API_HOST, API_PORT, MAX_UPLOAD_MB, OUTPUT_DIR
from hearbeat.models import AnalysisJob, AnalysisResult
from hearbeat.pipeline import analyze_file

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hearbeat API",
    description="Stage 2: Music Enjoyment + Drumming Analysis Engine",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store
_jobs: dict[str, AnalysisJob] = {}

# Store uploaded files for original audio playback
_upload_files: dict[str, Path] = {}

ALLOWED_EXTENSIONS = {
    ".mp4", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".webm",
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    mode: str = Query("music", pattern="^(music|drumming)$"),
) -> JSONResponse:
    """Upload a media file and run analysis.

    Args:
        mode: Analysis mode - 'music' (Stage 1) or 'drumming' (Stage 2).
    """
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    job_id = uuid.uuid4().hex[:12]
    job = AnalysisJob(job_id=job_id, filename=file.filename, status="processing", mode=mode)
    _jobs[job_id] = job

    # Save upload to temp file
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / file.filename

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            size_mb = len(content) / (1024 * 1024)
            if size_mb > MAX_UPLOAD_MB:
                raise HTTPException(413, f"File too large: {size_mb:.1f}MB (max: {MAX_UPLOAD_MB}MB)")
            f.write(content)

        result = analyze_file(
            input_path=tmp_path,
            output_dir=OUTPUT_DIR,
            output_json=True,
            mode=mode,
        )
        job.status = "completed"
        job.result = result

        # Keep original file for audio serving
        original_path = OUTPUT_DIR / file.filename
        shutil.copy2(tmp_path, original_path)
        _upload_files[job_id] = original_path

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        logger.error("Analysis failed for %s: %s", file.filename, e)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse(content=job.model_dump(mode="json"))


@app.get("/analysis/{job_id}")
def get_analysis(job_id: str) -> JSONResponse:
    """Retrieve a completed analysis by job ID."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return JSONResponse(content=job.model_dump(mode="json"))


@app.get("/analysis/{job_id}/json")
def get_analysis_json(job_id: str) -> FileResponse:
    """Download the raw JSON file for an analysis."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    stem = Path(job.filename).stem
    json_path = OUTPUT_DIR / f"{stem}.json"
    if not json_path.exists():
        raise HTTPException(404, "JSON file not found on disk")
    return FileResponse(json_path, media_type="application/json")


@app.get("/analysis/{job_id}/audio")
def get_original_audio(job_id: str) -> FileResponse:
    """Serve the original uploaded audio for playback."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")

    audio_path = _upload_files.get(job_id)
    if not audio_path or not audio_path.exists():
        raise HTTPException(404, "Original audio not available")

    ext = Path(job.filename).suffix.lower()
    media_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(audio_path, media_type=media_type, filename=job.filename)


@app.get("/analysis/{job_id}/diagnostic")
def get_diagnostic_audio(
    job_id: str,
    layers: str = Query("all", description="Comma-separated layers to include"),
) -> FileResponse:
    """Generate and serve diagnostic audio for an analysis.

    Args:
        layers: Comma-separated event types to include. 'all' for everything.
    """
    from hearbeat.diagnostic_player import generate_drum_diagnostic, generate_music_diagnostic, save_wav

    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    result = job.result
    stem = Path(job.filename).stem

    active_layers = None
    if layers != "all":
        active_layers = set(layers.split(","))

    if result.mode == "drumming":
        events_for_audio = [
            {"time": e.time, "type": e.type}
            for e in result.events
        ]
        audio, sr = generate_drum_diagnostic(
            events_for_audio, active_layers=active_layers
        )
    else:
        audio, sr = generate_music_diagnostic(
            result.events, active_layers=active_layers
        )

    layer_suffix = layers.replace(",", "+") if layers != "all" else "all"
    wav_name = f"{stem}_diagnostic_{layer_suffix}.wav"
    wav_path = OUTPUT_DIR / wav_name
    save_wav(audio, wav_path, sr)

    return FileResponse(wav_path, media_type="audio/wav", filename=wav_name)


@app.get("/analysis/{job_id}/waveform")
def get_waveform_data(
    job_id: str,
    resolution: int = Query(2000, ge=100, le=10000),
) -> JSONResponse:
    """Return downsampled waveform data for display.

    Args:
        resolution: Number of amplitude points to return.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")

    audio_path = _upload_files.get(job_id)
    if not audio_path or not audio_path.exists():
        raise HTTPException(404, "Original audio not available")

    try:
        import soundfile as sf
        audio, sr = sf.read(str(audio_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Downsample to resolution points
        n = len(audio)
        if n <= resolution:
            waveform = audio.tolist()
        else:
            chunk_size = n // resolution
            waveform = []
            for i in range(resolution):
                chunk = audio[i * chunk_size : (i + 1) * chunk_size]
                waveform.append(float(np.max(np.abs(chunk))))

        return JSONResponse(content={
            "waveform": waveform,
            "duration": len(audio) / sr,
            "sample_rate": sr,
            "resolution": len(waveform),
        })
    except Exception as e:
        raise HTTPException(500, f"Failed to generate waveform: {e}")


@app.get("/visualize/{job_id}", response_class=HTMLResponse)
def visualize(job_id: str) -> str:
    """Serve the debug visualization HTML for an analysis."""
    from hearbeat.visualizer import generate_html

    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    return generate_html(job.result, job.filename)


@app.get("/analysis/{job_id}/click-track")
def get_click_track(job_id: str, multi: bool = False) -> FileResponse:
    """Download a click-track WAV for the analysis."""
    from hearbeat.diagnostic_player import generate_music_diagnostic, save_wav

    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    result = job.result
    stem = Path(job.filename).stem

    if multi:
        audio, sr = generate_music_diagnostic(result.events, active_layers={"beat", "bass_beat", "bass_offbeat"})
        wav_name = f"{stem}_clicks_multi.wav"
    else:
        audio, sr = generate_music_diagnostic(result.events, active_layers={"beat"})
        wav_name = f"{stem}_clicks.wav"

    wav_path = OUTPUT_DIR / wav_name
    save_wav(audio, wav_path, sr)
    return FileResponse(wav_path, media_type="audio/wav", filename=wav_name)


def run_server() -> None:
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    run_server()
