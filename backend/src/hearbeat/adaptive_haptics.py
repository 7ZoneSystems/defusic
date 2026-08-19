"""Adaptive Haptic Scaling — loudness-driven dynamic haptic compensation.

Uses ITU-R BS.1770-style loudness measurement (K-weighted, gated) to adapt
haptic intensity and duration to each song's local dynamics.

Quiet sections get slightly stronger haptics; loud sections get slightly
less overbearing haptics, while preserving the event hierarchy:
    beat < hihat < snare < kick/bass

References:
- ITU-R BS.1770-5: https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/en
- EBU R 128 loudness: https://tech.ebu.ch/loudness
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as scipy_signal

from hearbeat.config import HOP_LENGTH, STFT_N_FFT
from hearbeat.haptic_config import HapticEventConfig
from hearbeat.haptic_mapper import HapticEvent

logger = logging.getLogger(__name__)


# ============================================================
# K-weighting filter (ITU-R BS.1770)
# ============================================================

# Two cascaded biquad filters for K-weighting:
#   Stage 1: High-shelf filter (+4 dB at 1500 Hz)
#   Stage 2: High-pass filter (RLB weighting)
# Coefficients for 44100 Hz sample rate, per ITU-R BS.1770-5

_K_WEIGHTING_STAGE1_COEFFS_44100 = {
    "b": [1.53512485958697, -2.69169618940638, 1.19839281085285],
    "a": [1.0, -1.69065929318241, 0.73248077421585],
}

_K_WEIGHTING_STAGE2_COEFFS_44100 = {
    "b": [1.0, -2.0, 1.0],
    "a": [1.0, -1.99004745483398, 0.99007225036621],
}


def _apply_k_weighting(audio: np.ndarray, sr: int) -> np.ndarray:
    """Apply ITU-R BS.1770 K-weighting filter.

    Uses cascaded biquad filters for the high-shelf and high-pass stages.
    If sr != 44100, recomputes coefficients via bilinear transform.
    """
    if sr == 44100:
        b1 = _K_WEIGHTING_STAGE1_COEFFS_44100["b"]
        a1 = _K_WEIGHTING_STAGE1_COEFFS_44100["a"]
        b2 = _K_WEIGHTING_STAGE2_COEFFS_44100["b"]
        a2 = _K_WEIGHTING_STAGE2_COEFFS_44100["a"]
    else:
        b1, a1 = _design_k_weighting_stage1(sr)
        b2, a2 = _design_k_weighting_stage2(sr)

    # Stage 1: high-shelf
    filtered = scipy_signal.lfilter(b1, a1, audio)
    # Stage 2: high-pass (RLB)
    filtered = scipy_signal.lfilter(b2, a2, filtered)
    return filtered


def _design_k_weighting_stage1(sr: int) -> tuple[list[float], list[float]]:
    """Design K-weighting stage 1 (high-shelf) for arbitrary sample rate.

    Analog prototype: +4 dB shelf at 1500 Hz.
    """
    # Pre-warped frequency
    f0 = 1500.0
    gain_db = 4.0
    Q = 0.7071  # Butterworth-like

    w0 = 2 * math.pi * f0 / sr
    A = 10 ** (gain_db / 40)
    alpha = math.sin(w0) / (2 * Q)

    b0 = A * ((A + 1) + (A - 1) * math.cos(w0) + 2 * math.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * math.cos(w0))
    b2 = A * ((A + 1) + (A - 1) * math.cos(w0) - 2 * math.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * math.cos(w0) + 2 * math.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * math.cos(w0))
    a2 = (A + 1) - (A - 1) * math.cos(w0) - 2 * math.sqrt(A) * alpha

    return [b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0]


def _design_k_weighting_stage2(sr: int) -> tuple[list[float], list[float]]:
    """Design K-weighting stage 2 (high-pass) for arbitrary sample rate.

    Analog prototype: 2nd-order Butterworth high-pass at ~38 Hz.
    """
    f0 = 38.0
    w0 = 2 * math.pi * f0 / sr
    alpha = math.sin(w0) / (2 * 0.7071)

    b0 = (1 + math.cos(w0)) / 2
    b1 = -(1 + math.cos(w0))
    b2 = (1 + math.cos(w0)) / 2
    a0 = 1 + alpha
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha

    return [b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0]


# ============================================================
# Loudness measurement (ITU-R BS.1770-style)
# ============================================================

@dataclass
class LoudnessProfile:
    """Complete loudness analysis of a track.

    All values follow ITU-R BS.1770 / EBU R 128 conventions.
    Units: LUFS (Loudness Units relative to Full Scale),
    also known as LKFS.
    """

    integrated_lufs: float = -70.0
    true_peak_dbtp: float = -70.0

    # Short-term statistics (3-second windows)
    short_term_p10: float = -70.0
    short_term_p50: float = -70.0
    short_term_p90: float = -70.0

    # Momentary (400ms) — kept for safety limiting
    momentary_max: float = -70.0

    # Time-series (downsampled for visualization)
    short_term_curve: list[dict] = field(default_factory=list)

    # Gating threshold (for reference)
    absolute_gate_lufs: float = -70.0
    relative_gate_lufs: float = -70.0


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive haptic scaling.

    All parameters are engineering starting values.
    """

    # Loudness windows
    short_term_window_s: float = 3.0
    momentary_window_s: float = 0.4

    # Percentiles for robust statistics
    percentile_low: float = 10.0
    percentile_mid: float = 50.0
    percentile_high: float = 90.0

    # Adaptive gain bounds
    min_adaptive_gain: float = 0.75
    neutral_adaptive_gain: float = 1.00
    max_adaptive_gain: float = 1.35

    # Duration gain bounds
    min_duration_gain: float = 0.85
    max_duration_gain: float = 1.20

    # Attack/release smoothing (seconds)
    gain_attack: float = 0.75
    gain_release: float = 2.0

    # Dead-band: small LUFS range around median where gain = 1.0
    loudness_deadband_lu: float = 1.5

    # True-peak safety
    true_peak_safety_margin_db: float = 1.0
    true_peak_attack_s: float = 0.05
    true_peak_release_s: float = 2.0

    # Silence gate: short-term LUFS below this is considered silence
    silence_gate_lufs: float = -70.0

    # Event duration safety bounds (ms) per event type
    # Bounds accommodate base durations: beat=65, hihat=144, kick=200, snare=167,
    # bass=200, subbass=170. Allow conservative stretch around base values.
    duration_bounds_ms: dict[str, tuple[int, int]] = field(default_factory=lambda: {
        "beat": (35, 100),
        "hihat": (80, 170),
        "snare": (110, 190),
        "kick": (150, 220),
        "bass": (150, 220),
        "subbass": (130, 200),
        "bass_beat": (100, 190),
        "bass_offbeat": (70, 140),
        "bass_accent": (130, 210),
        "bass_activity": (140, 220),
        "subbass_activity": (120, 190),
        "drum_onset": (100, 190),
        "cymbal": (60, 130),
        "percussion": (70, 150),
    })

    # Per-event intensity caps for background/activity layers.
    # These cap the final intensity AFTER adaptive scaling,
    # preventing low-strength activity from being boosted to full strength.
    activity_intensity_caps: dict[str, float] = field(default_factory=lambda: {
        "bass_activity": 0.35,
        "subbass_activity": 0.60,
    })


