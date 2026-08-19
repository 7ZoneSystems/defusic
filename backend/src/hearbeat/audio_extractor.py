"""FFmpeg-based audio extraction and normalization."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from hearbeat.config import ANALYSIS_SAMPLE_RATE, FFMPEG_PATH

logger = logging.getLogger(__name__)


class AudioExtractionError(Exception):
    """Raised when audio extraction fails."""


def get_audio_duration(wav_path: Path) -> float:
    """Get duration of a WAV file in seconds using ffprobe."""
    cmd = [
        FFMPEG_PATH.replace("ffmpeg", "ffprobe"),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AudioExtractionError(f"ffprobe failed: {result.stderr}")
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def extract_audio(input_path: Path, output_path: Path | None = None) -> Path:
    """Extract audio from any media file and normalize to WAV.

    Args:
        input_path: Path to input media (MP4, MP3, etc.)
        output_path: Where to write the WAV. If None, creates a temp file.

    Returns:
        Path to the normalized WAV file.

    Raises:
        AudioExtractionError: If extraction fails.
    """
    if not input_path.exists():
        raise AudioExtractionError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = Path(tempfile.mkdtemp()) / "normalized.wav"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sample_rate = ANALYSIS_SAMPLE_RATE

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_f32le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-f", "wav",
        str(output_path),
    ]

    logger.info("Extracting audio: %s -> %s", input_path.name, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise AudioExtractionError(
            f"FFmpeg failed (code {result.returncode}):\n{result.stderr}"
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise AudioExtractionError("FFmpeg produced empty output file")

    duration = get_audio_duration(output_path)
    logger.info(
        "Extracted %.1fs of audio at %d Hz -> %s",
        duration, sample_rate, output_path,
    )
    return output_path


def check_audio_stream(input_path: Path) -> bool:
    """Check if the input file has an audio stream."""
    cmd = [
        FFMPEG_PATH.replace("ffmpeg", "ffprobe"),
        "-v", "quiet",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return "audio" in result.stdout
