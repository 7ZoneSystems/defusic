"""Multi-expert onset fusion with temporal clustering and score-level combination.

Architecture:
    expert onset envelopes
        -> robust percentile normalization
        -> peak extraction per expert
        -> temporal clustering (within tolerance)
        -> weighted score-level fusion
        -> confidence calculation
        -> candidate events

References:
- Score-level onset fusion: https://www.researchgate.net/publication/220722982
- Rhythmic onset fusion: https://www.researchgate.net/publication/220736078
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from hearbeat.experts import ExpertOutput

logger = logging.getLogger(__name__)


@dataclass
class OnsetCandidate:
    """A fused onset candidate after temporal clustering."""

    time: float
    frame: int
    expert_scores: dict[str, float] = field(default_factory=dict)
    fused_score: float = 0.0
    n_experts_agreeing: int = 0
    raw_times: list[float] = field(default_factory=list)


@dataclass
class FusionConfig:
    """Configuration for multi-expert fusion."""

    # Temporal tolerance for clustering peaks from different experts (seconds)
    cluster_tolerance_ms: float = 25.0

    # Minimum gap between output events (seconds)
    minimum_event_gap_ms: float = 50.0

    # Expert weights for score-level fusion (higher = more influence)
    expert_weights: dict[str, float] = field(default_factory=lambda: {
        "hfc": 0.25,
        "complex": 0.35,
        "flux": 0.25,
        "rms_diff": 0.15,
    })

    # Percentile normalization: use this percentile as the "ceiling"
    normalize_percentile: float = 95.0

    # Minimum fused score to emit a candidate
    min_fused_score: float = 0.05

    # Minimum number of agreeing experts to boost confidence
    min_experts_for_boost: int = 2

    @property
    def cluster_tolerance_s(self) -> float:
        return self.cluster_tolerance_ms / 1000.0

    @property
    def minimum_event_gap_s(self) -> float:
        return self.minimum_event_gap_ms / 1000.0


def normalize_expert(
    envelope: np.ndarray,
    percentile: float = 95.0,
) -> np.ndarray:
    """Robust percentile normalization.

    Maps the envelope to [0, 1] where the specified percentile maps to 1.0.
    This prevents a single loud moment from squashing all other values.
    """
    if len(envelope) == 0:
        return envelope

    ceiling = float(np.percentile(envelope, percentile))
    if ceiling < 1e-10:
        return np.zeros_like(envelope)

    normalized = envelope / ceiling
    return np.clip(normalized, 0.0, 1.0)


def extract_peaks(
    envelope: np.ndarray,
    sr: int,
    hop_length: int,
    delta: float = 0.07,
    min_distance_ms: float = 30.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract peak frames from an onset envelope.

    Uses librosa peak picking if available, otherwise a simple local maximum detector.

    Returns:
        (peak_frames, peak_values)
    """
    if len(envelope) < 3:
        return np.array([], dtype=int), np.array([], dtype=np.float64)

    try:
        import librosa
        from librosa.util import peak_pick

        min_distance_frames = max(1, int(min_distance_ms * sr / 1000.0 / hop_length))

        peaks = peak_pick(
            envelope,
            pre_max=3,
            post_max=1,
            pre_avg=3,
            post_avg=5,
            delta=delta,
            wait=min_distance_frames,
        )
        if len(peaks) == 0:
            return np.array([], dtype=int), np.array([], dtype=np.float64)
        return peaks, envelope[peaks]

    except ImportError:
        return _simple_peaks(envelope, delta, min_distance_ms, sr, hop_length)


