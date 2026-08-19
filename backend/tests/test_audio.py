"""Tests for audio extraction (requires FFmpeg)."""

from pathlib import Path

import numpy as np
import pytest

from hearbeat.audio_extractor import extract_audio, check_audio_stream, AudioExtractionError


def _create_test_wav(path: Path, duration: float = 2.0, sr: int = 44100) -> None:
    """Create a simple WAV file for testing."""
    import wave
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, dtype=np.float32)
    # Simple 440 Hz sine wave
    samples = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def test_extract_audio_from_wav(tmp_path):
    input_wav = tmp_path / "input.wav"
    _create_test_wav(input_wav, duration=1.0)

    output_wav = tmp_path / "output.wav"
    result = extract_audio(input_wav, output_wav)

    assert result.exists()
    assert result.stat().st_size > 0


def test_extract_nonexistent_file():
    with pytest.raises(AudioExtractionError):
        extract_audio(Path("/nonexistent/file.mp4"))


def test_check_audio_stream(tmp_path):
    wav = tmp_path / "test.wav"
    _create_test_wav(wav, duration=0.5)
    assert check_audio_stream(wav) is True


def test_check_no_audio_stream(tmp_path):
    # Create a file with no audio stream
    txt_file = tmp_path / "not_audio.txt"
    txt_file.write_text("hello")
    assert check_audio_stream(txt_file) is False
