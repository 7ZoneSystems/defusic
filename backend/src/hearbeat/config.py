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

# --- Filter bank configuration ---
# All values are engineering starting points, not universal truths.

FILTER_ORDER = int(os.getenv("FILTER_ORDER", "4"))
STFT_N_FFT = int(os.getenv("STFT_N_FFT", "2048"))
HOP_LENGTH = int(os.getenv("HOP_LENGTH", "512"))

# Bass analysis bands (Hz)
SUBBASS_LOW_HZ = float(os.getenv("SUBBASS_LOW_HZ", "20"))
SUBBASS_HIGH_HZ = float(os.getenv("SUBBASS_HIGH_HZ", "60"))
BASS_LOW_HZ = float(os.getenv("BASS_LOW_HZ", "60"))
BASS_HIGH_HZ = float(os.getenv("BASS_HIGH_HZ", "150"))
LOWMID_LOW_HZ = float(os.getenv("LOWMID_LOW_HZ", "150"))
LOWMID_HIGH_HZ = float(os.getenv("LOWMID_HIGH_HZ", "250"))

# Kick analysis band (Hz)
KICK_LOW_HZ = float(os.getenv("KICK_LOW_HZ", "25"))
KICK_HIGH_HZ = float(os.getenv("KICK_HIGH_HZ", "180"))

# Bass activity detection
BASS_ACTIVITY_MIN_DURATION = float(os.getenv("BASS_ACTIVITY_MIN_DURATION", "0.3"))
BASS_ACTIVITY_THRESHOLD = float(os.getenv("BASS_ACTIVITY_THRESHOLD", "0.25"))
BASS_ONSET_DELTA = float(os.getenv("BASS_ONSET_DELTA", "0.07"))
BASS_MIN_EVENT_GAP = float(os.getenv("BASS_MIN_EVENT_GAP", "0.05"))

# Kick classification
KICK_ONSET_THRESHOLD = float(os.getenv("KICK_ONSET_THRESHOLD", "0.07"))
KICK_MIN_EVENT_GAP = float(os.getenv("KICK_MIN_EVENT_GAP", "0.08"))
KICK_CONFIDENCE_THRESHOLD = float(os.getenv("KICK_CONFIDENCE_THRESHOLD", "0.5"))
KICK_CONFIDENCE_MARGIN = float(os.getenv("KICK_CONFIDENCE_MARGIN", "0.15"))

# Bass analysis frequency bands (legacy aliases)
SUBBASS_MAX_HZ = SUBBASS_HIGH_HZ
BASS_MAX_HZ = BASS_HIGH_HZ

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
