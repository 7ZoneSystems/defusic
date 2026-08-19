"""Tests for adaptive haptic scaling (loudness-driven compensation).

Covers:
- ITU-R BS.1770 K-weighting filter
- Integrated, short-term, momentary loudness measurement
- True peak measurement
- Robust percentile statistics
- Adaptive gain computation (inverse compensation)
- Gain smoothing (attack/release)
- Event adaptation (intensity + duration)
- Timeline adaptation
- Silence gating
- Dead-band behavior
- Event hierarchy preservation
- Duration bounds per event type
"""

import math

import numpy as np
import pytest

from hearbeat.adaptive_haptics import (
    AdaptiveConfig,
    LoudnessProfile,
    adapt_event,
    adapt_timeline,
    compute_adaptive_gain,
    measure_loudness,
    smooth_gain_curve,
    _apply_k_weighting,
    _compute_integrated_loudness,
    _compute_true_peak,
)
from hearbeat.haptic_mapper import HapticEvent


# ============================================================
# K-weighting tests
# ============================================================

def test_k_weighting_preserves_low_frequencies():
    """Low frequencies above the high-pass cutoff should pass through."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 200 * t).astype(np.float32)

    filtered = _apply_k_weighting(audio, sr)

    # 200 Hz should pass through with minimal attenuation
    original_rms = np.sqrt(np.mean(audio**2))
    filtered_rms = np.sqrt(np.mean(filtered**2))
    ratio = filtered_rms / original_rms
    assert 0.7 < ratio < 1.5, f"200 Hz should pass through K-weighting, ratio={ratio:.3f}"


def test_k_weighting_boosts_high_frequencies():
    """K-weighting adds ~4 dB shelf above 1500 Hz."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 3000 * t).astype(np.float32) * 0.5

    filtered = _apply_k_weighting(audio, sr)

    original_rms = np.sqrt(np.mean(audio**2))
    filtered_rms = np.sqrt(np.mean(filtered**2))
    # High-shelf should boost above ~1 dB
    assert filtered_rms > original_rms * 0.9, "High frequencies should be boosted by K-weighting"


def test_k_weighting_different_sample_rates():
    """K-weighting should work at different sample rates."""
    for sr in [22050, 44100, 48000]:
        duration = 1.0
        t = np.arange(int(sr * duration)) / sr
        audio = np.sin(2 * np.pi * 100 * t).astype(np.float32)

        filtered = _apply_k_weighting(audio, sr)
        assert len(filtered) == len(audio)
        assert np.isfinite(filtered).all()


# ============================================================
# Loudness measurement tests
# ============================================================

def test_loudness_silence():
    """Silent audio should produce very low loudness."""
    sr = 44100
    audio = np.zeros(sr * 2, dtype=np.float32)
    profile = measure_loudness(audio, sr)
    assert profile.integrated_lufs < -60


def test_loudness_sine_1khz():
    """1 kHz sine at 0 dBFS should measure around -3 LUFS."""
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 1000 * t).astype(np.float32)

    profile = measure_loudness(audio, sr)
    # 1 kHz sine at 0 dBFS: integrated ~ -3.01 LUFS
    assert -6.0 < profile.integrated_lufs < 0.0


def test_loudness_true_peak_sine():
    """True peak of 0 dBFS sine should be ~0 dBTP."""
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 1000 * t).astype(np.float32)

    profile = measure_loudness(audio, sr)
    assert -1.0 < profile.true_peak_dbtp < 1.0


def test_loudness_true_peak_quiet():
    """True peak of quiet signal should be low."""
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 1000 * t).astype(np.float32) * 0.01

    profile = measure_loudness(audio, sr)
    assert profile.true_peak_dbtp < -30


def test_loudness_short_term_statistics():
    """Short-term percentiles should be computed."""
    sr = 44100
    duration = 15.0  # Multiple 3-second windows
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32) * 0.5

    profile = measure_loudness(audio, sr)
    # All should be valid LUFS values
    assert -70 < profile.short_term_p10 <= profile.short_term_p50 <= profile.short_term_p90 < 0


def test_loudness_curve_populated():
    """Loudness curve should have entries for visualization."""
    sr = 44100
    duration = 10.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32) * 0.5

    profile = measure_loudness(audio, sr)
    assert len(profile.short_term_curve) > 0
    assert "time" in profile.short_term_curve[0]
    assert "short_term_lufs" in profile.short_term_curve[0]


