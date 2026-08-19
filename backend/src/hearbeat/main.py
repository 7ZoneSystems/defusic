"""FastAPI backend for hearbeat analysis."""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from hearbeat.config import API_HOST, API_PORT, MAX_UPLOAD_MB, OUTPUT_DIR
from hearbeat.models import AnalysisJob, AnalysisResult
from hearbeat.pipeline import analyze_file

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hearbeat API",
    description="Stage 1: Bass + Beat Musical Event Extraction Engine",
    version="0.1.0",
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

ALLOWED_EXTENSIONS = {
    ".mp4", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".webm",
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a media file and run analysis."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    job_id = uuid.uuid4().hex[:12]
    job = AnalysisJob(job_id=job_id, filename=file.filename, status="processing")
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
        )
        job.status = "completed"
        job.result = result

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
    """Download a click-track WAV for the analysis.

    Args:
        multi: If true, includes bass+beat and bass offbeat layers.
    """
    from hearbeat.beat_player import generate_click_train, generate_multi_track, save_wav
    from hearbeat.models import EventType

    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    result = job.result
    stem = Path(job.filename).stem
    out_dir = OUTPUT_DIR

    if multi:
        bass_beat_times = [e.time for e in result.events if e.type == EventType.BASS_BEAT]
        bass_offbeat_times = [e.time for e in result.events if e.type == EventType.BASS_OFFBEAT]
        audio, sr = generate_multi_track(
            beat_timestamps=result.rhythm.beats,
            bass_beat_timestamps=bass_beat_times,
            bass_offbeat_timestamps=bass_offbeat_times,
        )
        wav_name = f"{stem}_clicks_multi.wav"
    else:
        audio, sr = generate_click_train(result.rhythm.beats)
        wav_name = f"{stem}_clicks.wav"

    wav_path = out_dir / wav_name
    save_wav(audio, wav_path, sr)
    return FileResponse(wav_path, media_type="audio/wav", filename=wav_name)


def run_server() -> None:
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    run_server()
