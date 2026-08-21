"""FastAPI backend for hearbeat analysis."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import httpx
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from hearbeat.config import API_HOST, API_PORT, MAX_UPLOAD_MB, OUTPUT_DIR
from hearbeat.haptic_config import HapticConfig, get_preset, list_presets
from hearbeat.haptic_mapper import HapticMapper
from hearbeat.models import (
    AdaptiveDebugEvent,
    AnalysisJob,
    AnalysisResult,
    HapticConfigUpdate,
    HapticTimelineModel,
    LoudnessCurvePoint,
    LoudnessData,
)
from hearbeat.pipeline import analyze_file
from hearbeat import cohesivity as coh

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hearbeat API",
    description="Stage 3: Music Enjoyment + Drumming + Haptic Translation Engine",
    version="0.3.0",
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
    return {"status": "ok", "version": "0.3.0"}


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


@app.get("/analysis/{job_id}/filtered")
def get_filtered_audio(
    job_id: str,
    band: str = Query("bass", description="Filter band: bass, subbass, lowmid, kick"),
) -> FileResponse:
    """Export filtered WAV for diagnostic listening.

    Development-only endpoint for debugging filter bank analysis.
    Bands: bass, subbass, lowmid, kick.
    """
    from hearbeat.filter_bank import FilterBank, DEFAULT_BANDS
    from hearbeat.config import FILTER_ORDER, KICK_LOW_HZ, KICK_HIGH_HZ
    import soundfile as sf

    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    audio_path = _upload_files.get(job_id)
    if not audio_path or not audio_path.exists():
        raise HTTPException(404, "Original audio not available")

    audio, sr = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Build filter bank with requested band
    band_ranges = {
        "bass": (60.0, 150.0),
        "subbass": (20.0, 60.0),
        "lowmid": (150.0, 250.0),
        "kick": (KICK_LOW_HZ, KICK_HIGH_HZ),
    }
    if band not in band_ranges:
        raise HTTPException(400, f"Unknown band: {band}. Use: {list(band_ranges.keys())}")

    fb = FilterBank(sr=sr, bands={band: band_ranges[band]}, order=FILTER_ORDER)
    filtered = fb.filter_band(audio, band, causal=False)

    stem = Path(job.filename).stem
    wav_name = f"{stem}_{band}_filtered.wav"
    wav_path = OUTPUT_DIR / wav_name
    sf.write(str(wav_path), filtered, sr, subtype="FLOAT")

    return FileResponse(wav_path, media_type="audio/wav", filename=wav_name)


# --- Haptic endpoints ---


@app.get("/presets")
def get_presets() -> JSONResponse:
    """List available haptic presets."""
    return JSONResponse(content={"presets": list_presets()})


@app.get("/analysis/{job_id}/loudness")
def get_loudness_profile(job_id: str) -> JSONResponse:
    """Get the loudness profile for a completed analysis.

    Computes ITU-R BS.1770-style loudness if not already cached.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    # Check if loudness was already computed and cached in metadata
    cached = job.result.metadata.get("loudness")
    if cached:
        return JSONResponse(content=cached)

    # Compute from original audio
    audio_path = _upload_files.get(job_id)
    if not audio_path or not audio_path.exists():
        raise HTTPException(404, "Original audio not available for loudness analysis")

    import soundfile as sf
    from hearbeat.adaptive_haptics import measure_loudness, AdaptiveConfig

    audio, sr = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    profile = measure_loudness(audio, sr, AdaptiveConfig())

    loudness_data = LoudnessData(
        integrated_lufs=round(profile.integrated_lufs, 1),
        true_peak_dbtp=round(profile.true_peak_dbtp, 1),
        short_term_p10=round(profile.short_term_p10, 1),
        short_term_p50=round(profile.short_term_p50, 1),
        short_term_p90=round(profile.short_term_p90, 1),
        momentary_max=round(profile.momentary_max, 1),
        curve=[
            LoudnessCurvePoint(time=p["time"], short_term_lufs=p["short_term_lufs"])
            for p in profile.short_term_curve
        ],
    )

    result_dict = loudness_data.model_dump()

    # Cache in metadata
    job.result.metadata["loudness"] = result_dict

    return JSONResponse(content=result_dict)