# ============================================================
# Loudness analysis
# ============================================================

def measure_loudness(
    audio: np.ndarray,
    sr: int,
    config: AdaptiveConfig | None = None,
) -> LoudnessProfile:
    """Compute full loudness profile using ITU-R BS.1770-style measurement.

    Args:
        audio: Mono float audio waveform.
        sr: Sample rate.
        config: Adaptive configuration.

    Returns:
        LoudnessProfile with integrated, short-term, momentary, and true peak.
    """
    cfg = config or AdaptiveConfig()
    profile = LoudnessProfile()

    if len(audio) < sr:
        return profile

    # Apply K-weighting
    k_weighted = _apply_k_weighting(audio, sr)

    # --- Integrated loudness ---
    integrated, gated_samples = _compute_integrated_loudness(k_weighted, sr)
    profile.integrated_lufs = integrated

    # --- True peak (oversampled) ---
    profile.true_peak_dbtp = _compute_true_peak(audio, sr)

    # --- Short-term loudness (3s windows) ---
    st_window = int(cfg.short_term_window_s * sr)
    st_hop = st_window  # Non-overlapping for EBU compliance
    st_values = _compute_block_loudness(k_weighted, st_window, st_hop)

    # Gate out silence/low-level windows
    valid_st = st_values[st_values > cfg.silence_gate_lufs]

    if len(valid_st) > 0:
        profile.short_term_p10 = float(np.percentile(valid_st, cfg.percentile_low))
        profile.short_term_p50 = float(np.percentile(valid_st, cfg.percentile_mid))
        profile.short_term_p90 = float(np.percentile(valid_st, cfg.percentile_high))
    else:
        # Fallback: use integrated as reference
        profile.short_term_p10 = integrated
        profile.short_term_p50 = integrated
        profile.short_term_p90 = integrated

    # --- Momentary loudness (400ms windows) ---
    m_window = int(cfg.momentary_window_s * sr)
    m_hop = m_window
    m_values = _compute_block_loudness(k_weighted, m_window, m_hop)
    valid_m = m_values[m_values > cfg.silence_gate_lufs]
    profile.momentary_max = float(np.max(valid_m)) if len(valid_m) > 0 else integrated

    # --- Short-term curve (downsampled for visualization) ---
    profile.short_term_curve = _build_loudness_curve(
        st_values, st_hop, sr, len(audio), cfg
    )

    # --- Gating thresholds ---
    profile.absolute_gate_lufs = -70.0  # ITU absolute gate
    if len(gated_samples) > 0:
        profile.relative_gate_lufs = float(
            np.mean(gated_samples) - 10.0
        )

    logger.info(
        "Loudness: integrated=%.1f LUFS, true_peak=%.1f dBTP, "
        "ST p10=%.1f p50=%.1f p90=%.1f",
        integrated, profile.true_peak_dbtp,
        profile.short_term_p10, profile.short_term_p50, profile.short_term_p90,
    )

    return profile