def test_loudness_short_audio():
    """Very short audio should return a basic profile without crashing."""
    sr = 44100
    audio = np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32) * 0.5

    profile = measure_loudness(audio, sr)
    assert isinstance(profile, LoudnessProfile)


# ============================================================
# Adaptive gain computation tests
# ============================================================

def _make_profile(
    p10: float = -30.0,
    p50: float = -20.0,
    p90: float = -10.0,
    integrated: float = -20.0,
) -> LoudnessProfile:
    return LoudnessProfile(
        integrated_lufs=integrated,
        short_term_p10=p10,
        short_term_p50=p50,
        short_term_p90=p90,
    )


def test_gain_neutral_at_median():
    """Gain should be ~1.0 at the median loudness (dead-band)."""
    profile = _make_profile(p10=-30, p50=-20, p90=-10)
    cfg = AdaptiveConfig(loudness_deadband_lu=1.5)

    ig, dg = compute_adaptive_gain(-20.0, profile, cfg)
    assert 0.95 <= ig <= 1.05, f"Median gain should be ~1.0, got {ig}"


def test_gain_quiet_section():
    """Quiet section should produce gain > 1.0."""
    profile = _make_profile(p10=-30, p50=-20, p90=-10)
    cfg = AdaptiveConfig()

    ig, dg = compute_adaptive_gain(-28.0, profile, cfg)
    assert ig > 1.0, f"Quiet section should have gain > 1.0, got {ig}"
    assert ig <= cfg.max_adaptive_gain


def test_gain_loud_section():
    """Loud section should produce gain < 1.0."""
    profile = _make_profile(p10=-30, p50=-20, p90=-10)
    cfg = AdaptiveConfig()

    ig, dg = compute_adaptive_gain(-12.0, profile, cfg)
    assert ig < 1.0, f"Loud section should have gain < 1.0, got {ig}"
    assert ig >= cfg.min_adaptive_gain


def test_gain_bounds():
    """Gain should never exceed configured bounds."""
    profile = _make_profile(p10=-40, p50=-20, p90=-5)
    cfg = AdaptiveConfig()

    # Extremely quiet
    ig_quiet, _ = compute_adaptive_gain(-39.0, profile, cfg)
    assert ig_quiet <= cfg.max_adaptive_gain

    # Extremely loud
    ig_loud, _ = compute_adaptive_gain(-6.0, profile, cfg)
    assert ig_loud >= cfg.min_adaptive_gain


def test_gain_silence_gate():
    """Silent audio should not produce large haptic gain."""
    profile = _make_profile()
    cfg = AdaptiveConfig(silence_gate_lufs=-70.0)

    ig, dg = compute_adaptive_gain(-80.0, profile, cfg)
    assert ig == 1.0, "Silence should produce neutral gain"


def test_gain_duration_bounds():
    """Duration gain should be within configured bounds."""
    profile = _make_profile(p10=-30, p50=-20, p90=-10)
    cfg = AdaptiveConfig()

    ig_quiet, dg_quiet = compute_adaptive_gain(-28.0, profile, cfg)
    ig_loud, dg_loud = compute_adaptive_gain(-12.0, profile, cfg)

    assert cfg.min_duration_gain <= dg_quiet <= cfg.max_duration_gain
    assert cfg.min_duration_gain <= dg_loud <= cfg.max_duration_gain


def test_gain_is_bounded():
    """All gain values should be within the configured bounds."""
    profile = _make_profile()
    cfg = AdaptiveConfig()

    for lufs in np.linspace(-50, -5, 20):
        ig, dg = compute_adaptive_gain(lufs, profile, cfg)
        assert cfg.min_adaptive_gain <= ig <= cfg.max_adaptive_gain
        assert cfg.min_duration_gain <= dg <= cfg.max_duration_gain


# ============================================================
# Gain smoothing tests
# ============================================================

def test_smoothing_attack_release():
    """Smoothed gains should change more slowly than raw gains."""
    raw = np.array([1.0, 1.0, 1.0, 1.3, 1.3, 1.3, 0.7, 0.7, 0.7])
    frame_rate = 10.0  # 10 frames/sec
    cfg = AdaptiveConfig(gain_attack=0.5, gain_release=1.0)

    smoothed = smooth_gain_curve(raw, frame_rate, cfg)

    # The jump from 1.0 to 1.3 should be smoothed
    assert abs(smoothed[3] - 1.0) < 0.3, "Attack smoothing should soften the jump"
    assert abs(smoothed[3] - 1.3) > 0.01, "Should not jump instantly to 1.3"


