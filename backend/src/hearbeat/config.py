"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "outputs")))
TEST_AUDIO_DIR = BASE_DIR / "test_audio"
MODELS_DIR = Path(os.getenv("MODELS_DIR", str(BASE_DIR / "models")))

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs")
DEVICE = os.getenv("DEVICE", "cpu")
ANALYSIS_SAMPLE_RATE = int(os.getenv("ANALYSIS_SAMPLE_RATE", "44100"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