def _compute_integrated_loudness(
    k_weighted: np.ndarray, sr: int
) -> tuple[float, np.ndarray]:
    """Compute integrated loudness per ITU-R BS.1770.

    Uses 400ms gating blocks with relative gate.
    Returns (integrated_lufs, gated_block_energies).
    """
    block_size = int(0.4 * sr)  # 400ms
    hop_size = block_size  # Non-overlapping

    n_blocks = max(1, (len(k_weighted) - block_size) // hop_size + 1)
    block_energies = np.zeros(n_blocks)

    for i in range(n_blocks):
        start = i * hop_size
        end = start + block_size
        block = k_weighted[start:end]
        block_energies[i] = np.mean(block**2)

    # Absolute gate: -70 LUFS
    absolute_gate = 10 ** ((-70 + 0.691) / 10)
    above_absolute = block_energies[block_energies > absolute_gate]

    if len(above_absolute) == 0:
        return -70.0, block_energies

    # Relative gate: -10 dB below ungated mean
    ungated_mean = np.mean(above_absolute)
    relative_gate = ungated_mean * 10 ** (-10 / 10)

    gated = above_absolute[above_absolute > relative_gate]

    if len(gated) == 0:
        return -70.0, block_energies

    # Integrated loudness
    mean_energy = np.mean(gated)
    integrated = -0.691 + 10 * np.log10(max(mean_energy, 1e-30))

    return float(integrated), gated


def _compute_true_peak(audio: np.ndarray, sr: int) -> float:
    """Compute true peak in dBTP using 4x oversampling.

    Per ITU-R BS.1770, true peak is measured after 4x oversampling.
    """
    if len(audio) == 0:
        return -70.0

    # 4x oversampling
    upsampled = scipy_signal.resample_poly(audio, 4, 1)
    peak = float(np.max(np.abs(upsampled)))

    if peak < 1e-30:
        return -70.0

    return float(20 * np.log10(peak))


def _compute_block_loudness(
    k_weighted: np.ndarray,
    block_size: int,
    hop_size: int,
) -> np.ndarray:
    """Compute mean-square loudness per block in LUFS."""
    n_blocks = max(0, (len(k_weighted) - block_size) // hop_size + 1)
    if n_blocks == 0:
        return np.array([], dtype=np.float64)

    loudness = np.zeros(n_blocks, dtype=np.float64)
    for i in range(n_blocks):
        start = i * hop_size
        end = start + block_size
        block = k_weighted[start:end]
        mean_sq = np.mean(block**2)
        loudness[i] = -0.691 + 10 * np.log10(max(mean_sq, 1e-30))

    return loudness


def _build_loudness_curve(
    st_values: np.ndarray,
    st_hop: int,
    sr: int,
    total_samples: int,
    cfg: AdaptiveConfig,
) -> list[dict]:
    """Build downsampled loudness curve for visualization.

    Downsample to ~100 points max for the UI.
    """
    if len(st_values) == 0:
        return []

    target_points = 100
    step = max(1, len(st_values) // target_points)

    curve = []
    for i in range(0, len(st_values), step):
        time_s = (i * st_hop) / sr
        curve.append({
            "time": round(time_s, 3),
            "short_term_lufs": round(float(st_values[i]), 1),
        })

    return curve


# ============================================================
# Adaptive gain controller
# ============================================================

def compute_adaptive_gain(
    local_lufs: float,
    profile: LoudnessProfile,
    config: AdaptiveConfig | None = None,
) -> tuple[float, float]:
    """Compute adaptive intensity and duration gain for a local loudness value.

    Uses nonlinear inverse compensation:
        quiet section -> gain > 1.0
        loud section -> gain < 1.0

    Returns (intensity_gain, duration_gain) both bounded.
    """
    cfg = config or AdaptiveConfig()

    # Gate: if below silence threshold, return neutral
    if local_lufs < cfg.silence_gate_lufs:
        return cfg.neutral_adaptive_gain, cfg.neutral_adaptive_gain

    p10 = profile.short_term_p10
    p50 = profile.short_term_p50
    p90 = profile.short_term_p90

    # Avoid division by zero
    if abs(p90 - p10) < 0.1:
        return cfg.neutral_adaptive_gain, cfg.neutral_adaptive_gain

    # Normalized loudness position: 0 = quietest, 1 = loudest
    loudness_position = (local_lufs - p10) / (p90 - p10)
    loudness_position = float(np.clip(loudness_position, 0.0, 1.0))

    # Dead-band: around median, return neutral
    half_deadband = cfg.loudness_deadband_lu / (p90 - p10) if (p90 - p10) > 0 else 0.1
    if abs(loudness_position - 0.5) < half_deadband:
        return cfg.neutral_adaptive_gain, cfg.neutral_adaptive_gain

    # Nonlinear inverse compensation (logistic-like curve)
    # Centered at 0.5, inverted so quiet gets higher gain
    # Using a smooth sigmoid-like mapping
    x = (loudness_position - 0.5) * 2  # Map to [-1, 1]

    # Smooth nonlinear curve: tanh-like with configurable steepness
    intensity_response = -math.tanh(x * 1.5)  # -1 to 1, inverted
    duration_response = -math.tanh(x * 1.2)   # Slightly less aggressive

    # Map to gain range
    intensity_gain = cfg.neutral_adaptive_gain + intensity_response * (
        cfg.max_adaptive_gain - cfg.neutral_adaptive_gain
        if intensity_response > 0
        else cfg.neutral_adaptive_gain - cfg.min_adaptive_gain
    )

    duration_gain = cfg.neutral_adaptive_gain + duration_response * (
        cfg.max_duration_gain - cfg.neutral_adaptive_gain
        if duration_response > 0
        else cfg.neutral_adaptive_gain - cfg.min_duration_gain
    )

    # Clamp
    intensity_gain = float(np.clip(intensity_gain, cfg.min_adaptive_gain, cfg.max_adaptive_gain))
    duration_gain = float(np.clip(duration_gain, cfg.min_duration_gain, cfg.max_duration_gain))

    return intensity_gain, duration_gain


def smooth_gain_curve(
    raw_gains: np.ndarray,
    sr: int,
    config: AdaptiveConfig | None = None,
) -> np.ndarray:
    """Apply attack/release smoothing to a gain sequence.

    Uses separate time constants for increasing (attack) and
    decreasing (release) gain changes to prevent pumping.

    Args:
        raw_gains: 1D array of per-frame raw gains.
        sr: Frame rate (frames per second, e.g. sr/hop_length).
        config: Adaptive configuration.

    Returns:
        Smoothed gain array of same length.
    """
    cfg = config or AdaptiveConfig()

    if len(raw_gains) == 0:
        return raw_gains

    attack_coeff = math.exp(-1.0 / (cfg.gain_attack * sr)) if cfg.gain_attack > 0 else 0.0
    release_coeff = math.exp(-1.0 / (cfg.gain_release * sr)) if cfg.gain_release > 0 else 0.0

    smoothed = np.zeros_like(raw_gains, dtype=np.float64)
    smoothed[0] = raw_gains[0]

    for i in range(1, len(raw_gains)):
        diff = raw_gains[i] - smoothed[i - 1]
        if diff > 0:
            # Gain increasing -> use attack coefficient
            coeff = attack_coeff
        else:
            # Gain decreasing -> use release coefficient
            coeff = release_coeff

        smoothed[i] = smoothed[i - 1] + (1.0 - coeff) * diff

    return smoothed


# ============================================================
# Haptic event adaptation
# ============================================================

def adapt_event(
    event: HapticEvent,
    local_lufs: float,
    intensity_gain: float,
    duration_gain: float,
    config: AdaptiveConfig | None = None,
) -> HapticEvent:
    """Apply adaptive scaling to a single haptic event.

    Modifies intensity and duration while preserving event hierarchy.
    Returns a new HapticEvent with adapted values.
    """
    cfg = config or AdaptiveConfig()

    # Apply intensity gain
    adapted_intensity = event.intensity * intensity_gain
    adapted_intensity = float(np.clip(adapted_intensity, 0.0, 1.0))

    # Apply per-event-type activity cap (prevents background layers from being boosted)
    cap = cfg.activity_intensity_caps.get(event.type)
    if cap is not None:
        adapted_intensity = min(adapted_intensity, cap)

    # Apply duration gain with per-type bounds
    raw_duration = event.duration_ms * duration_gain
    bounds = cfg.duration_bounds_ms.get(event.type, (20, 250))
    adapted_duration = int(np.clip(round(raw_duration), bounds[0], bounds[1]))

    return HapticEvent(
        time=event.time,
        type=event.type,
        intensity=adapted_intensity,
        duration_ms=adapted_duration,
        is_anticipation=event.is_anticipation,
    )


def adapt_timeline(
    events: list[HapticEvent],
    profile: LoudnessProfile,
    config: AdaptiveConfig | None = None,
    enabled: bool = True,
    gain_strength: float = 1.0,
) -> tuple[list[HapticEvent], list[dict]]:
    """Apply adaptive loudness scaling to an entire haptic timeline.

    Args:
        events: Original haptic events (sorted by time).
        profile: Loudness analysis profile.
        config: Adaptive configuration.
        enabled: Whether adaptive scaling is active.
        gain_strength: Manual strength multiplier (0.0-1.0) for A/B testing.

    Returns:
        (adapted_events, debug_info) where debug_info contains per-event
        diagnostic data.
    """
    cfg = config or AdaptiveConfig()

    if not enabled or not events:
        return events, []

    # --- Compute per-frame gain curve from short-term loudness ---
    st_curve = profile.short_term_curve
    if not st_curve:
        return events, []

    # Build time-indexed loudness lookup
    st_times = np.array([p["time"] for p in st_curve])
    st_lufs = np.array([p["short_term_lufs"] for p in st_curve])

    # Compute raw gains for each ST frame
    raw_intensity_gains = np.zeros(len(st_lufs))
    raw_duration_gains = np.zeros(len(st_lufs))

    for i, lufs in enumerate(st_lufs):
        ig, dg = compute_adaptive_gain(lufs, profile, cfg)
        raw_intensity_gains[i] = ig
        raw_duration_gains[i] = dg

    # Smooth gains using a reference frame rate so that the attack/release
    # time constants (0.75s / 2.0s) produce the intended smoothing behavior.
    # The ST frame rate (1/3 fps) is too low for the time constants to work
    # as designed. Using 10 fps gives correct exponential smoothing.
    smooth_frame_rate = 10.0
    smoothed_intensity = smooth_gain_curve(raw_intensity_gains, smooth_frame_rate, cfg)
    smoothed_duration = smooth_gain_curve(raw_duration_gains, smooth_frame_rate, cfg)

    # Apply manual strength slider
    if gain_strength < 1.0:
        # Interpolate toward neutral
        smoothed_intensity = 1.0 + (smoothed_intensity - 1.0) * gain_strength
        smoothed_duration = 1.0 + (smoothed_duration - 1.0) * gain_strength

    # --- True-peak safety limiting with attack/release smoothing ---
    tp_limit = _compute_true_peak_limit(profile, cfg)
    if tp_limit < 1.0:
        # Apply smooth attack/release to prevent abrupt gain jumps
        tp_attack_coeff = math.exp(-1.0 / (cfg.true_peak_attack_s * smooth_frame_rate)) if cfg.true_peak_attack_s > 0 else 0.0
        tp_release_coeff = math.exp(-1.0 / (cfg.true_peak_release_s * smooth_frame_rate)) if cfg.true_peak_release_s > 0 else 0.0

        tp_caps = np.ones_like(smoothed_intensity)
        tp_caps[:] = tp_limit

        # Smooth the TP cap: fast attack (when TP is high, cap drops quickly)
        # slow release (when TP is low, cap recovers slowly)
        smoothed_tp = np.zeros_like(tp_caps)
        smoothed_tp[0] = tp_caps[0]
        for i in range(1, len(tp_caps)):
            diff = tp_caps[i] - smoothed_tp[i - 1]
            if diff < 0:
                coeff = tp_attack_coeff
            else:
                coeff = tp_release_coeff
            smoothed_tp[i] = smoothed_tp[i - 1] + (1.0 - coeff) * diff

        smoothed_intensity = np.minimum(smoothed_intensity, smoothed_tp)

    # --- Adapt each event ---
    adapted: list[HapticEvent] = []
    debug: list[dict] = []

    for event in events:
        # Find nearest ST frame
        frame_idx = int(np.searchsorted(st_times, event.time)) - 1
        frame_idx = max(0, min(frame_idx, len(smoothed_intensity) - 1))

        ig = float(smoothed_intensity[frame_idx])
        dg = float(smoothed_duration[frame_idx])

        # Look up local LUFS
        local_lufs = float(st_lufs[frame_idx]) if frame_idx < len(st_lufs) else profile.integrated_lufs

        new_event = adapt_event(event, local_lufs, ig, dg, cfg)
        adapted.append(new_event)

        debug.append({
            "time": round(event.time, 6),
            "type": event.type,
            "base_intensity": round(event.intensity, 4),
            "adaptive_gain": round(ig, 4),
            "final_intensity": round(new_event.intensity, 4),
            "base_duration_ms": event.duration_ms,
            "duration_gain": round(dg, 4),
            "final_duration_ms": new_event.duration_ms,
            "local_short_term_lufs": round(local_lufs, 1),
        })

    logger.info(
        "Adaptive scaling applied: %d events, gain range [%.2f, %.2f]",
        len(adapted),
        float(np.min(smoothed_intensity)),
        float(np.max(smoothed_intensity)),
    )

    return adapted, debug


def _compute_true_peak_limit(
    profile: LoudnessProfile,
    cfg: AdaptiveConfig,
) -> float:
    """Compute momentary gain cap from true peak.

    If true peak approaches 0 dBTP, apply a safety cap to prevent
    excessive haptic output. Does NOT permanently reduce gain.
    """
    tp = profile.true_peak_dbtp
    threshold = -cfg.true_peak_safety_margin_db

    if tp > threshold:
        # Scale down proportionally
        excess = tp - threshold
        reduction = max(0.5, 1.0 - excess * 0.1)
        return float(np.clip(reduction, cfg.min_adaptive_gain, 1.0))

    return 1.0