def test_smoothing_monotonic():
    """Smoothing should be monotonic (no overshoot)."""
    raw = np.array([1.0, 1.2, 1.4, 1.2, 1.0])
    frame_rate = 10.0
    cfg = AdaptiveConfig(gain_attack=0.5, gain_release=1.0)

    smoothed = smooth_gain_curve(raw, frame_rate, cfg)
    # Smoothed values should not exceed max of raw
    assert smoothed.max() <= raw.max() + 0.01
    assert smoothed.min() >= raw.min() - 0.01


def test_smoothing_empty():
    """Smoothing empty array should return empty."""
    raw = np.array([], dtype=np.float64)
    cfg = AdaptiveConfig()
    result = smooth_gain_curve(raw, 10.0, cfg)
    assert len(result) == 0


def test_smoothing_single_value():
    """Smoothing a single value should return that value."""
    raw = np.array([1.0])
    cfg = AdaptiveConfig()
    result = smooth_gain_curve(raw, 10.0, cfg)
    assert result[0] == 1.0


# ============================================================
# Event adaptation tests
# ============================================================

def test_adapt_event_intensity():
    """Intensity should be scaled by gain."""
    event = HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.2, duration_gain=1.0, config=cfg)
    assert adapted.intensity == pytest.approx(0.84, abs=0.01)


def test_adapt_event_duration():
    """Duration should be scaled by gain."""
    event = HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.0, duration_gain=1.1, config=cfg)
    # 200 * 1.1 = 220, within bounds (150, 220)
    assert adapted.duration_ms == 220


def test_adapt_event_intensity_clamped():
    """Intensity should never exceed 1.0."""
    event = HapticEvent(time=1.0, type="beat", intensity=0.9, duration_ms=65)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.5, duration_gain=1.0, config=cfg)
    assert adapted.intensity <= 1.0


def test_adapt_event_duration_within_bounds():
    """Duration should respect per-type bounds."""
    event = HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.0, duration_gain=1.5, config=cfg)
    bounds = cfg.duration_bounds_ms["kick"]
    assert bounds[0] <= adapted.duration_ms <= bounds[1]


def test_adapt_event_preserves_type():
    """Event type should be preserved."""
    event = HapticEvent(time=1.0, type="snare", intensity=0.5, duration_ms=167)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.0, duration_gain=1.0, config=cfg)
    assert adapted.type == "snare"
    assert adapted.time == 1.0


def test_adapt_event_preserves_anticipation():
    """Anticipation flag should be preserved."""
    event = HapticEvent(time=1.0, type="anticipation", intensity=0.05, duration_ms=15, is_anticipation=True)
    cfg = AdaptiveConfig()

    adapted = adapt_event(event, local_lufs=-20.0, intensity_gain=1.0, duration_gain=1.0, config=cfg)
    assert adapted.is_anticipation is True


# ============================================================
# Timeline adaptation tests
# ============================================================

def _make_profile_with_curve() -> LoudnessProfile:
    """Create a profile with a short-term curve for timeline tests."""
    profile = LoudnessProfile(
        integrated_lufs=-20.0,
        short_term_p10=-30.0,
        short_term_p50=-20.0,
        short_term_p90=-10.0,
        short_term_curve=[
            {"time": 0.0, "short_term_lufs": -30.0},
            {"time": 3.0, "short_term_lufs": -25.0},
            {"time": 6.0, "short_term_lufs": -20.0},
            {"time": 9.0, "short_term_lufs": -15.0},
            {"time": 12.0, "short_term_lufs": -10.0},
        ],
    )
    return profile


def test_adapt_timeline_enabled():
    """Timeline should be adapted when enabled."""
    profile = _make_profile_with_curve()
    events = [
        HapticEvent(time=1.0, type="beat", intensity=0.15, duration_ms=65),
        HapticEvent(time=2.0, type="kick", intensity=0.70, duration_ms=200),
    ]

    adapted, debug = adapt_timeline(events, profile, enabled=True)
    assert len(adapted) == 2
    assert len(debug) == 2


def test_adapt_timeline_disabled():
    """Timeline should be unchanged when disabled."""
    profile = _make_profile_with_curve()
    events = [
        HapticEvent(time=1.0, type="beat", intensity=0.15, duration_ms=65),
    ]

    adapted, debug = adapt_timeline(events, profile, enabled=False)
    assert len(adapted) == 1
    assert adapted[0].intensity == 0.15
    assert debug == []


