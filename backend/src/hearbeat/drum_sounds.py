"""Synthetic diagnostic sound generation for all event types."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SR = 44100


@dataclass
class SoundConfig:
    """Configuration for a single diagnostic sound."""
    freq: float = 800.0
    duration: float = 0.015
    volume: float = 0.6
    decay: float = 0.3
    fade_samples: int = 64
    waveform: str = "sine"  # sine, triangle, noise_burst


@dataclass
class LayerConfig:
    """Configuration for a diagnostic layer (intensity levels)."""
    beat: float = 0.45
    drum: float = 0.60
    kick: float = 0.70
    snare: float = 0.65
    hihat: float = 0.40
    drum_onset: float = 0.55
    bass: float = 0.90
    bass_beat: float = 0.85
    bass_offbeat: float = 0.70
    bass_accent: float = 0.75
    subbass: float = 0.70


# Sound definitions for each event type
SOUND_DEFS: dict[str, SoundConfig] = {
    "beat": SoundConfig(freq=1000.0, duration=0.012, decay=0.25, waveform="sine"),
    "kick": SoundConfig(freq=80.0, duration=0.035, decay=0.35, waveform="triangle"),
    "snare": SoundConfig(freq=400.0, duration=0.025, decay=0.30, waveform="noise_burst"),
    "hihat": SoundConfig(freq=6000.0, duration=0.010, decay=0.20, waveform="noise_burst"),
    "drum_onset": SoundConfig(freq=800.0, duration=0.020, decay=0.30, waveform="triangle"),
    "bass": SoundConfig(freq=100.0, duration=0.040, decay=0.40, waveform="triangle"),
    "bass_beat": SoundConfig(freq=100.0, duration=0.035, decay=0.35, waveform="triangle"),
    "bass_offbeat": SoundConfig(freq=120.0, duration=0.025, decay=0.30, waveform="triangle"),
    "bass_accent": SoundConfig(freq=90.0, duration=0.040, decay=0.35, waveform="triangle"),
    "subbass": SoundConfig(freq=250.0, duration=0.045, decay=0.40, waveform="triangle"),
}

# Layer intensity defaults
DEFAULT_LAYER_CONFIG = LayerConfig()


def generate_sound(
    config: SoundConfig,
    volume: float,
    sr: int = DEFAULT_SR,
) -> np.ndarray:
    """Generate a single synthetic diagnostic sound.

    Args:
        config: Sound configuration (freq, duration, etc.)
        volume: Output volume 0.0-1.0.
        sr: Sample rate.

    Returns:
        Audio array (float32).
    """
    n_samples = int(config.duration * sr)
    if n_samples == 0:
        return np.array([], dtype=np.float32)

    t = np.arange(n_samples) / sr

    # Generate waveform
    if config.waveform == "sine":
        wave = np.sin(2 * np.pi * config.freq * t)
    elif config.waveform == "triangle":
        # Triangle wave via integrated square
        wave = 2 * np.abs(2 * (config.freq * t % 1) - 1) - 1
    elif config.waveform == "noise_burst":
        # Shaped noise burst
        rng = np.random.default_rng(42)
        wave = rng.standard_normal(n_samples)
        # Apply bandpass-ish shape via exponential decay of high freq content
        fft = np.fft.rfft(wave)
        freqs = np.fft.rfftfreq(n_samples, 1.0 / sr)
        # Roll off above fundamental
        mask = freqs > config.freq * 3
        fft[mask] *= 0.1
        wave = np.fft.irfft(fft, n=n_samples)
    else:
        wave = np.sin(2 * np.pi * config.freq * t)

    # Apply envelope: fast attack + exponential decay
    attack_samples = min(int(0.001 * sr), n_samples // 4)
    envelope = np.ones(n_samples)
    if config.decay > 0 and n_samples > 0:
        decay_time = config.duration * config.decay
        envelope *= np.exp(-t / max(decay_time, 1e-6))
    if attack_samples > 0:
        envelope[:attack_samples] *= np.linspace(0, 1, attack_samples)

    wave *= envelope

    # Fade in/out to avoid clicks
    fade = min(config.fade_samples, n_samples // 4)
    if fade > 0:
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)

    # Normalize and apply volume
    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak * volume

    return wave.astype(np.float32)


def get_layer_volume(event_type: str, layer_config: LayerConfig | None = None) -> float:
    """Get the default volume for an event type."""
    cfg = layer_config or DEFAULT_LAYER_CONFIG
    return getattr(cfg, event_type, 0.5)