def _simple_peaks(
    envelope: np.ndarray,
    delta: float,
    min_distance_ms: float,
    sr: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Simple local-maximum peak detection fallback."""
    threshold = np.mean(envelope) + delta * np.std(envelope)
    min_dist = max(1, int(min_distance_ms * sr / 1000.0 / hop_length))

    peaks = []
    last_peak = -min_dist

    for i in range(1, len(envelope) - 1):
        if (
            envelope[i] > threshold
            and envelope[i] >= envelope[i - 1]
            and envelope[i] >= envelope[i + 1]
            and i - last_peak >= min_dist
        ):
            peaks.append(i)
            last_peak = i

    if not peaks:
        return np.array([], dtype=int), np.array([], dtype=np.float64)

    peaks_arr = np.array(peaks, dtype=int)
    return peaks_arr, envelope[peaks_arr]


def cluster_peaks(
    all_peaks: dict[str, tuple[np.ndarray, np.ndarray]],
    sr: int,
    hop_length: int,
    tolerance_s: float,
) -> list[OnsetCandidate]:
    """Cluster peaks from multiple experts within temporal tolerance.

    Args:
        all_peaks: Dict mapping expert name to (peak_frames, peak_values).
        sr: Sample rate.
        hop_length: STFT hop length.
        tolerance_s: Temporal tolerance for clustering (seconds).

    Returns:
        List of OnsetCandidate with fused scores.
    """
    # Collect all peak times across experts
    all_peak_info: list[tuple[float, str, float]] = []  # (time, expert_name, value)
    for expert_name, (frames, values) in all_peaks.items():
        for frame, value in zip(frames, values):
            time_s = frame * hop_length / sr
            all_peak_info.append((time_s, expert_name, float(value)))

    if not all_peak_info:
        return []

    # Sort by time
    all_peak_info.sort(key=lambda x: x[0])

    # Cluster: group peaks within tolerance
    candidates: list[OnsetCandidate] = []
    current_cluster: list[tuple[float, str, float]] = [all_peak_info[0]]

    for peak_time, expert_name, value in all_peak_info[1:]:
        # Check if this peak belongs to the current cluster
        cluster_center = np.mean([p[0] for p in current_cluster])
        if peak_time - cluster_center <= tolerance_s:
            # Avoid duplicate expert in same cluster
            existing_experts = {p[1] for p in current_cluster}
            if expert_name not in existing_experts:
                current_cluster.append((peak_time, expert_name, value))
        else:
            # Finalize current cluster and start new one
            candidates.append(_finalize_cluster(current_cluster))
            current_cluster = [(peak_time, expert_name, value)]

    # Finalize last cluster
    candidates.append(_finalize_cluster(current_cluster))

    return candidates


def _finalize_cluster(cluster: list[tuple[float, str, float]]) -> OnsetCandidate:
    """Convert a temporal cluster into a single OnsetCandidate."""
    times = [p[0] for p in cluster]
    center_time = float(np.mean(times))
    # Use the earliest frame for the candidate
    frame = int(min(times) * 44100 / 512)  # approximate

    expert_scores = {}
    raw_times = []
    for time_s, expert_name, value in cluster:
        expert_scores[expert_name] = value
        raw_times.append(time_s)

    return OnsetCandidate(
        time=center_time,
        frame=frame,
        expert_scores=expert_scores,
        raw_times=raw_times,
    )


def fuse_candidates(
    candidates: list[OnsetCandidate],
    config: FusionConfig | None = None,
) -> list[OnsetCandidate]:
    """Apply weighted score fusion and confidence calculation to candidates.

    Args:
        candidates: Temporally clustered candidates.
        config: Fusion configuration.

    Returns:
        Candidates with fused scores and confidence.
    """
    if config is None:
        config = FusionConfig()

    weights = config.expert_weights
    total_weight = sum(weights.values()) or 1.0

    for candidate in candidates:
        # Weighted sum of expert scores
        weighted_sum = 0.0
        for expert_name, score in candidate.expert_scores.items():
            w = weights.get(expert_name, 0.0)
            weighted_sum += w * score

        candidate.fused_score = weighted_sum / total_weight
        candidate.n_experts_agreeing = len(candidate.expert_scores)

        # Boost confidence when multiple experts agree
        if candidate.n_experts_agreeing >= config.min_experts_for_boost:
            agreement_boost = 0.1 * (candidate.n_experts_agreeing - 1)
            candidate.fused_score = min(1.0, candidate.fused_score + agreement_boost)

    return candidates


def apply_minimum_gap(
    candidates: list[OnsetCandidate],
    minimum_gap_s: float,
) -> list[OnsetCandidate]:
    """Remove candidates that are too close together.

    Keeps the candidate with the higher fused score.
    """
    if not candidates:
        return []

    candidates.sort(key=lambda c: c.time)
    result: list[OnsetCandidate] = [candidates[0]]

    for candidate in candidates[1:]:
        last = result[-1]
        gap = candidate.time - last.time
        if gap >= minimum_gap_s:
            result.append(candidate)
        elif candidate.fused_score > last.fused_score:
            result[-1] = candidate

    return result


def multi_expert_fusion(
    experts: dict[str, ExpertOutput],
    config: FusionConfig | None = None,
    delta: float = 0.07,
) -> list[OnsetCandidate]:
    """Full multi-expert onset fusion pipeline.

    Args:
        experts: Dict mapping expert name to ExpertOutput.
        config: Fusion configuration.
        delta: Peak detection delta threshold.

    Returns:
        List of fused OnsetCandidate events.
    """
    if config is None:
        config = FusionConfig()

    sr = list(experts.values())[0].sample_rate
    hop = list(experts.values())[0].hop_length

    # Step 1: Normalize each expert
    normalized: dict[str, np.ndarray] = {}
    for name, expert in experts.items():
        normalized[name] = normalize_expert(
            expert.onset_envelope, percentile=config.normalize_percentile
        )

    # Step 2: Extract peaks per expert
    all_peaks: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, norm_env in normalized.items():
        peaks, values = extract_peaks(norm_env, sr, hop, delta=delta)
        if len(peaks) > 0:
            all_peaks[name] = (peaks, values)

    if not all_peaks:
        return []

    # Step 3: Temporal clustering
    candidates = cluster_peaks(
        all_peaks, sr, hop, config.cluster_tolerance_s
    )

    # Step 4: Score fusion
    candidates = fuse_candidates(candidates, config)

    # Step 5: Filter by minimum score
    candidates = [c for c in candidates if c.fused_score >= config.min_fused_score]

    # Step 6: Minimum gap enforcement
    candidates = apply_minimum_gap(candidates, config.minimum_event_gap_s)

    logger.info(
        "Multi-expert fusion: %d experts -> %d peaks -> %d clusters -> %d candidates",
        len(experts),
        sum(len(v[0]) for v in all_peaks.values()),
        len(candidates),
        len(candidates),
    )

    return candidates
