"""Dedicated kick detection using multi-expert onset fusion.

Architecture:
    drum/percussion signal
        -> kick-focused bandpass filter (25-180 Hz)
        -> multi-expert onset fusion (HFC, complex, flux, RMS)
        -> low-frequency energy evidence
        -> temporal shape filtering (attack/decay)
        -> beat context
        -> kick / drum_onset classification

References:
- Essentia onset detection: https://essentia.upf.edu/reference/streaming_OnsetDetection.html
- Score-level fusion: https://www.researchgate.net/publication/220722982
"""

from __future__ import annotations

import logging

import numpy as np

from hearbeat.config import (
    FILTER_ORDER,
    HOP_LENGTH,
    KICK_CONFIDENCE_THRESHOLD,
    KICK_HIGH_HZ,
    KICK_LOW_HZ,
    STFT_N_FFT,
)
from hearbeat.experts import compute_all_experts
from hearbeat.filter_bank import FilterBank
from hearbeat.onset_fusion import (
    FusionConfig,
    OnsetCandidate,
    multi_expert_fusion,
)

logger = logging.getLogger(__name__)


class KickDetector:
    """Multi-expert kick detector.

    Uses multiple onset experts on a kick-focused filtered signal,
    combined with low-frequency energy evidence and temporal shape analysis.
    """

    def __init__(self, sr: int = 44100) -> None:
        self.sr = sr
        self._filter_bank: FilterBank | None = None

    def _get_filter_bank(self) -> FilterBank:
        if self._filter_bank is None:
            self._filter_bank = FilterBank(
                sr=self.sr,
                bands={"kick_analysis": (KICK_LOW_HZ, KICK_HIGH_HZ)},
                order=FILTER_ORDER,
            )
        return self._filter_bank

    def detect(
        self,
        drums: np.ndarray,
        beats: np.ndarray,
        hop_length: int = HOP_LENGTH,
    ) -> list[dict]:
        """Detect kick events using multi-expert fusion.

        Args:
            drums: Drum/percussion audio array (mono).
            beats: Beat timestamps for beat alignment.
            hop_length: STFT hop length.

        Returns:
            List of kick event dicts.
        """
        if len(drums) == 0:
            return []

        fb = self._get_filter_bank()
        kick_filtered = fb.filter_band(drums, "kick_analysis", causal=False)

        # Multi-expert onset fusion on kick-filtered signal
        experts = compute_all_experts(
            kick_filtered, sr=self.sr, n_fft=STFT_N_FFT,
            hop_length=hop_length,
            experts=["hfc", "complex", "flux", "rms_diff"],
        )

        config = FusionConfig(
            cluster_tolerance_ms=25.0,
            minimum_event_gap_ms=80.0,
            expert_weights={
                "hfc": 0.15,
                "complex": 0.40,
                "flux": 0.25,
                "rms_diff": 0.20,
            },
            min_fused_score=0.04,
        )

        candidates = multi_expert_fusion(experts, config=config, delta=0.05)

        # Score each candidate with kick-specific features
        events: list[dict] = []
        for cand in candidates:
            kick_score, kick_features = self._score_kick(
                drums, kick_filtered, cand, beats
            )

            # Temporal shape gates: reject continuous signals
            if kick_features.get("attack_ratio", 0) < 2.0:
                continue
            if kick_features.get("decay_ratio", 0) < 1.3:
                continue

            # Beat alignment
            nearest_beat, beat_delta = _align_to_beat(cand.time, beats)

            event_type = "kick" if kick_score >= KICK_CONFIDENCE_THRESHOLD else "drum_onset"

            events.append({
                "time": cand.time,
                "type": event_type,
                "strength": float(np.clip(cand.fused_score, 0.0, 1.0)),
                "confidence": kick_score,
                "nearest_beat": nearest_beat,
                "beat_delta_seconds": round(beat_delta, 6),
                "beat_position": _beat_position(cand.time, beats),
                "kick_features": kick_features,
                "expert_scores": cand.expert_scores,
                "fused_score": cand.fused_score,
                "n_experts_agreeing": cand.n_experts_agreeing,
            })

        logger.info(
            "Kick detection: %d candidates -> %d kicks, %d drum_onset",
            len(candidates),
            sum(1 for e in events if e["type"] == "kick"),
            sum(1 for e in events if e["type"] == "drum_onset"),
        )

        return events

    def _score_kick(
        self,
        drums: np.ndarray,
        kick_filtered: np.ndarray,
        candidate: OnsetCandidate,
        beats: np.ndarray,
    ) -> tuple[float, dict[str, float]]:
        """Score a kick candidate using multi-expert fusion + spectral features.

        Returns (kick_score, feature_dict) where kick_score is 0.0-1.0.
        """
        onset_time = candidate.time
        center = int(onset_time * self.sr)

        # Extract features around this onset (50ms before, 100ms after)
        pre_samples = int(0.05 * self.sr)
        post_samples = int(0.10 * self.sr)
        start = max(0, center - pre_samples)
        end = min(len(drums), center + post_samples)

        segment = drums[start:end]
        kick_segment = kick_filtered[start:end]

        if len(segment) < 2:
            return 0.0, {}

        # --- Spectral features ---
        total_energy = float(np.sum(segment**2))
        kick_energy = float(np.sum(kick_segment**2))
        low_ratio = kick_energy / total_energy if total_energy > 0 else 0.0

        fft = np.abs(np.fft.rfft(segment))
        freqs = np.fft.rfftfreq(len(segment), 1.0 / self.sr)

        centroid = 0.0
        bandwidth = 0.0
        if fft.sum() > 0:
            centroid = float(np.sum(freqs * fft) / np.sum(fft))
            bandwidth = float(np.sqrt(
                np.sum(fft * (freqs - centroid) ** 2) / np.sum(fft)
            ))

        sub_mask = freqs < 60
        sub_energy = float(np.sum(fft[sub_mask] ** 2)) if sub_mask.any() else 0.0

        # --- Temporal shape ---
        if len(kick_segment) > 0:
            peak_val = float(np.max(np.abs(kick_segment)))
            mean_val = float(np.mean(np.abs(kick_segment)))
            attack_ratio = peak_val / mean_val if mean_val > 0 else 1.0
        else:
            attack_ratio = 1.0

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

        # --- Kick score from multi-expert + features ---
        score = 0.0

        # Fused onset expert score (the multi-expert evidence)
        fused = candidate.fused_score
        if fused > 0.3:
            score += 0.25
        elif fused > 0.15:
            score += 0.15
        elif fused > 0.08:
            score += 0.08

        # Number of agreeing experts
        n_agree = candidate.n_experts_agreeing
        if n_agree >= 3:
            score += 0.15
        elif n_agree >= 2:
            score += 0.10

        # Low energy ratio
        if low_ratio > 0.6:
            score += 0.15
        elif low_ratio > 0.4:
            score += 0.10
        elif low_ratio > 0.25:
            score += 0.05

        # Spectral centroid
        if centroid < 150:
            score += 0.10
        elif centroid < 250:
            score += 0.06

        # Attack shape
        if attack_ratio > 3.0:
            score += 0.10
        elif attack_ratio > 2.0:
            score += 0.05

        # Decay
        if 1.3 < decay_ratio < 5.0:
            score += 0.10
        elif decay_ratio > 5.0:
            score += 0.05

        # Sub-bass energy
        if sub_energy > 0:
            score += 0.05

        score = min(score, 1.0)

        kick_features = {
            "kick_score": round(score, 4),
            "fused_score": round(fused, 4),
            "n_experts_agreeing": n_agree,
            "low_energy_ratio": round(low_ratio, 4),
            "spectral_centroid": round(centroid, 2),
            "spectral_bandwidth": round(bandwidth, 2),
            "attack_ratio": round(attack_ratio, 2),
            "decay_ratio": round(decay_ratio, 2),
            "sub_energy": round(sub_energy, 6),
            "expert_scores": candidate.expert_scores,
        }

        return score, kick_features


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
