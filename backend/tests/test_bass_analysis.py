"""Tests for multi-expert onset fusion, bass analysis, kick detection, and synthetic audio.

Covers:
- Expert onset detectors (HFC, complex, flux, RMS)
- Multi-expert fusion (normalization, clustering, scoring)
- Bass analyzer (multi-expert transients, hysteresis activity)
- Kick detector (multi-expert on filtered signal)
- Synthetic audio ground truth tests
- Event fusion integration
"""

import numpy as np
import pytest

from hearbeat.experts import (
    compute_stft,
    hfc_expert,
    complex_domain_expert,
    spectral_flux_expert,
    rms_difference_expert,
    compute_all_experts,
)
from hearbeat.onset_fusion import (
    FusionConfig,
    OnsetCandidate,
    normalize_expert,
    extract_peaks,
    cluster_peaks,
    fuse_candidates,
    apply_minimum_gap,
    multi_expert_fusion,
)
from hearbeat.filter_bank import FilterBank, _frame_rms
from hearbeat.bass_analyzer import BassAnalyzer
from hearbeat.kick_detector import KickDetector
from hearbeat.event_fusion import fuse_events, BEAT_ON_TOLERANCE
from hearbeat.models import EventType


# ============================================================
# Expert Tests
# ============================================================

def test_stft_computation():
    sr = 44100
    t = np.arange(sr * 1) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    mag, phase = compute_stft(audio, n_fft=2048, hop_length=512)
    assert mag.ndim == 2
    assert phase.ndim == 2
    assert mag.shape == phase.shape
    assert mag.shape[0] == 1025  # n_fft/2 + 1
    assert mag.shape[1] > 0


def test_hfc_expert():
    sr = 44100
    mag, phase = compute_stft(
        np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32),
        n_fft=2048, hop_length=512,
    )
    out = hfc_expert(mag, sr, 512)
    assert out.name == "hfc"
    assert len(out.onset_envelope) > 0
    assert out.onset_envelope.max() <= 1.0 + 1e-6
    assert out.onset_envelope.min() >= 0.0


def test_complex_domain_expert():
    sr = 44100
    mag, phase = compute_stft(
        np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32),
        n_fft=2048, hop_length=512,
    )
    out = complex_domain_expert(mag, phase, sr, 512)
    assert out.name == "complex"
    assert len(out.onset_envelope) > 0
    assert out.onset_envelope.max() <= 1.0 + 1e-6


def test_spectral_flux_expert():
    sr = 44100
    mag, _ = compute_stft(
        np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32),
        n_fft=2048, hop_length=512,
    )
    out = spectral_flux_expert(mag, sr, 512)
    assert out.name == "flux"
    assert len(out.onset_envelope) > 0
    assert out.onset_envelope.max() <= 1.0 + 1e-6


def test_rms_difference_expert():
    sr = 44100
    audio = np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32)
    out = rms_difference_expert(audio, sr, 512)
    assert out.name == "rms_diff"
    assert len(out.onset_envelope) > 0
    assert out.onset_envelope.max() <= 1.0 + 1e-6


def test_compute_all_experts():
    sr = 44100
    audio = np.sin(2 * np.pi * 100 * np.arange(sr) / sr).astype(np.float32)
    result = compute_all_experts(audio, sr, 2048, 512)
    assert "hfc" in result
    assert "complex" in result
    assert "flux" in result
    assert "rms_diff" in result
    # STFT-based experts share frame count, RMS diff may differ slightly
    stft_count = result["hfc"].n_frames
    for name in ["hfc", "complex", "flux"]:
        assert result[name].n_frames == stft_count
    # RMS diff uses a slightly different framing, allow ~5% tolerance
    assert abs(result["rms_diff"].n_frames - stft_count) <= max(5, stft_count * 0.05)


