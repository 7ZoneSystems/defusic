"""Dedicated kick detection from drum/percussive signal.

Operates on the drum stem (or drum-separated signal) using a low-frequency
filter path. Produces kick candidates with confidence scores, separate from
the general onset detector.

Pipeline:
    drum signal
        -> kick-focused filter (25-180 Hz)
        -> onset strength
        -> spectral features (centroid, bandwidth, energy ratio)
        -> temporal context (attack/decay shape)
        -> kick score -> kick / drum_onset
"""

from __future__ import annotations

import logging

import numpy as np

from hearbeat.config import (
    FILTER_ORDER,
    HOP_LENGTH,
    KICK_CONFIDENCE_MARGIN,
    KICK_CONFIDENCE_THRESHOLD,
    KICK_HIGH_HZ,
    KICK_LOW_HZ,
    KICK_MIN_EVENT_GAP,
    KICK_ONSET_THRESHOLD,
    STFT_N_FFT,
)
from hearbeat.filter_bank import FilterBank

logger = logging.getLogger(__name__)


class KickDetector:
    """Detects kick drum events from a drum/percussive signal.

    Uses a dedicated low-frequency filter path with onset detection,
    spectral features, and temporal context analysis.
    """

    def __init__(self, sr: int = 44100) -> None:
        self.sr = sr
        self._filter_bank: FilterBank | None = None

    def _get_filter_bank(self) -> FilterBank:
        if self._filter_bank is None:
            self._filter_bank = FilterBank(
                sr=self.sr,
                bands={
                    "kick_analysis": (KICK_LOW_HZ, KICK_HIGH_HZ),
                },
                order=FILTER_ORDER,
            )
        return self._filter_bank

    def detect(
        self,
        drums: np.ndarray,
        beats: np.ndarray,
        hop_length: int = HOP_LENGTH,
    ) -> list[dict]:
        """Detect kick events from a drum signal.

        Args:
            drums: Drum/percussion audio array (mono).
            beats: Beat timestamps for beat alignment.
            hop_length: STFT hop length.

        Returns:
            List of kick event dicts with time, type, confidence, features.
        """
        if len(drums) == 0:
            return []

        fb = self._get_filter_bank()

        # Filter for kick frequency range
        kick_filtered = fb.filter_band(drums, "kick_analysis", causal=False)

        # Onset strength on kick-filtered signal
        onset_env = _onset_strength(kick_filtered, self.sr, hop_length)

        # Detect onset peaks
        onset_times, onset_strengths = _detect_onset_peaks(
            kick_filtered, self.sr, hop_length, onset_env
        )

        if len(onset_times) == 0:
            return []

        # Compute raw onset envelope statistics for gating
        raw_onset_median = float(np.median(onset_env)) if len(onset_env) > 0 else 0.0
        raw_onset_max = float(np.max(onset_env)) if len(onset_env) > 0 else 0.0

        # For each onset, compute kick features and score
        events: list[dict] = []
        min_gap_samples = int(KICK_MIN_EVENT_GAP * self.sr)
        last_onset_sample = -min_gap_samples

        for i, onset_time in enumerate(onset_times):
            onset_sample = int(onset_time * self.sr)

            # Enforce minimum gap
            if onset_sample - last_onset_sample < min_gap_samples:
                continue

            strength = float(onset_strengths[i]) if i < len(onset_strengths) else 0.5

            # Gate: reject weak onsets — for continuous signals the normalized
            # strength can be high, but the raw onset energy is low.
            # Require onset frame to be significantly above the median.
            onset_frame = int(onset_time * self.sr / hop_length)
            if onset_frame < len(onset_env):
                raw_val = float(onset_env[onset_frame])
            else:
                raw_val = 0.0

            # Skip if onset is not meaningfully above median (continuous signal)
            if raw_onset_median > 0 and raw_val < raw_onset_median * 2.0:
                continue
            elif raw_val < 0.01:
                continue

            # Extract features around this onset
            features = self._extract_kick_features(drums, kick_filtered, onset_time)

            # Score as kick
            kick_score, kick_features = self._score_kick(features, strength)

            # Reject candidates that lack kick-like temporal shape:
            # - attack_ratio must be > 2.0 (sharp onset)
            # - decay_ratio must be > 1.3 (energy decreases after onset)
            if features["attack_ratio"] < 2.0:
                continue
            if features["decay_ratio"] < 1.3:
                continue

            # Beat alignment
            nearest_beat, beat_delta = _align_to_beat(onset_time, beats)

            event_type = "kick" if kick_score >= KICK_CONFIDENCE_THRESHOLD else "drum_onset"

            events.append({
                "time": float(onset_time),
                "type": event_type,
                "strength": strength,
                "confidence": kick_score,
                "nearest_beat": nearest_beat,
                "beat_delta_seconds": round(beat_delta, 6),
                "beat_position": _beat_position(onset_time, beats),
                "kick_features": kick_features,
            })

            last_onset_sample = onset_sample

        logger.info(
            "Kick detection: %d candidates, %d kicks, %d drum_onset",
            len(events),
            sum(1 for e in events if e["type"] == "kick"),
            sum(1 for e in events if e["type"] == "drum_onset"),
        )

        return events

    def _extract_kick_features(
        self,
        drums: np.ndarray,
        kick_filtered: np.ndarray,
        onset_time: float,
    ) -> dict[str, float]:
        """Extract features around a kick candidate onset.

        Inspects a window of ~50ms before to ~100ms after the onset.
        """
        center = int(onset_time * self.sr)
        pre_samples = int(0.05 * self.sr)  # 50ms before
        post_samples = int(0.10 * self.sr)  # 100ms after
        start = max(0, center - pre_samples)
        end = min(len(drums), center + post_samples)

        segment = drums[start:end]
        kick_segment = kick_filtered[start:end]

        if len(segment) < 2:
            return self._default_features()

        # RMS of full drum signal in window
        drum_rms = float(np.sqrt(np.mean(segment**2)))

        # RMS of kick-filtered signal
        kick_rms = float(np.sqrt(np.mean(kick_segment**2)))

        # Low energy ratio: how much of the drum energy is in the kick band
        total_energy = float(np.sum(segment**2))
        kick_energy = float(np.sum(kick_segment**2))
        low_ratio = kick_energy / total_energy if total_energy > 0 else 0.0

        # Spectral features
        fft = np.abs(np.fft.rfft(segment))
        freqs = np.fft.rfftfreq(len(segment), 1.0 / self.sr)

        centroid = 0.0
        bandwidth = 0.0
        if fft.sum() > 0:
            centroid = float(np.sum(freqs * fft) / np.sum(fft))
            bandwidth = float(np.sqrt(
                np.sum(fft * (freqs - centroid) ** 2) / np.sum(fft)
            ))

        # Sub-band energy (below 60 Hz)
        sub_mask = freqs < 60
        sub_energy = float(np.sum(fft[sub_mask] ** 2)) if sub_mask.any() else 0.0

        # Attack shape: ratio of peak to mean in the window
        if len(kick_segment) > 0:
            peak_val = float(np.max(np.abs(kick_segment)))
            mean_val = float(np.mean(np.abs(kick_segment)))
            attack_ratio = peak_val / mean_val if mean_val > 0 else 1.0
        else:
            attack_ratio = 1.0

        # Decay shape: compare first half to second half of post-onset
        post_start = center - start
        post_end = len(kick_segment)
        if post_end - post_start > 10:
            first_half = kick_segment[post_start:post_start + (post_end - post_start) // 2]
            second_half = kick_segment[post_start + (post_end - post_start) // 2:post_end]
            first_energy = float(np.sum(first_half**2))
            second_energy = float(np.sum(second_half**2))
            decay_ratio = first_energy / second_energy if second_energy > 0 else 1.0
        else:
            decay_ratio = 1.0

        return {
            "drum_rms": drum_rms,
            "kick_rms": kick_rms,
            "low_energy_ratio": low_ratio,
            "sub_energy": sub_energy,
            "spectral_centroid": centroid,
            "spectral_bandwidth": bandwidth,
            "attack_ratio": attack_ratio,
            "decay_ratio": decay_ratio,
        }

    def _score_kick(
        self, features: dict[str, float], onset_strength: float
    ) -> tuple[float, dict[str, float]]:
        """Score a kick candidate based on features.

        Returns (kick_score, feature_dict) where kick_score is 0.0-1.0.
        """
        low_ratio = features["low_energy_ratio"]
        centroid = features["spectral_centroid"]
        bandwidth = features["spectral_bandwidth"]
        attack_ratio = features["attack_ratio"]
        decay_ratio = features["decay_ratio"]
        sub_energy = features["sub_energy"]

        score = 0.0

        # Low energy ratio: kicks should have strong low-frequency content
        if low_ratio > 0.6:
            score += 0.25
        elif low_ratio > 0.4:
            score += 0.15
        elif low_ratio > 0.25:
            score += 0.08

        # Spectral centroid: kicks are low-frequency
        if centroid < 150:
            score += 0.20
        elif centroid < 250:
            score += 0.12
        elif centroid < 400:
            score += 0.05

        # Spectral bandwidth: kicks have moderate bandwidth
        if 200 < bandwidth < 800:
            score += 0.10
        elif bandwidth < 200:
            score += 0.05

        # Onset strength: kicks should have strong attacks
        if onset_strength > 0.7:
            score += 0.20
        elif onset_strength > 0.4:
            score += 0.10
        elif onset_strength > 0.2:
            score += 0.05

        # Attack shape: sharp attack
        if attack_ratio > 3.0:
            score += 0.10
        elif attack_ratio > 2.0:
            score += 0.05

        # Decay: moderate decay (not too fast, not too slow)
        if 1.0 < decay_ratio < 5.0:
            score += 0.10
        elif decay_ratio > 5.0:
            score += 0.05

        # Sub-bass energy
        if sub_energy > 0:
            score += 0.05

        score = min(score, 1.0)

        kick_features = {
            "kick_score": round(score, 4),
            "low_energy_ratio": round(low_ratio, 4),
            "spectral_centroid": round(centroid, 2),
            "spectral_bandwidth": round(bandwidth, 2),
            "attack_ratio": round(attack_ratio, 2),
            "decay_ratio": round(decay_ratio, 2),
            "onset_strength": round(onset_strength, 4),
        }

        return score, kick_features


def _onset_strength(
    signal: np.ndarray, sr: int, hop_length: int
) -> np.ndarray:
    """Compute onset strength envelope."""
    try:
        import librosa

        onset_env = librosa.onset.onset_strength(
            y=signal.astype(np.float32),
            sr=sr,
            hop_length=hop_length,
        )
        return onset_env.astype(np.float64)
    except ImportError:
        from scipy.signal import stft
        _, _, Zxx = stft(signal, fs=sr, nperseg=STFT_N_FFT, noverlap=STFT_N_FFT - hop_length)
        magnitude = np.abs(Zxx)
        diff = np.diff(magnitude, axis=1)
        flux = np.maximum(0, diff).sum(axis=0)
        return flux.astype(np.float64)


def _detect_onset_peaks(
    audio: np.ndarray, sr: int, hop_length: int, onset_env: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Detect onset peaks using librosa's peak picking."""
    try:
        import librosa

        onset_frames = librosa.onset.onset_detect(
            y=audio.astype(np.float32),
            sr=sr,
            hop_length=hop_length,
            onset_envelope=onset_env,
            delta=KICK_ONSET_THRESHOLD,
        )

        if len(onset_frames) == 0:
            return np.array([]), np.array([])

        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

        strengths = np.zeros(len(onset_frames))
        for i, frame in enumerate(onset_frames):
            if frame < len(onset_env):
                strengths[i] = onset_env[frame]

        if strengths.max() > 0:
            strengths = strengths / strengths.max()

        return onset_times, strengths

    except ImportError:
        # Fallback: simple threshold-based peak detection
        return _simple_peak_detect(onset_env, sr, hop_length)


def _simple_peak_detect(
    onset_env: np.ndarray, sr: int, hop_length: int
) -> tuple[np.ndarray, np.ndarray]:
    """Simple peak detection fallback."""
    if len(onset_env) < 3:
        return np.array([]), np.array([])

    threshold = np.mean(onset_env) + KICK_ONSET_THRESHOLD * np.std(onset_env)
    min_distance = int(0.05 * sr / hop_length)

    peaks = []
    strengths = []
    last_peak = -min_distance

    for i in range(1, len(onset_env) - 1):
        if (
            onset_env[i] > threshold
            and onset_env[i] >= onset_env[i - 1]
            and onset_env[i] >= onset_env[i + 1]
            and i - last_peak >= min_distance
        ):
            peaks.append(i)
            strengths.append(onset_env[i])
            last_peak = i

    if not peaks:
        return np.array([]), np.array([])

    times = np.array(peaks) * hop_length / sr
    strengths_arr = np.array(strengths)
    if strengths_arr.max() > 0:
        strengths_arr = strengths_arr / strengths_arr.max()

    return times, strengths_arr


def _align_to_beat(
    onset_time: float, beats: np.ndarray
) -> tuple[float, float]:
    """Find nearest beat and delta."""
    if len(beats) == 0:
        return 0.0, 0.0

    idx = int(np.argmin(np.abs(beats - onset_time)))
    nearest = float(beats[idx])
    delta = onset_time - nearest
    return nearest, delta


def _beat_position(onset_time: float, beats: np.ndarray) -> float:
    """Normalized position within beat cycle (0.0 to 1.0)."""
    if len(beats) < 2:
        return 0.0

    idx = int(np.searchsorted(beats, onset_time)) - 1
    idx = max(0, min(idx, len(beats) - 2))

    beat_start = beats[idx]
    beat_end = beats[idx + 1]
    beat_duration = beat_end - beat_start

    if beat_duration <= 0:
        return 0.0

    position = (onset_time - beat_start) / beat_duration
    return float(np.clip(position, 0.0, 1.0))