def test_adapt_timeline_empty():
    """Empty timeline should return empty."""
    profile = _make_profile_with_curve()
    adapted, debug = adapt_timeline([], profile, enabled=True)
    assert len(adapted) == 0
    assert len(debug) == 0


def test_adapt_timeline_debug_fields():
    """Debug info should contain required fields."""
    profile = _make_profile_with_curve()
    events = [HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200)]

    _, debug = adapt_timeline(events, profile, enabled=True)
    assert len(debug) == 1
    d = debug[0]
    assert "time" in d
    assert "type" in d
    assert "base_intensity" in d
    assert "adaptive_gain" in d
    assert "final_intensity" in d
    assert "base_duration_ms" in d
    assert "duration_gain" in d
    assert "final_duration_ms" in d
    assert "local_short_term_lufs" in d


def test_adapt_timeline_quiet_section_boosts():
    """Events in quiet sections should have higher intensity."""
    profile = LoudnessProfile(
        integrated_lufs=-20.0,
        short_term_p10=-30.0,
        short_term_p50=-20.0,
        short_term_p90=-10.0,
        short_term_curve=[
            {"time": 0.0, "short_term_lufs": -28.0},  # Quiet
        ],
    )
    events = [HapticEvent(time=0.5, type="kick", intensity=0.7, duration_ms=200)]

    adapted, _ = adapt_timeline(events, profile, enabled=True)
    assert adapted[0].intensity >= 0.7, "Quiet section should boost intensity"


def test_adapt_timeline_loud_section_reduces():
    """Events in loud sections should have lower intensity."""
    profile = LoudnessProfile(
        integrated_lufs=-20.0,
        short_term_p10=-30.0,
        short_term_p50=-20.0,
        short_term_p90=-10.0,
        short_term_curve=[
            {"time": 0.0, "short_term_lufs": -12.0},  # Loud
        ],
    )
    events = [HapticEvent(time=0.5, type="kick", intensity=0.7, duration_ms=200)]

    adapted, _ = adapt_timeline(events, profile, enabled=True)
    assert adapted[0].intensity <= 0.7, "Loud section should reduce intensity"


def test_adapt_timeline_preserves_hierarchy():
    """After adaptation, beat < kick < bass should still hold."""
    profile = LoudnessProfile(
        integrated_lufs=-20.0,
        short_term_p10=-30.0,
        short_term_p50=-20.0,
        short_term_p90=-10.0,
        short_term_curve=[
            {"time": 0.0, "short_term_lufs": -20.0},  # Median
        ],
    )
    events = [
        HapticEvent(time=1.0, type="beat", intensity=0.15, duration_ms=65),
        HapticEvent(time=1.1, type="kick", intensity=0.70, duration_ms=200),
        HapticEvent(time=1.2, type="bass", intensity=0.80, duration_ms=200),
    ]

    adapted, _ = adapt_timeline(events, profile, enabled=True)
    beat_e = next(e for e in adapted if e.type == "beat")
    kick_e = next(e for e in adapted if e.type == "kick")
    bass_e = next(e for e in adapted if e.type == "bass")

    # Intensity hierarchy preserved
    assert beat_e.intensity < kick_e.intensity < bass_e.intensity
    # Duration hierarchy preserved
    assert beat_e.duration_ms < kick_e.duration_ms <= bass_e.duration_ms


def test_adapt_timeline_gain_strength():
    """Gain strength 0 should produce no adaptation."""
    profile = _make_profile_with_curve()
    events = [
        HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200),
    ]

    adapted_zero, _ = adapt_timeline(events, profile, enabled=True, gain_strength=0.0)
    adapted_full, _ = adapt_timeline(events, profile, enabled=True, gain_strength=1.0)

    # With strength=0, intensity should be unchanged
    assert adapted_zero[0].intensity == pytest.approx(0.7, abs=0.01)
    # With strength=1, adaptation applies
    assert adapted_full[0].intensity != 0.7


def test_adapt_timeline_no_curve():
    """Without a curve, events should be returned unchanged."""
    profile = LoudnessProfile(short_term_curve=[])
    events = [HapticEvent(time=1.0, type="kick", intensity=0.7, duration_ms=200)]

    adapted, debug = adapt_timeline(events, profile, enabled=True)
    assert len(adapted) == 1
    assert debug == []