@app.post("/analysis/{job_id}/haptic")
def generate_haptic_timeline(
    job_id: str,
    config_update: HapticConfigUpdate | None = None,
) -> JSONResponse:
    """Generate a haptic timeline from an analysis result.

    Accepts optional haptic configuration overrides.
    Supports adaptive loudness scaling when enabled.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(400, "Analysis not completed yet")

    result = job.result

    # Build config from preset + overrides
    if config_update and config_update.preset:
        haptic_config = get_preset(config_update.preset)
        preset_name = config_update.preset
    else:
        haptic_config = HapticConfig()
        preset_name = "drummer_default"

    # Apply overrides
    if config_update:
        _apply_config_overrides(haptic_config, config_update)

    # Determine adaptive settings
    adaptive_enabled = haptic_config.adaptive_enabled
    adaptive_gain_strength = haptic_config.adaptive_gain_strength
    if config_update:
        if config_update.adaptive_enabled is not None:
            adaptive_enabled = config_update.adaptive_enabled
        if config_update.adaptive_gain_strength is not None:
            adaptive_gain_strength = config_update.adaptive_gain_strength

    # Compute or retrieve loudness profile
    loudness_profile = None
    if adaptive_enabled:
        loudness_profile = _get_or_compute_loudness(job_id, result)

    mapper = HapticMapper(config=haptic_config, preset_name=preset_name)
    timeline, adaptive_debug = mapper.map_events(
        result.events,
        result.source.duration_seconds,
        loudness_profile=loudness_profile,
        adaptive_enabled=adaptive_enabled,
        adaptive_gain_strength=adaptive_gain_strength,
    )

    response = timeline.to_dict()
    if adaptive_debug:
        response["adaptive_debug"] = adaptive_debug
    if loudness_profile:
        from hearbeat.adaptive_haptics import LoudnessProfile as LP
        response["loudness"] = {
            "integrated_lufs": round(loudness_profile.integrated_lufs, 1),
            "true_peak_dbtp": round(loudness_profile.true_peak_dbtp, 1),
            "short_term_p10": round(loudness_profile.short_term_p10, 1),
            "short_term_p50": round(loudness_profile.short_term_p50, 1),
            "short_term_p90": round(loudness_profile.short_term_p90, 1),
        }

    return JSONResponse(content=response)


def _get_or_compute_loudness(job_id: str, result: AnalysisResult) -> object:
    """Get cached loudness profile or compute from audio."""
    # Check metadata cache first
    cached = result.metadata.get("loudness")
    if cached:
        from hearbeat.adaptive_haptics import LoudnessProfile
        profile = LoudnessProfile(
            integrated_lufs=cached.get("integrated_lufs", -70.0),
            true_peak_dbtp=cached.get("true_peak_dbtp", -70.0),
            short_term_p10=cached.get("short_term_p10", -70.0),
            short_term_p50=cached.get("short_term_p50", -70.0),
            short_term_p90=cached.get("short_term_p90", -70.0),
            momentary_max=cached.get("momentary_max", -70.0),
            short_term_curve=[
                {"time": p["time"], "short_term_lufs": p["short_term_lufs"]}
                for p in cached.get("curve", [])
            ],
        )
        return profile

    # Compute from audio
    audio_path = _upload_files.get(job_id)
    if not audio_path or not audio_path.exists():
        return None

    import soundfile as sf
    from hearbeat.adaptive_haptics import measure_loudness, AdaptiveConfig

    audio, sr = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    profile = measure_loudness(audio, sr, AdaptiveConfig())

    # Cache in metadata
    result.metadata["loudness"] = {
        "integrated_lufs": round(profile.integrated_lufs, 1),
        "true_peak_dbtp": round(profile.true_peak_dbtp, 1),
        "short_term_p10": round(profile.short_term_p10, 1),
        "short_term_p50": round(profile.short_term_p50, 1),
        "short_term_p90": round(profile.short_term_p90, 1),
        "momentary_max": round(profile.momentary_max, 1),
        "curve": profile.short_term_curve,
    }

    return profile


def _apply_config_overrides(config: HapticConfig, update: HapticConfigUpdate) -> None:
    """Apply user overrides to haptic config."""
    if update.beat_intensity is not None:
        config.beat.intensity = update.beat_intensity
    if update.beat_duration_ms is not None:
        config.beat.duration_ms = update.beat_duration_ms
    if update.hihat_intensity is not None:
        config.hihat.intensity = update.hihat_intensity
    if update.hihat_duration_ms is not None:
        config.hihat.duration_ms = update.hihat_duration_ms
    if update.kick_intensity is not None:
        config.kick.intensity = update.kick_intensity
    if update.kick_duration_ms is not None:
        config.kick.duration_ms = update.kick_duration_ms
    if update.snare_intensity is not None:
        config.snare.intensity = update.snare_intensity
    if update.snare_duration_ms is not None:
        config.snare.duration_ms = update.snare_duration_ms
    if update.bass_intensity is not None:
        config.bass.intensity = update.bass_intensity
    if update.bass_duration_ms is not None:
        config.bass.duration_ms = update.bass_duration_ms
    if update.subbass_intensity is not None:
        config.subbass.intensity = update.subbass_intensity
    if update.subbass_duration_ms is not None:
        config.subbass.duration_ms = update.subbass_duration_ms
    if update.anticipation_enabled is not None:
        config.anticipation.enabled = update.anticipation_enabled
    if update.minimum_gap_ms is not None:
        config.minimum_gap_ms = update.minimum_gap_ms
    if update.master_intensity is not None:
        config.master_intensity = update.master_intensity
    if update.adaptive_enabled is not None:
        config.adaptive_enabled = update.adaptive_enabled
    if update.adaptive_gain_strength is not None:
        config.adaptive_gain_strength = update.adaptive_gain_strength


# --- Auth endpoints ---


@app.get("/auth/login")
async def auth_login(return_to: str = "/") -> RedirectResponse:
    """Redirect to Cohesivity Google login."""
    login_url = coh.get_login_url(return_to=return_to)
    return RedirectResponse(url=login_url)


@app.get("/auth/callback")
async def auth_callback(
    access_token: str | None = Query(None),
    refresh_token: str | None = Query(None),
    return_to: str = Query("/"),
    error: str | None = Query(None),
) -> RedirectResponse:
    """Handle OAuth callback from Cohesivity.

    Tokens are set as HttpOnly cookies server-side and never exposed
    in the redirect URL to the browser.
    """
    frontend_url = os.getenv("FRONTEND_URL", "")

    if error or not access_token:
        error_path = f"/?auth_error={error or 'no_token'}"
        target = f"{frontend_url}{error_path}" if frontend_url else error_path
        return RedirectResponse(url=target)

    redirect_path = return_to if return_to.startswith("/") else "/"
    target = f"{frontend_url}{redirect_path}" if frontend_url else redirect_path
    resp = RedirectResponse(url=target)

    resp.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
    )
    if refresh_token:
        resp.set_cookie(
            "refresh_token", refresh_token,
            httponly=True, secure=True, samesite="lax", path="/", max_age=30 * 86400,
        )

    return resp


@app.get("/auth/me")
async def auth_me(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Get current authenticated user. Returns 401 if not logged in."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    resp = JSONResponse(content={"user": user})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
        resp.set_cookie(
            "refresh_token", new_tokens["refresh_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=30 * 86400,
        )
    return resp


@app.post("/auth/logout")
async def auth_logout(
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Log out: revoke refresh token and clear cookies."""
    if refresh_token:
        try:
            tid = coh.get_tenant_id()
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{coh.COHESIVITY_BASE}/edge/auth/{tid}/logout",
                    json={"refresh_token": refresh_token},
                    headers={"User-Agent": "hearbeat-app/1.0"},
                )
        except Exception:
            pass

    resp = JSONResponse(content={"status": "ok"})
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/")
    return resp