def test_experts_detect_transient():
    """Experts should detect an onset at a sudden burst."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.zeros_like(t)
    # Sharp onset at 1.0s
    idx = int(1.0 * sr)
    burst_len = int(0.05 * sr)
    end = min(idx + burst_len, len(audio))
    audio[idx:end] = np.sin(2 * np.pi * 100 * np.arange(burst_len) / sr)[:end - idx] * 0.9

    result = compute_all_experts(audio, sr, 2048, 512)
    # Each expert should have elevated energy around the onset
    for name, expert in result.items():
        peak_frame = np.argmax(expert.onset_envelope)
        peak_time = peak_frame * 512 / sr
        assert abs(peak_time - 1.0) < 0.15, f"{name} peak at {peak_time:.3f}, expected ~1.0"


# ============================================================
# Onset Fusion Tests
# ============================================================

def test_normalize_expert():
    env = np.array([0.0, 0.5, 1.0, 2.0, 0.1])
    norm = normalize_expert(env, percentile=95)
    assert norm.max() <= 1.0
    assert norm.min() >= 0.0
    # The 95th percentile value should map to ~1.0
    assert norm[3] == 1.0  # max value


def test_normalize_expert_zeros():
    env = np.zeros(100)
    norm = normalize_expert(env)
    assert np.all(norm == 0)


def test_extract_peaks():
    # Create a signal with clear peaks
    env = np.zeros(100)
    env[20] = 1.0
    env[50] = 0.8
    env[80] = 0.9

    frames, values = extract_peaks(env, 44100, 512, delta=0.05, min_distance_ms=30)
    assert len(frames) >= 2  # Should detect at least 2 peaks


def test_cluster_peaks_within_tolerance():
    # Two experts with peaks close together
    all_peaks = {
        "expert_a": (np.array([10, 50]), np.array([0.8, 0.9])),
        "expert_b": (np.array([11, 52]), np.array([0.7, 0.85])),
    }
    candidates = cluster_peaks(all_peaks, 44100, 512, tolerance_s=0.025)
    # Should cluster into 2 candidates (peaks at ~10 and ~50 frames)
    assert len(candidates) == 2
    # Each candidate should have 2 experts
    for c in candidates:
        assert len(c.expert_scores) == 2


def test_cluster_peaks_far_apart():
    all_peaks = {
        "expert_a": (np.array([10, 100]), np.array([0.8, 0.9])),
        "expert_b": (np.array([60, 150]), np.array([0.7, 0.85])),
    }
    candidates = cluster_peaks(all_peaks, 44100, 512, tolerance_s=0.025)
    # All 4 peaks are far apart -> 4 candidates
    assert len(candidates) == 4


def test_fuse_candidates_weighted_score():
    cand = OnsetCandidate(
        time=1.0, frame=100,
        expert_scores={"hfc": 0.5, "complex": 0.8, "flux": 0.6},
    )
    config = FusionConfig(expert_weights={"hfc": 0.25, "complex": 0.35, "flux": 0.25, "rms_diff": 0.15})
    result = fuse_candidates([cand], config)
    assert result[0].fused_score > 0
    assert result[0].fused_score <= 1.0
    assert result[0].n_experts_agreeing == 3


def test_fuse_candidates_agreement_boost():
    # 3 experts agreeing should get a boost over 1 expert
    single = OnsetCandidate(time=1.0, frame=100, expert_scores={"complex": 0.5})
    multi = OnsetCandidate(time=1.0, frame=100, expert_scores={"hfc": 0.5, "complex": 0.5, "flux": 0.5})
    config = FusionConfig()
    fuse_candidates([single], config)
    fuse_candidates([multi], config)
    assert multi.fused_score > single.fused_score


def test_apply_minimum_gap():
    candidates = [
        OnsetCandidate(time=1.0, frame=100, fused_score=0.8),
        OnsetCandidate(time=1.01, frame=101, fused_score=0.9),  # Too close, higher score
        OnsetCandidate(time=1.5, frame=200, fused_score=0.7),
    ]
    result = apply_minimum_gap(candidates, minimum_gap_s=0.05)
    assert len(result) == 2
    assert result[0].fused_score == 0.9  # Higher score kept (second overrides first)
    assert result[1].time == 1.5


def test_multi_expert_fusion_full():
    sr = 44100
    # Signal with a clear transient at 1.0s
    t = np.arange(sr * 2) / sr
    audio = np.zeros_like(t)
    idx = int(1.0 * sr)
    burst_len = int(0.05 * sr)
    end = min(idx + burst_len, len(audio))
    audio[idx:end] = np.sin(2 * np.pi * 80 * np.arange(burst_len) / sr)[:end - idx] * 0.9

    experts = compute_all_experts(audio, sr, 2048, 512)
    candidates = multi_expert_fusion(experts)
    assert len(candidates) >= 1
    # Should detect near 1.0s
    assert abs(candidates[0].time - 1.0) < 0.2


# ============================================================
# Filter Bank Tests
# ============================================================

def test_filter_bank_creates_default_bands():
    fb = FilterBank(sr=44100)
    assert "subbass" in fb.band_names
    assert "bass" in fb.band_names
    assert "lowmid" in fb.band_names


def test_filter_bank_low_freq_passes():
    fb = FilterBank(sr=44100, bands={"low": (20, 100)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 60 * t).astype(np.float32)
    filtered = fb.filter_band(audio, "low", causal=False)
    assert np.sqrt(np.mean(filtered**2)) > 0.01


def test_filter_bank_high_freq_rejected():
    fb = FilterBank(sr=44100, bands={"low": (20, 100)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 5000 * t).astype(np.float32) * 0.5
    filtered = fb.filter_band(audio, "low", causal=False)
    assert np.sqrt(np.mean(filtered**2)) < 0.01


def test_frame_rms():
    signal = np.ones(4096, dtype=np.float64)
    rms = _frame_rms(signal, 2048, 512)
    assert len(rms) > 0
    assert abs(rms[0] - 1.0) < 0.01


# ============================================================
# Bass Analyzer Tests (multi-expert)
# ============================================================

def test_bass_analyzer_sine_60hz():
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 60 * t).astype(np.float32) * 0.8

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)
    assert "events" in result
    assert "features" in result
    assert len(result["events"]) > 0


def test_bass_analyzer_silence():
    sr = 44100
    audio = np.zeros(int(sr * 2), dtype=np.float32)
    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)
    assert len(result["events"]) == 0


def test_bass_analyzer_sustained_bass():
    """Sustained bass should produce activity events."""
    sr = 44100
    duration = 4.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 60 * t).astype(np.float32) * 0.8

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    activity = [e for e in result["events"] if e.get("event_kind") == "activity"]
    assert len(activity) > 0, "Sustained 60 Hz bass should produce activity events"
    assert activity[0]["duration"] > 0.5, "Activity should span > 0.5s"


def test_bass_analyzer_transient_hits():
    """Short bass hits should produce transient events."""
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.zeros_like(t)

    for hit_time in [0.5, 1.0, 1.5, 2.0, 2.5]:
        idx = int(hit_time * sr)
        burst_len = int(0.05 * sr)
        end = min(idx + burst_len, len(audio))
        audio[idx:end] = np.sin(2 * np.pi * 80 * np.arange(burst_len) / sr)[:end - idx] * 0.9

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    transients = [e for e in result["events"] if e.get("event_kind") == "transient"]
    assert len(transients) >= 2, f"Expected >= 2 transients, got {len(transients)}"


def test_bass_analyzer_filtered_output():
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 80 * t).astype(np.float32)

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    assert "filtered" in result
    assert "subbass" in result["filtered"]
    assert "bass" in result["filtered"]
    assert "lowmid" in result["filtered"]
    assert len(result["filtered"]["bass"]) == len(audio)


def test_bass_analyzer_features():
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 80 * t).astype(np.float32)

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    features = result["features"]
    assert "subbass_energy" in features
    assert "bass_energy" in features
    assert "lowmid_energy" in features
    assert "bass_rms" in features
    assert len(features["bass_rms"]) > 0


def test_bass_transient_has_expert_scores():
    """Transient events should include multi-expert diagnostic info."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.zeros_like(t)
    idx = int(0.5 * sr)
    burst_len = int(0.05 * sr)
    end = min(idx + burst_len, len(audio))
    audio[idx:end] = np.sin(2 * np.pi * 80 * np.arange(burst_len) / sr)[:end - idx] * 0.9

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    transients = [e for e in result["events"] if e.get("event_kind") == "transient"]
    if transients:
        t0 = transients[0]
        assert "expert_scores" in t0
        assert "fused_score" in t0
        assert "n_experts_agreeing" in t0


