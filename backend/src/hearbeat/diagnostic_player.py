"""Diagnostic audio player: generates multi-layer diagnostic tracks."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from hearbeat.drum_sounds import (
    DEFAULT_SR,
    LayerConfig,
    SOUND_DEFS,
    generate_sound,
    get_layer_volume,
)

logger = logging.getLogger(__name__)


def generate_layer(
    timestamps: list[float],
    event_type: str,
    sr: int = DEFAULT_SR,
    layer_config: LayerConfig | None = None,
) -> np.ndarray:
    """Generate audio for a single event layer.

    Args:
        timestamps: Event times in seconds.
        event_type: Type of sound to generate.
        sr: Sample rate.
        layer_config: Volume configuration.

    Returns:
        Audio array (float32).
    """
    if not timestamps:
        return np.array([], dtype=np.float32)

    duration = max(timestamps) + 0.5
    n_samples = int(duration * sr)
    audio = np.zeros(n_samples, dtype=np.float64)

    sound_cfg = SOUND_DEFS.get(event_type, SOUND_DEFS["drum_onset"])
    volume = get_layer_volume(event_type, layer_config)

    for ts in timestamps:
        start = int(ts * sr)
        sound = generate_sound(sound_cfg, volume, sr)
        end = min(start + len(sound), n_samples)
        if start >= n_samples:
            continue
        audio[start:end] += sound[: end - start]

    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio /= peak

    return audio.astype(np.float32)


def generate_drum_diagnostic(
    events: list[dict],
    sr: int = DEFAULT_SR,
    layer_config: LayerConfig | None = None,
    active_layers: set[str] | None = None,
) -> tuple[np.ndarray, int]:
    """Generate combined diagnostic audio for drum analysis events.

    Args:
        events: List of drum event dicts with 'time' and 'type'.
        sr: Sample rate.
        layer_config: Volume configuration.
        active_layers: Set of event types to include. None = all.

    Returns:
        Tuple of (mixed_audio, sample_rate).
    """
    if not events:
        return np.array([], dtype=np.float32), sr

    duration = max(e["time"] for e in events) + 0.5
    n_samples = int(duration * sr)
    audio = np.zeros(n_samples, dtype=np.float64)

    # Group events by type
    by_type: dict[str, list[float]] = {}
    for e in events:
        etype = e["type"]
        if active_layers is not None and etype not in active_layers:
            continue
        by_type.setdefault(etype, []).append(e["time"])

    # Generate each layer
    for etype, times in by_type.items():
        layer = generate_layer(times, etype, sr, layer_config)
        if len(layer) > 0:
            end = min(len(layer), n_samples)
            audio[:end] += layer[:end]

    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio /= peak

    return audio.astype(np.float32), sr


def generate_music_diagnostic(
    events: list,
    sr: int = DEFAULT_SR,
    layer_config: LayerConfig | None = None,
    active_layers: set[str] | None = None,
) -> tuple[np.ndarray, int]:
    """Generate diagnostic audio for music enjoyment mode events.

    Events are AnalysisEvent objects with .time and .type attributes.
    """
    if not events:
        return np.array([], dtype=np.float32), sr

    duration = max(e.time for e in events) + 0.5
    n_samples = int(duration * sr)
    audio = np.zeros(n_samples, dtype=np.float64)

    # Map event types to diagnostic sounds
    type_map = {
        "beat": "beat",
        "bass": "bass",
        "bass_beat": "bass_beat",
        "bass_offbeat": "bass_offbeat",
        "bass_accent": "bass_accent",
    }

    by_type: dict[str, list[float]] = {}
    for e in events:
        sound_type = type_map.get(e.type, "beat")
        if active_layers is not None and sound_type not in active_layers:
            continue
        by_type.setdefault(sound_type, []).append(e.time)

    for sound_type, times in by_type.items():
        layer = generate_layer(times, sound_type, sr, layer_config)
        if len(layer) > 0:
            end = min(len(layer), n_samples)
            audio[:end] += layer[:end]

    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio /= peak

    return audio.astype(np.float32), sr


def save_wav(audio: np.ndarray, path: Path | str, sr: int = DEFAULT_SR) -> Path:
    """Save audio array to a WAV file."""
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="FLOAT")
    logger.info("Saved WAV: %s (%.1fs)", path, len(audio) / sr)
    return path


def play_audio(audio: np.ndarray, sr: int = DEFAULT_SR) -> None:
    """Play audio array through the default output device."""
    if len(audio) == 0:
        logger.warning("No audio to play")
        return
    import sounddevice as sd

    duration = len(audio) / sr
    logger.info("Playing %.1fs of audio at %d Hz", duration, sr)
    sd.play(audio, sr, blocking=True)
