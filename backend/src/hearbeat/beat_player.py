"""Beat playback: generate and play click tracks from analysis results."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SR = 44100


def generate_click_train(
    timestamps: list[float],
    sr: int = DEFAULT_SR,
    click_freq: float = 1000.0,
    click_duration: float = 0.015,
    click_volume: float = 0.8,
    fade_samples: int = 64,
) -> tuple[np.ndarray, int]:
    """Generate a click train audio signal from timestamps.

    Args:
        timestamps: Event times in seconds.
        sr: Sample rate.
        click_freq: Frequency of the click tone in Hz.
        click_duration: Duration of each click in seconds.
        click_volume: Peak amplitude 0.0-1.0.
        fade_samples: Fade in/out samples to avoid pops.

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    if not timestamps:
        return np.array([], dtype=np.float32), sr

    duration = max(timestamps) + 0.5  # padding after last click
    n_samples = int(duration * sr)
    audio = np.zeros(n_samples, dtype=np.float64)

    click_len = int(click_duration * sr)
    t_click = np.arange(click_len) / sr
    click = click_volume * np.sin(2 * np.pi * click_freq * t_click)

    # Apply exponential decay envelope
    envelope = np.exp(-t_click / (click_duration * 0.3))
    click *= envelope

    # Apply fade in/out to avoid clicks
    if fade_samples > 0 and len(click) > 2 * fade_samples:
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        click[:fade_samples] *= fade_in
        click[-fade_samples:] *= fade_out

    for ts in timestamps:
        start = int(ts * sr)
        end = start + click_len
        if end > n_samples:
            end = n_samples
            click_trimmed = click[: end - start]
        else:
            click_trimmed = click
        audio[start:end] += click_trimmed

    # Clip to prevent overflow
    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio /= peak

    return audio.astype(np.float32), sr


def generate_multi_track(
    beat_timestamps: list[float],
    bass_beat_timestamps: list[float],
    bass_offbeat_timestamps: list[float],
    sr: int = DEFAULT_SR,
) -> tuple[np.ndarray, int]:
    """Generate a multi-layer click track with different sounds per event type.

    - Beats: short high-pitched click (1000 Hz)
    - Bass+Beat: lower thud (200 Hz)
    - Bass offbeat: mid-tone blip (600 Hz)

    Returns:
        Tuple of (mixed_audio, sample_rate)
    """
    if not any([beat_timestamps, bass_beat_timestamps, bass_offbeat_timestamps]):
        return np.array([], dtype=np.float32), sr

    all_times = beat_timestamps + bass_beat_timestamps + bass_offbeat_timestamps
    duration = max(all_times) + 0.5
    n_samples = int(duration * sr)
    audio = np.zeros(n_samples, dtype=np.float64)

    def _place_clicks(timestamps: list[float], freq: float, vol: float, dur: float = 0.02):
        if not timestamps:
            return
        click_len = int(dur * sr)
        t_click = np.arange(click_len) / sr
        click = vol * np.sin(2 * np.pi * freq * t_click)
        envelope = np.exp(-t_click / (dur * 0.25))
        click *= envelope
        # Fade
        fade = min(32, click_len // 4)
        if fade > 0:
            click[:fade] *= np.linspace(0, 1, fade)
            click[-fade:] *= np.linspace(1, 0, fade)
        for ts in timestamps:
            start = int(ts * sr)
            end = min(start + click_len, n_samples)
            audio[start:end] += click[: end - start]

    # Beat clicks: high, short
    _place_clicks(beat_timestamps, freq=1000.0, vol=0.3, dur=0.012)
    # Bass+beat: low thud
    _place_clicks(bass_beat_timestamps, freq=200.0, vol=0.7, dur=0.025)
    # Bass offbeat: mid blip
    _place_clicks(bass_offbeat_timestamps, freq=600.0, vol=0.5, dur=0.018)

    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio /= peak

    return audio.astype(np.float32), sr


def play_audio(audio: np.ndarray, sr: int = DEFAULT_SR) -> None:
    """Play audio array through the default output device."""
    if len(audio) == 0:
        logger.warning("No audio to play")
        return
    import sounddevice as sd
    duration = len(audio) / sr
    logger.info("Playing %.1fs of audio at %d Hz", duration, sr)
    sd.play(audio, sr, blocking=True)


def save_wav(audio: np.ndarray, path: Path | str, sr: int = DEFAULT_SR) -> Path:
    """Save audio array to a WAV file."""
    import soundfile as sf
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="FLOAT")
    logger.info("Saved WAV: %s (%.1fs)", path, len(audio) / sr)
    return path
