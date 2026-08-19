"""Tests for filter-bank bass analysis, kick detection, and synthetic audio."""

import numpy as np
import pytest

from hearbeat.filter_bank import FilterBank, _frame_rms
from hearbeat.bass_analyzer import BassAnalyzer
from hearbeat.kick_detector import KickDetector
from hearbeat.event_fusion import fuse_events, BEAT_ON_TOLERANCE
from hearbeat.models import EventType


# ============================================================
# Filter Bank Tests
# ============================================================

def test_filter_bank_creates_default_bands():
    fb = FilterBank(sr=44100)
    assert "subbass" in fb.band_names
    assert "bass" in fb.band_names
    assert "lowmid" in fb.band_names
    assert "kick_analysis" in fb.band_names


def test_filter_bank_custom_bands():
    fb = FilterBank(sr=44100, bands={"low": (20, 100), "high": (2000, 8000)})
    assert fb.band_names == ["low", "high"]


def test_filter_bank_low_freq_passes():
    fb = FilterBank(sr=44100, bands={"low": (20, 100)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 60 * t).astype(np.float32)
    filtered = fb.filter_band(audio, "low", causal=False)
    assert filtered.shape == audio.shape
    assert np.sqrt(np.mean(filtered**2)) > 0.01


def test_filter_bank_high_freq_rejected():
    fb = FilterBank(sr=44100, bands={"low": (20, 100)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 5000 * t).astype(np.float32) * 0.5
    filtered = fb.filter_band(audio, "low", causal=False)
    assert np.sqrt(np.mean(filtered**2)) < 0.01


def test_filter_bank_energy_envelope():
    fb = FilterBank(sr=44100, bands={"bass": (60, 150)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    envelope = fb.band_energy_envelope(audio, "bass", hop_length=512, frame_length=2048)
    assert len(envelope) > 0
    assert envelope.mean() > 0.01


def test_filter_bank_multi_band_energy():
    fb = FilterBank(sr=44100)
    sr = 44100
    t = np.arange(sr * 1) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    energies = fb.multi_band_energy(audio, hop_length=512, frame_length=2048)
    assert "subbass" in energies
    assert "bass" in energies
    assert "lowmid" in energies


def test_filter_bank_causal_vs_noncausal():
    fb = FilterBank(sr=44100, bands={"bass": (60, 150)}, order=4)
    sr = 44100
    t = np.arange(sr * 2) / sr
    audio = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    offline = fb.filter_band(audio, "bass", causal=False)
    causal = fb.filter_band(audio, "bass", causal=True)
    # Both should produce non-zero output
    assert np.sqrt(np.mean(offline**2)) > 0.01
    assert np.sqrt(np.mean(causal**2)) > 0.01


def test_frame_rms():
    signal = np.ones(4096, dtype=np.float64)
    rms = _frame_rms(signal, 2048, 512)
    assert len(rms) > 0
    assert abs(rms[0] - 1.0) < 0.01


# ============================================================
# Bass Analyzer Tests (filter-bank based)
# ============================================================

def test_bass_analyzer_sine_60hz():
    """60 Hz sine should produce bass events."""
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 60 * t).astype(np.float32) * 0.8

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    assert "events" in result
    assert "features" in result
    assert len(result["events"]) > 0


def test_bass_analyzer_high_freq_low_bass_energy():
    """5000 Hz tone should have very low bass band energy."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 5000 * t).astype(np.float32) * 0.5

    analyzer = BassAnalyzer(sr=sr)
    result = analyzer.analyze_audio(audio)

    # Bass band energy should be very low for 5000 Hz
    bass_energy = result["features"]["bass_energy"]
    if len(bass_energy) > 0:
        assert bass_energy.mean() < 0.005, "5000 Hz should have negligible bass band energy"


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
    assert len(transients) >= 3, f"Expected >= 3 transients, got {len(transients)}"


def test_bass_analyzer_filtered_output():
    """Analyzer should return filtered signals."""
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
    """Analyzer should return diagnostic features."""
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
    assert "onset_strength" in features
    assert len(features["bass_rms"]) > 0


# ============================================================
# Kick Detector Tests (synthetic)
# ============================================================

def test_kick_detector_low_freq_transient():
    """Low-frequency transient with sharp attack should be a kick candidate."""
    sr = 44100
    t = np.arange(sr * 2) / sr
    drums = np.zeros_like(t)

    # Sharp low-frequency hit at 1.0s
    hit_idx = int(1.0 * sr)
    burst_len = int(0.08 * sr)
    end = min(hit_idx + burst_len, len(drums))
    burst = np.sin(2 * np.pi * 60 * np.arange(burst_len) / sr)[:end - hit_idx]
    # Apply fast decay envelope
    decay = np.exp(-np.arange(end - hit_idx) / (0.02 * sr))
    drums[hit_idx:end] = (burst * decay * 0.9).astype(np.float32)

    beats = np.array([0.5, 1.0, 1.5], dtype=np.float64)
    detector = KickDetector(sr=sr)
    events = detector.detect(drums, beats)

    # Should detect at least one event
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

    # Should produce very few events (onset at start, then nothing)
    assert len(events) <= 2, f"Continuous sine should not produce many kicks, got {len(events)}"


def test_kick_detector_empty():
    sr = 44100
    detector = KickDetector(sr=sr)
    events = detector.detect(np.array([], dtype=np.float32), np.array([]))
    assert events == []


def test_kick_detector_confidence():
    """Kick events should have confidence scores."""
    sr = 44100
    t = np.arange(sr * 1) / sr
    drums = np.zeros_like(t)
    # Add a kick-like hit
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


# ============================================================
# Event Fusion Tests (preserved from original + updated)
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
    """Drum events should be included in fused output."""
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
    # One beat may be deduplicated with the bass event at t=1.5
    assert len(beat_events) >= 5

    bass_beat_events = [e for e in events if e.type == EventType.BASS_BEAT]
    assert len(bass_beat_events) >= 1

    activity_events = [e for e in events if e.type == EventType.BASS_ACTIVITY]
    assert len(activity_events) == 1
    assert activity_events[0].duration == 1.0


def test_bass_beat_classification():
    beat_info = {
        "bpm": 120.0, "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0], "beat_count": 3,
    }
    bass_events = [
        {"time": 1.005, "strength": 0.6, "raw_rms": 0.4,
         "normalized_energy": 0.5, "duration": 0.05,
         "onset_strength": 0.7, "frame_index": 100, "event_kind": "transient"},
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    bass_events_out = [e for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_OFFBEAT)]
    assert len(bass_events_out) == 1
    assert bass_events_out[0].type == EventType.BASS_BEAT


def test_bass_offbeat_classification():
    beat_info = {
        "bpm": 120.0, "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0], "beat_count": 3,
    }
    bass_events = [
        {"time": 1.5, "strength": 0.5, "raw_rms": 0.3,
         "normalized_energy": 0.4, "duration": 0.05,
         "onset_strength": 0.6, "frame_index": 200, "event_kind": "transient"},
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    bass_events_out = [e for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_OFFBEAT)]
    assert len(bass_events_out) == 1
    assert bass_events_out[0].type == EventType.BASS_OFFBEAT


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


def test_event_count_total():
    beat_info = {
        "bpm": 120.0, "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5], "beat_count": 3,
    }
    bass_events = [
        {"time": 0.5, "strength": 0.8, "raw_rms": 0.05, "duration": 0.1},
        {"time": 0.75, "strength": 0.5, "raw_rms": 0.03, "duration": 0.06},
    ]
    events, _, _ = fuse_events(beat_info, bass_events)
    # 3 beats + 2 bass, but bass at t=0.5 merges with beat at t=0.5
    assert len(events) >= 4


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