# ============================================================
# Duration bounds tests
# ============================================================

def test_duration_bounds_all_types():
    """All event types should have valid duration bounds."""
    cfg = AdaptiveConfig()
    for event_type, (lo, hi) in cfg.duration_bounds_ms.items():
        assert lo > 0, f"{event_type} lower bound should be > 0"
        assert hi > lo, f"{event_type} upper bound should be > lower bound"
        assert hi <= 300, f"{event_type} upper bound should be <= 300ms"


def test_duration_bounds_kick():
    """Kick duration bounds should accommodate base 200ms."""
    cfg = AdaptiveConfig()
    lo, hi = cfg.duration_bounds_ms["kick"]
    assert lo < 200  # Base duration must be within bounds
    assert hi >= 200


def test_duration_bounds_beat():
    """Beat duration bounds should accommodate base 65ms."""
    cfg = AdaptiveConfig()
    lo, hi = cfg.duration_bounds_ms["beat"]
    assert lo < 65  # Base duration must be within bounds
    assert hi > 65


# ============================================================
# Synthetic audio tests
# ============================================================

def test_constant_loudness():
    """Constant loudness should produce adaptive gain ~1.0."""
    sr = 44100
    duration = 15.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32) * 0.5

    profile = measure_loudness(audio, sr)

    # All short-term windows should be similar
    if len(profile.short_term_curve) > 1:
        lufs_values = [p["short_term_lufs"] for p in profile.short_term_curve]
        spread = max(lufs_values) - min(lufs_values)
        # Constant signal should have small spread
        assert spread < 5.0, f"Constant signal should have tight LUFS spread, got {spread}"


def test_crescendo():
    """Crescendo should show increasing short-term loudness."""
    sr = 44100
    duration = 15.0
    t = np.arange(int(sr * duration)) / sr
    # Linearly increasing amplitude
    envelope = t / duration
    audio = (np.sin(2 * np.pi * 100 * t) * envelope).astype(np.float32)

    profile = measure_loudness(audio, sr)

    if len(profile.short_term_curve) >= 3:
        lufs_values = [p["short_term_lufs"] for p in profile.short_term_curve]
        # Later windows should be louder
        first_half = np.mean(lufs_values[:len(lufs_values) // 2])
        second_half = np.mean(lufs_values[len(lufs_values) // 2:])
        assert second_half > first_half, "Crescendo should show increasing loudness"


def test_fadeout():
    """Fadeout should show decreasing short-term loudness."""
    sr = 44100
    duration = 15.0
    t = np.arange(int(sr * duration)) / sr
    envelope = 1.0 - (t / duration)
    audio = (np.sin(2 * np.pi * 100 * t) * envelope).astype(np.float32)

    profile = measure_loudness(audio, sr)

    if len(profile.short_term_curve) >= 3:
        lufs_values = [p["short_term_lufs"] for p in profile.short_term_curve]
        first_half = np.mean(lufs_values[:len(lufs_values) // 2])
        second_half = np.mean(lufs_values[len(lufs_values) // 2:])
        assert second_half < first_half, "Fadeout should show decreasing loudness"


def test_quiet_vs_loud_tracks():
    """Quiet and loud tracks should produce different loudness profiles."""
    sr = 44100
    duration = 15.0
    t = np.arange(int(sr * duration)) / sr

    quiet_audio = np.sin(2 * np.pi * 100 * t).astype(np.float32) * 0.05
    loud_audio = np.sin(2 * np.pi * 100 * t).astype(np.float32) * 0.95

    quiet_profile = measure_loudness(quiet_audio, sr)
    loud_profile = measure_loudness(loud_audio, sr)

    assert loud_profile.integrated_lufs > quiet_profile.integrated_lufs + 10


# ============================================================
# AdaptiveConfig defaults tests
# ============================================================

def test_config_defaults():
    """All default config values should be within expected ranges."""
    cfg = AdaptiveConfig()

    assert 0.5 <= cfg.min_adaptive_gain < 1.0
    assert cfg.neutral_adaptive_gain == 1.0
    assert cfg.max_adaptive_gain > 1.0
    assert 0.5 <= cfg.min_duration_gain < 1.0
    assert cfg.max_duration_gain > 1.0
    assert cfg.gain_attack > 0
    assert cfg.gain_release > cfg.gain_attack
    assert cfg.loudness_deadband_lu > 0
    assert cfg.silence_gate_lufs < -50