def test_bass_high_freq_low_energy():
    """5000 Hz should have very low bass band energy."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 5000 * t).astype(np.float32) * 0.5

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    bass_energy = result["features"]["bass_energy"]
    if len(bass_energy) > 0:
        assert bass_energy.mean() < 0.005


# ============================================================
# Kick Detector Tests (multi-expert)
# ============================================================

def test_kick_detector_low_freq_transient():
    """Low-frequency transient should be a kick candidate."""
    sr = 44100
    t = np.arange(sr * 2) / sr
    drums = np.zeros_like(t)

    hit_idx = int(1.0 * sr)
    burst_len = int(0.08 * sr)
    end = min(hit_idx + burst_len, len(drums))
    burst = np.sin(2 * np.pi * 60 * np.arange(burst_len) / sr)[:end - hit_idx]
    decay = np.exp(-np.arange(end - hit_idx) / (0.02 * sr))
    drums[hit_idx:end] = (burst * decay * 0.9).astype(np.float32)

    beats = np.array([0.5, 1.0, 1.5], dtype=np.float64)
    detector = KickDetector(sr=sr)
    events = detector.detect(drums, beats)

    kick_events = [e for e in events if e["type"] == "kick"]
    assert len(kick_events) >= 1, "Sharp low-frequency hit should be detected as kick"


def test_kick_detector_continuous_sine_not_kicks():
    """Continuous low-frequency sine should NOT produce repeated kicks."""
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr
    drums = np.sin(2 * np.pi * 60 * t).astype(np.float32) * 0.8

    beats = np.array([0.5, 1.0, 1.5, 2.0, 2.5], dtype=np.float64)
    detector = KickDetector(sr=sr)
    events = detector.detect(drums, beats)

    assert len(events) <= 2, f"Continuous sine should not produce many kicks, got {len(events)}"


def test_kick_detector_empty():
    sr = 44100
    detector = KickDetector(sr=sr)
    events = detector.detect(np.array([], dtype=np.float32), np.array([]))
    assert events == []


def test_kick_detector_confidence():
    sr = 44100
    t = np.arange(sr * 1) / sr
    drums = np.zeros_like(t)
    hit_idx = int(0.5 * sr)
    burst_len = int(0.08 * sr)
    end = min(hit_idx + burst_len, len(drums))
    decay = np.exp(-np.arange(end - hit_idx) / (0.02 * sr))
    drums[hit_idx:end] = (np.sin(2 * np.pi * 60 * np.arange(burst_len) / sr)[:end - hit_idx] * decay * 0.9).astype(np.float32)

    beats = np.array([0.5], dtype=np.float64)
    detector = KickDetector(sr=sr)
    events = detector.detect(drums, beats)

    for e in events:
        assert "confidence" in e
        assert 0.0 <= e["confidence"] <= 1.0
        assert "kick_features" in e
        assert "expert_scores" in e


def test_kick_has_expert_scores():
    """Kick events should include expert fusion diagnostics."""
    sr = 44100
    t = np.arange(sr * 1) / sr
    drums = np.zeros_like(t)
    hit_idx = int(0.5 * sr)
    burst_len = int(0.08 * sr)
    end = min(hit_idx + burst_len, len(drums))
    decay = np.exp(-np.arange(end - hit_idx) / (0.02 * sr))
    drums[hit_idx:end] = (np.sin(2 * np.pi * 60 * np.arange(burst_len) / sr)[:end - hit_idx] * decay * 0.9).astype(np.float32)

    beats = np.array([0.5], dtype=np.float64)
    detector = KickDetector(sr=sr)
    events = detector.detect(drums, beats)

    for e in events:
        kf = e["kick_features"]
        assert "fused_score" in kf
        assert "n_experts_agreeing" in kf
        assert "attack_ratio" in kf
        assert "decay_ratio" in kf


# ============================================================
# Event Fusion Tests
# ============================================================

def test_fuse_empty_bass():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5, 2.0], "beat_count": 4,
    }
    events, details, warnings = fuse_events(beat_info, [])
    beat_events = [e for e in events if e.type == EventType.BEAT]
    assert len(beat_events) == 4
    assert any("No bass events" in w for w in warnings)


def test_fuse_empty_beats():
    beat_info = {
        "bpm": 0.0, "confidence": 0.0,
        "beats": [], "beat_count": 0,
    }
    bass_events = [
        {"time": 1.0, "strength": 0.8, "raw_rms": 0.05, "duration": 0.1},
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)
    bass_evts = [e for e in events if e.type == EventType.BASS]
    assert len(bass_evts) == 1
    assert any("No beats detected" in w for w in warnings)


def test_fuse_on_beat():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5], "beat_count": 3,
    }
    bass_events = [
        {"time": 0.505, "strength": 0.8, "raw_rms": 0.05, "duration": 0.1},
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)
    bass_evts = [e for e in events if e.type == EventType.BASS_BEAT]
    assert len(bass_evts) == 1
    assert abs(bass_evts[0].beat_delta_seconds) < BEAT_ON_TOLERANCE


def test_fuse_offbeat():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5], "beat_count": 3,
    }
    bass_events = [
        {"time": 0.75, "strength": 0.6, "raw_rms": 0.03, "duration": 0.08},
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)
    bass_evts = [e for e in events if e.type == EventType.BASS_OFFBEAT]
    assert len(bass_evts) == 1
    assert bass_evts[0].beat_delta_seconds is not None
    assert abs(bass_evts[0].beat_delta_seconds) > BEAT_ON_TOLERANCE


def test_fuse_mixed_events():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5, 2.0], "beat_count": 4,
    }
    bass_events = [
        {"time": 0.502, "strength": 0.9, "raw_rms": 0.06, "duration": 0.1},
        {"time": 0.75, "strength": 0.4, "raw_rms": 0.02, "duration": 0.05},
        {"time": 1.001, "strength": 0.85, "raw_rms": 0.055, "duration": 0.09},
        {"time": 1.25, "strength": 0.7, "raw_rms": 0.04, "duration": 0.06},
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)

    on_beat = [e for e in events if e.type == EventType.BASS_BEAT]
    offbeat = [e for e in events if e.type == EventType.BASS_OFFBEAT]
    assert len(on_beat) == 2
    assert len(offbeat) == 2
    assert len(details) == 4


def test_fuse_with_drum_events():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5], "beat_count": 3,
    }
    drum_events = [
        {"time": 0.5, "type": "kick", "strength": 0.8, "confidence": 0.7,
         "nearest_beat": 0.5, "beat_delta_seconds": 0.0, "beat_position": 0.0},
        {"time": 0.75, "type": "hihat", "strength": 0.5, "confidence": 0.6,
         "nearest_beat": 0.5, "beat_delta_seconds": 0.25, "beat_position": 0.5},
    ]
    events, _, _ = fuse_events(beat_info, [], drum_events)

    kick_events = [e for e in events if e.type == "kick"]
    hihat_events = [e for e in events if e.type == "hihat"]
    assert len(kick_events) == 1
    assert len(hihat_events) == 1


def test_bass_activity_in_fusion():
    beat_info = {
        "bpm": 120.0, "confidence": 0.8,
        "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0], "beat_count": 6,
    }
    bass_events = [
        {
            "time": 1.5, "strength": 0.7, "raw_rms": 0.5,
            "normalized_energy": 0.6, "duration": 0.05,
            "onset_strength": 0.8, "frame_index": 100, "event_kind": "transient",
        },
        {
            "time": 2.25, "strength": 0.5, "raw_rms": 0.3,
            "normalized_energy": 0.4, "duration": 1.0,
            "onset_strength": 0.0, "frame_index": 200,
            "event_kind": "activity", "start_time": 1.75, "end_time": 2.75,
        },
    ]

    events, details, warnings = fuse_events(beat_info, bass_events)

    beat_events = [e for e in events if e.type == EventType.BEAT]
    assert len(beat_events) >= 5

    bass_beat_events = [e for e in events if e.type == EventType.BASS_BEAT]
    assert len(bass_beat_events) >= 1

    activity_events = [e for e in events if e.type == EventType.BASS_ACTIVITY]
    assert len(activity_events) == 1
    assert activity_events[0].duration == 1.0


def test_bass_accent_classification():
    beat_info = {
        "bpm": 120.0, "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0], "beat_count": 3,
    }
    bass_events = [
        {"time": 1.1, "strength": 0.3, "raw_rms": 0.2, "normalized_energy": 0.25, "duration": 0.05,
         "onset_strength": 0.4, "frame_index": 100, "event_kind": "transient"},
        {"time": 1.3, "strength": 0.4, "raw_rms": 0.3, "normalized_energy": 0.35, "duration": 0.05,
         "onset_strength": 0.5, "frame_index": 150, "event_kind": "transient"},
        {"time": 1.6, "strength": 0.95, "raw_rms": 0.8, "normalized_energy": 0.9, "duration": 0.05,
         "onset_strength": 0.9, "frame_index": 200, "event_kind": "transient"},
        {"time": 2.2, "strength": 0.3, "raw_rms": 0.2, "normalized_energy": 0.25, "duration": 0.05,
         "onset_strength": 0.4, "frame_index": 250, "event_kind": "transient"},
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    accent_events = [e for e in events if e.type == EventType.BASS_ACCENT]
    assert len(accent_events) >= 1


def test_normalized_energy_preserved():
    beat_info = {
        "bpm": 120.0, "confidence": 0.8,
        "beats": [1.0], "beat_count": 1,
    }
    bass_events = [
        {"time": 1.0, "strength": 0.7, "raw_rms": 0.5,
         "normalized_energy": 0.65, "duration": 0.05,
         "onset_strength": 0.8, "frame_index": 100, "event_kind": "transient"},
    ]

    events, details, _ = fuse_events(beat_info, bass_events)
    bass_event = [e for e in events if e.type == EventType.BASS_BEAT][0]
    assert bass_event.normalized_energy == 0.65


def test_event_type_bass_activity():
    assert EventType.BASS_ACTIVITY.value == "bass_activity"


def test_strength_normalized():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0], "beat_count": 2,
    }
    bass_events = [
        {"time": 0.5, "strength": 0.1, "raw_rms": 0.01, "duration": 0.03},
        {"time": 1.0, "strength": 0.95, "raw_rms": 0.08, "duration": 0.12},
    ]
    events, _, _ = fuse_events(beat_info, bass_events)
    strengths = [e.strength for e in events if e.type != EventType.BEAT]
    assert all(0.0 <= s <= 1.0 for s in strengths)


def test_beat_delta_calculation():
    beat_info = {
        "bpm": 100.0, "confidence": 0.85,
        "beats": [0.6, 1.2, 1.8], "beat_count": 3,
    }
    bass_events = [
        {"time": 0.63, "strength": 0.7, "raw_rms": 0.04, "duration": 0.05},
    ]
    events, _, _ = fuse_events(beat_info, bass_events)
    bass_evt = [e for e in events if e.type == EventType.BASS_BEAT][0]
    assert bass_evt.beat_delta_seconds is not None
    assert abs(bass_evt.beat_delta_seconds - 0.03) < 0.001
    assert bass_evt.nearest_beat_time == 0.6


def test_multiple_experts_agreeing():
    """Multiple experts detecting the same event should produce higher fused score."""
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.zeros_like(t)
    # Sharp onset at 1.0s with multiple frequency components
    idx = int(1.0 * sr)
    burst_len = int(0.08 * sr)
    end = min(idx + burst_len, len(audio))
    t_burst = np.arange(burst_len) / sr
    audio[idx:end] = (
        np.sin(2 * np.pi * 80 * t_burst) * 0.5 +
        np.sin(2 * np.pi * 200 * t_burst) * 0.3 +
        np.sin(2 * np.pi * 800 * t_burst) * 0.2
    )[:end - idx] * 0.9

    experts = compute_all_experts(audio, sr, 2048, 512)
    candidates = multi_expert_fusion(experts)

    if candidates:
        # With multiple frequency components, multiple experts should agree
        assert candidates[0].n_experts_agreeing >= 2