# --- Google Drive endpoints ---

from hearbeat import drive as gdrive


@app.get("/drive/status")
async def drive_status(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Check if Google Drive is connected for the authenticated user."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    connected = bool(db_user.get("drive_songs_folder_id"))
    return JSONResponse({
        "connected": connected,
        "folder_id": db_user.get("drive_folder_id"),
        "songs_folder_id": db_user.get("drive_songs_folder_id"),
    })


@app.post("/drive/exchange")
async def drive_exchange(
    code: str,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Exchange Google OAuth code for Drive tokens and set up folder structure."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    # Exchange code for tokens
    try:
        token_data = await gdrive.exchange_code(code)
    except Exception as e:
        logger.error("Drive token exchange failed: %s", e)
        raise HTTPException(400, "Invalid authorization code")

    drive_access = token_data["access_token"]
    drive_refresh = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    # Store tokens
    await gdrive._store_tokens(db_user["id"], drive_access, drive_refresh, expires_in)

    # Ensure folder structure
    try:
        hb_id, songs_id = await gdrive.ensure_folder_structure(drive_access)
        await gdrive.save_folder_ids(db_user["id"], hb_id, songs_id)
    except Exception as e:
        logger.error("Drive folder setup failed: %s", e)
        raise HTTPException(500, "Failed to set up Drive folders")

    return JSONResponse({
        "status": "connected",
        "folder_id": hb_id,
        "songs_folder_id": songs_id,
    })


@app.post("/drive/disconnect")
async def drive_disconnect(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Disconnect Google Drive without deleting files."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    await gdrive.disconnect_drive(db_user["id"])
    return JSONResponse({"status": "disconnected"})


@app.post("/drive/upload")
async def drive_upload(
    file: UploadFile = File(...),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Upload an audio file to the user's Google Drive HearBeat/Songs/ folder."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    drive_token = await gdrive._get_valid_token(db_user)
    if not drive_token:
        raise HTTPException(400, "Google Drive not connected")

    songs_folder_id = db_user.get("drive_songs_folder_id")
    if not songs_folder_id:
        raise HTTPException(400, "Drive folder structure not set up")

    file_bytes = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        file_id = await gdrive.upload_file(
            drive_token, songs_folder_id, file.filename or "audio", mime_type, file_bytes
        )
    except Exception as e:
        logger.error("Drive upload failed: %s", e)
        raise HTTPException(500, "Failed to upload to Google Drive")

    return JSONResponse({"drive_file_id": file_id})


@app.get("/drive/download/{file_id:path}")
async def drive_download(
    file_id: str,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> Response:
    """Download a file from the user's Google Drive."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    drive_token = await gdrive._get_valid_token(db_user)
    if not drive_token:
        raise HTTPException(400, "Google Drive not connected")

    songs_folder_id = db_user.get("drive_songs_folder_id")
    if not songs_folder_id:
        raise HTTPException(400, "Drive folder structure not set up")

    # Verify the file belongs to the user's HearBeat/Songs folder
    if not await gdrive.verify_file_in_folder(drive_token, file_id, songs_folder_id):
        raise HTTPException(403, "File is not in your HearBeat/Songs folder")

    try:
        file_bytes = await gdrive.download_file(drive_token, file_id)
        meta = await gdrive.get_file_metadata(drive_token, file_id)
        filename = meta["name"] if meta else "download"
        mime = meta.get("mimeType", "application/octet-stream") if meta else "application/octet-stream"
    except Exception as e:
        logger.error("Drive download failed: %s", e)
        raise HTTPException(500, "Failed to download from Google Drive")

    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/drive/file/{file_id:path}")
async def drive_delete_file(
    file_id: str,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Permanently delete a file from the user's Google Drive."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    drive_token = await gdrive._get_valid_token(db_user)
    if not drive_token:
        raise HTTPException(400, "Google Drive not connected")

    songs_folder_id = db_user.get("drive_songs_folder_id")
    if not songs_folder_id:
        raise HTTPException(400, "Drive folder structure not set up")

    # Verify the file belongs to the user's HearBeat/Songs folder
    if not await gdrive.verify_file_in_folder(drive_token, file_id, songs_folder_id):
        raise HTTPException(403, "File is not in your HearBeat/Songs folder")

    success = await gdrive.delete_file(drive_token, file_id)
    if not success:
        raise HTTPException(500, "Failed to delete file from Drive")

    return JSONResponse({"status": "deleted", "drive_file_id": file_id})


# --- Library endpoints ---


@app.get("/library/songs")
async def list_songs(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """List all songs for the authenticated user."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        return JSONResponse(content={"songs": []})

    rows = await coh.db_query(
        """
        SELECT s.id, s.original_name, s.file_hash, s.file_size, s.duration_seconds,
               s.analysis_mode, s.drive_file_id, s.created_at, s.last_played,
               a.id as analysis_id, a.created_at as analysis_created_at
        FROM user_songs s
        LEFT JOIN song_analysis a ON a.song_id = s.id
        WHERE s.user_id = $1
        ORDER BY s.last_played DESC NULLS LAST, s.created_at DESC
        """,
        [db_user["id"]],
    )

    songs = []
    for row in rows:
        songs.append({
            "id": row["id"],
            "filename": row["original_name"],
            "file_hash": row["file_hash"],
            "file_size": row["file_size"],
            "duration_seconds": row["duration_seconds"],
            "analysis_mode": row["analysis_mode"],
            "drive_file_id": row.get("drive_file_id"),
            "has_analysis": row["analysis_id"] is not None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "last_played": row["last_played"].isoformat() if row.get("last_played") else None,
        })

    resp = JSONResponse(content={"songs": songs})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.get("/drive/songs")
async def list_drive_songs(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """List audio files in the user's Google Drive HearBeat/Songs/ folder."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    drive_token = await gdrive._get_valid_token(db_user)
    if not drive_token:
        raise HTTPException(400, "Google Drive not connected")

    songs_folder_id = db_user.get("drive_songs_folder_id")
    if not songs_folder_id:
        raise HTTPException(400, "Drive folder structure not set up")

    try:
        from hearbeat.drive import _drive_request, DRIVE_API_BASE
        resp = await _drive_request(
            "GET",
            f"{DRIVE_API_BASE}/files",
            drive_token,
            params={
                "q": f"'{songs_folder_id}' in parents and trashed=false "
                     "and (mimeType contains 'audio/' or mimeType='application/octet-stream')",
                "fields": "files(id,name,size,mimeType,createdTime)",
                "pageSize": "100",
                "orderBy": "name",
            },
        )
        resp.raise_for_status()
        files = resp.json().get("files", [])
    except Exception as e:
        logger.error("Drive list songs failed: %s", e)
        raise HTTPException(500, "Failed to list Drive songs")

    resp = JSONResponse(content={"songs": files})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.post("/drive/analyze/{file_id:path}")
async def analyze_drive_song(
    file_id: str,
    mode: str = Query("music", pattern="^(music|drumming)$"),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Download a Drive file, analyze it, and save to the user's library."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(401, "User not found")

    drive_token = await gdrive._get_valid_token(db_user)
    if not drive_token:
        raise HTTPException(400, "Google Drive not connected")

    songs_folder_id = db_user.get("drive_songs_folder_id")
    if not songs_folder_id:
        raise HTTPException(400, "Drive folder structure not set up")

    # Verify the file belongs to the user's HearBeat/Songs folder
    if not await gdrive.verify_file_in_folder(drive_token, file_id, songs_folder_id):
        raise HTTPException(403, "File is not in your HearBeat/Songs folder")

    # Download from Drive
    try:
        file_bytes = await gdrive.download_file(drive_token, file_id)
        meta = await gdrive.get_file_metadata(drive_token, file_id)
        filename = meta["name"] if meta else "audio"
    except Exception as e:
        logger.error("Drive download for analysis failed: %s", e)
        raise HTTPException(500, "Failed to download file from Drive")

    # Compute hash
    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check if already in library
    existing = await coh.db_query(
        "SELECT id FROM user_songs WHERE user_id = $1 AND file_hash = $2",
        [db_user["id"], file_hash],
    )

    if existing:
        # Already analyzed - just return the existing song
        song_id = existing[0]["id"]
        await coh.db_query(
            "UPDATE user_songs SET last_played = NOW() WHERE id = $1",
            [song_id],
        )
        resp = JSONResponse(content={"song_id": song_id, "status": "already_analyzed"})
        if new_tokens:
            resp.set_cookie(
                "access_token", new_tokens["access_token"],
                httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
            )
        return resp

    # Get duration
    duration = None
    try:
        import io
        import soundfile as sf
        audio_data, sr = sf.read(io.BytesIO(file_bytes), dtype="float32")
        duration = len(audio_data) / sr
    except Exception:
        pass

    # Run analysis
    import tempfile
    from pathlib import Path
    from hearbeat.pipeline import analyze_file as run_analysis

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / filename
    try:
        tmp_path.write_bytes(file_bytes)
        result = run_analysis(
            input_path=tmp_path,
            output_dir=OUTPUT_DIR,
            output_json=True,
            mode=mode,
        )
    except Exception as e:
        logger.error("Analysis failed for Drive file %s: %s", file_id, e)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Save to library
    rows = await coh.db_query(
        """
        INSERT INTO user_songs (user_id, filename, original_name, file_hash, file_size, duration_seconds, analysis_mode, drive_file_id, last_played)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        RETURNING id
        """,
        [db_user["id"], filename, filename, file_hash, len(file_bytes), duration, mode, file_id],
    )
    song_id = rows[0]["id"]

    # Save analysis result
    analysis_json = result.model_dump(mode="json")
    await coh.db_query(
        """
        INSERT INTO song_analysis (song_id, analysis_data, analysis_mode)
        VALUES ($1, $2, $3)
        """,
        [song_id, json.dumps(analysis_json), mode],
    )

    resp = JSONResponse(content={"song_id": song_id, "status": "analyzed"})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.post("/library/songs")
async def save_song(
    file: UploadFile = File(...),
    mode: str = Query("music", pattern="^(music|drumming)$"),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Save an uploaded song to the user's library (metadata) and Google Drive (audio file)."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        db_user = await coh.upsert_user(user["id"], user["email"], user.get("name"), user.get("picture"))

    content = await file.read()
    import hashlib
    file_hash = hashlib.sha256(content).hexdigest()

    existing = await coh.db_query(
        "SELECT id, drive_file_id FROM user_songs WHERE user_id = $1 AND file_hash = $2",
        [db_user["id"], file_hash],
    )

    if existing:
        # Dedup: song already in library, just update last_played — no Drive needed
        song_id = existing[0]["id"]
        await coh.db_query(
            "UPDATE user_songs SET last_played = NOW() WHERE id = $1",
            [song_id],
        )
    else:
        # New song: require Drive connection for persistent library storage
        drive_token = await gdrive._get_valid_token(db_user)
        songs_folder_id = db_user.get("drive_songs_folder_id") if db_user else None
        if not drive_token or not songs_folder_id:
            raise HTTPException(
                400,
                "Connect Google Drive to save songs to your library. "
                "Songs are stored in your Google Drive under HearBeat/Songs/.",
            )

        # Get duration
        duration = None
        try:
            import soundfile as sf
            import io
            audio_data, sr = sf.read(io.BytesIO(content), dtype="float32")
            duration = len(audio_data) / sr if audio_data.ndim == 1 else len(audio_data) / sr
        except Exception:
            pass

        # Upload to Google Drive (required)
        try:
            mime_type = file.content_type or "application/octet-stream"
            drive_file_id = await gdrive.upload_file(
                drive_token,
                songs_folder_id,
                file.filename or "audio",
                mime_type,
                content,
            )
        except Exception as e:
            logger.error("Drive upload failed: %s", e)
            raise HTTPException(500, "Failed to upload to Google Drive")

        rows = await coh.db_query(
            """
            INSERT INTO user_songs (user_id, filename, original_name, file_hash, file_size, duration_seconds, analysis_mode, drive_file_id, last_played)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING id
            """,
            [db_user["id"], file.filename, file.filename, file_hash, len(content), duration, mode, drive_file_id],
        )
        song_id = rows[0]["id"]

    resp = JSONResponse(content={"song_id": song_id, "file_hash": file_hash, "drive_file_id": drive_file_id if not existing else existing[0].get("drive_file_id")})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.delete("/library/songs/{song_id}")
async def delete_song(
    song_id: int,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Delete a song from the user's library."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    rows = await coh.db_query(
        "DELETE FROM user_songs WHERE id = $1 AND user_id = $2 RETURNING id",
        [song_id, db_user["id"]],
    )
    if not rows:
        raise HTTPException(404, "Song not found")

    resp = JSONResponse(content={"status": "deleted"})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.post("/library/songs/{song_id}/play")
async def mark_song_played(
    song_id: int,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Mark a song as last played (for sort order)."""
    user, _ = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    await coh.db_query(
        "UPDATE user_songs SET last_played = NOW() WHERE id = $1 AND user_id = $2",
        [song_id, db_user["id"]],
    )
    return JSONResponse(content={"status": "ok"})


@app.get("/library/songs/{song_id}/analysis")
async def get_library_song_analysis(
    song_id: int,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Retrieve saved analysis data for a library song."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    rows = await coh.db_query(
        """
        SELECT s.id, s.original_name, s.file_hash, s.duration_seconds, s.analysis_mode,
               s.drive_file_id, a.analysis_data
        FROM user_songs s
        LEFT JOIN song_analysis a ON a.song_id = s.id
        WHERE s.id = $1 AND s.user_id = $2
        """,
        [song_id, db_user["id"]],
    )
    if not rows:
        raise HTTPException(404, "Song not found")

    row = rows[0]
    if not row.get("analysis_data"):
        raise HTTPException(404, "No analysis data for this song")

    resp = JSONResponse(content={
        "song_id": row["id"],
        "filename": row["original_name"],
        "file_hash": row["file_hash"],
        "duration_seconds": row["duration_seconds"],
        "analysis_mode": row["analysis_mode"],
        "drive_file_id": row.get("drive_file_id"),
        "analysis": row["analysis_data"],
    })
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.post("/library/songs/{song_id}/reprocess")
async def reprocess_library_song(
    song_id: int,
    mode: str | None = Query(None, pattern="^(music|drumming)$"),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Reprocess a library song: re-download from Drive (if available) and re-analyze."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    # Get song
    rows = await coh.db_query(
        "SELECT id, original_name, file_hash, file_size, drive_file_id, analysis_mode FROM user_songs WHERE id = $1 AND user_id = $2",
        [song_id, db_user["id"]],
    )
    if not rows:
        raise HTTPException(404, "Song not found")

    song = rows[0]
    analysis_mode = mode or song["analysis_mode"]

    # Get audio bytes: prefer Drive, fallback to original_name
    file_bytes = None
    filename = song["original_name"]

    if song.get("drive_file_id"):
        drive_token = await gdrive._get_valid_token(db_user)
        if drive_token:
            try:
                file_bytes = await gdrive.download_file(drive_token, song["drive_file_id"])
                meta = await gdrive.get_file_metadata(drive_token, song["drive_file_id"])
                if meta:
                    filename = meta["name"]
            except Exception as e:
                logger.warning("Drive download for reprocess failed: %s", e)

    if file_bytes is None:
        raise HTTPException(400, "Audio file not available for reprocessing (Drive not connected or file removed)")

    # Run analysis
    import hashlib
    from hearbeat.pipeline import analyze_file as run_analysis

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / filename
    try:
        tmp_path.write_bytes(file_bytes)
        result = run_analysis(
            input_path=tmp_path,
            output_dir=OUTPUT_DIR,
            output_json=True,
            mode=analysis_mode,
        )
    except Exception as e:
        logger.error("Reanalysis failed for song %s: %s", song_id, e)
        raise HTTPException(500, f"Reanalysis failed: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Update hash and duration
    new_hash = hashlib.sha256(file_bytes).hexdigest()
    import io
    import soundfile as sf
    try:
        audio_data, sr = sf.read(io.BytesIO(file_bytes), dtype="float32")
        new_duration = len(audio_data) / sr
    except Exception:
        new_duration = song.get("duration_seconds")

    await coh.db_query(
        "UPDATE user_songs SET file_hash = $1, duration_seconds = $2, analysis_mode = $3 WHERE id = $4",
        [new_hash, new_duration, analysis_mode, song_id],
    )

    # Replace analysis
    analysis_json = result.model_dump(mode="json")
    await coh.db_query(
        "DELETE FROM song_analysis WHERE song_id = $1",
        [song_id],
    )
    await coh.db_query(
        """
        INSERT INTO song_analysis (song_id, analysis_data, analysis_mode)
        VALUES ($1, $2, $3)
        """,
        [song_id, json.dumps(analysis_json), analysis_mode],
    )

    resp = JSONResponse(content={"song_id": song_id, "status": "reanalyzed"})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


# --- Presets library endpoints ---


@app.get("/library/presets")
async def list_user_presets(
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """List saved haptic presets for the authenticated user."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        return JSONResponse(content={"presets": []})

    rows = await coh.db_query(
        """
        SELECT id, name, description, config, is_default, created_at, updated_at
        FROM haptic_presets
        WHERE user_id = $1
        ORDER BY is_default DESC, name ASC
        """,
        [db_user["id"]],
    )

    presets = []
    for row in rows:
        presets.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "config": row["config"],
            "is_default": row["is_default"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        })

    resp = JSONResponse(content={"presets": presets})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.post("/library/presets")
async def save_preset(
    name: str = Query(...),
    config: dict = ...,
    description: str | None = None,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Save a custom haptic preset."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    rows = await coh.db_query(
        """
        INSERT INTO haptic_presets (user_id, name, description, config)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        [db_user["id"], name, description, json.dumps(config)],
    )

    resp = JSONResponse(content={"preset_id": rows[0]["id"]})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


@app.delete("/library/presets/{preset_id}")
async def delete_preset(
    preset_id: int,
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
) -> JSONResponse:
    """Delete a custom haptic preset."""
    user, new_tokens = await coh.get_auth_user(access_token, refresh_token)
    if not user:
        raise HTTPException(401, "Not authenticated")

    db_user = await coh.get_user_by_cohesivity_id(user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")

    rows = await coh.db_query(
        "DELETE FROM haptic_presets WHERE id = $1 AND user_id = $2 AND is_default = FALSE RETURNING id",
        [preset_id, db_user["id"]],
    )
    if not rows:
        raise HTTPException(404, "Preset not found or is default")

    resp = JSONResponse(content={"status": "deleted"})
    if new_tokens:
        resp.set_cookie(
            "access_token", new_tokens["access_token"],
            httponly=True, secure=True, samesite="lax", path="/", max_age=3600,
        )
    return resp


def run_server() -> None:
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    run_server()
