"""Tests for bass analysis with sustained bass detection."""

import numpy as np

from hearbeat.bass_analyzer import BassAnalyzer
from hearbeat.event_fusion import fuse_events
from hearbeat.models import EventType


# --- Bass analyzer feature extraction tests ---

def test_low_frequency_energy_sine():
    """Low-freq energy should be high for a 60 Hz sine wave."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    bass = np.sin(2 * np.pi * 60 * t).astype(np.float32)

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)

    # Low-freq energy should be significant for 60 Hz
    assert len(features["low_freq_energy"]) > 0
    assert features["low_freq_energy"].mean() > 0.01


def test_low_frequency_energy_high_freq():
    """Low-freq energy should be low for a 5000 Hz tone."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    bass = np.sin(2 * np.pi * 5000 * t).astype(np.float32) * 0.5

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)

    # Low-freq energy should be minimal for 5 kHz
    assert len(features["low_freq_energy"]) > 0
    assert features["low_freq_energy"].mean() < 0.1


def test_band_energy_subbass():
    """Sub-bass energy should be high for a 40 Hz tone."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    bass = np.sin(2 * np.pi * 40 * t).astype(np.float32)

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)

    assert len(features["subbass_energy"]) > 0
    assert features["subbass_energy"].mean() > 0.01


def test_bass_band_energy():
    """Bass band energy should capture 100 Hz."""
    sr = 44100
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    bass = np.sin(2 * np.pi * 100 * t).astype(np.float32)

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)

    assert len(features["bass_band_energy"]) > 0
    assert features["bass_band_energy"].mean() > 0.01


# --- Sustained bass activity detection tests ---

def test_sustained_bass_detected():
    """Strong sustained sub-bass should produce bass_activity events."""
    sr = 44100
    duration = 4.0
    t = np.arange(int(sr * duration)) / sr

    # Create sustained sub-bass (60 Hz, constant amplitude)
    bass = np.sin(2 * np.pi * 60 * t).astype(np.float32) * 0.8

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)
    activity = analyzer._detect_bass_activity(bass, sr, features)

    # Should detect at least one activity region
    assert len(activity) > 0, "Sustained bass should produce activity events"

    # Activity should span a significant duration
    assert activity[0]["duration"] > 0.5, "Sustained bass activity should last > 0.5s"


def test_no_bass_no_false_activity():
    """Silence should not produce false bass activity."""
    sr = 44100
    duration = 2.0
    bass = np.zeros(int(sr * duration), dtype=np.float32)

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)
    activity = analyzer._detect_bass_activity(bass, sr, features)

    assert len(activity) == 0, "Silence should not produce activity events"


def test_transient_bass_detected():
    """Sharp bass transients should produce bass events."""
    sr = 44100
    duration = 3.0
    t = np.arange(int(sr * duration)) / sr

    # Create sharp bass hits at 0.5, 1.0, 1.5, 2.0, 2.5
    bass = np.zeros_like(t)
    for hit_time in [0.5, 1.0, 1.5, 2.0, 2.5]:
        idx = int(hit_time * sr)
        # Short burst
        burst_len = int(0.05 * sr)
        end = min(idx + burst_len, len(bass))
        bass[idx:end] = np.sin(2 * np.pi * 80 * np.arange(burst_len) / sr)[:end-idx] * 0.9

    analyzer = BassAnalyzer()
    features = analyzer._extract_features(bass, sr)
    transients = analyzer._detect_bass_transients(bass, sr, features)

    # Should detect several transients
    assert len(transients) >= 3, f"Expected >= 3 transients, got {len(transients)}"


# --- Event fusion tests ---

def test_bass_activity_in_fusion():
    """Bass activity events should be included in fused output."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
        "beat_count": 6,
    }

    bass_events = [
        {
            "time": 1.5,
            "strength": 0.7,
            "raw_rms": 0.5,
            "normalized_energy": 0.6,
            "duration": 0.05,
            "onset_strength": 0.8,
            "frame_index": 100,
            "event_kind": "transient",
        },
        {
            "time": 2.25,
            "strength": 0.5,
            "raw_rms": 0.3,
            "normalized_energy": 0.4,
            "duration": 1.0,
            "onset_strength": 0.0,
            "frame_index": 200,
            "event_kind": "activity",
            "start_time": 1.75,
            "end_time": 2.75,
        },
    ]

    events, details, warnings = fuse_events(beat_info, bass_events)

    # Should have beat events + bass events
    beat_events = [e for e in events if e.type == EventType.BEAT]
    assert len(beat_events) == 6

    # Should have bass_beat (transient at 1.5 is on beat at 1.5)
    bass_beat_events = [e for e in events if e.type == EventType.BASS_BEAT]
    assert len(bass_beat_events) >= 1

    # Should have bass_activity
    activity_events = [e for e in events if e.type == EventType.BASS_ACTIVITY]
    assert len(activity_events) == 1, f"Expected 1 bass_activity, got {len(activity_events)}"
    assert activity_events[0].duration == 1.0


def test_bass_beat_classification():
    """Bass near a beat should be classified as bass_beat."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0],
        "beat_count": 3,
    }

    bass_events = [
        {
            "time": 1.005,  # Very close to beat at 1.0
            "strength": 0.6,
            "raw_rms": 0.4,
            "normalized_energy": 0.5,
            "duration": 0.05,
            "onset_strength": 0.7,
            "frame_index": 100,
            "event_kind": "transient",
        },
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    bass_events_out = [e for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_OFFBEAT)]
    assert len(bass_events_out) == 1
    assert bass_events_out[0].type == EventType.BASS_BEAT


def test_bass_offbeat_classification():
    """Bass between beats should be classified as bass_offbeat."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0],
        "beat_count": 3,
    }

    bass_events = [
        {
            "time": 1.5,  # Between beats at 1.0 and 2.0
            "strength": 0.5,
            "raw_rms": 0.3,
            "normalized_energy": 0.4,
            "duration": 0.05,
            "onset_strength": 0.6,
            "frame_index": 200,
            "event_kind": "transient",
        },
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    bass_events_out = [e for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_OFFBEAT)]
    assert len(bass_events_out) == 1
    assert bass_events_out[0].type == EventType.BASS_OFFBEAT


def test_bass_accent_classification():
    """Strong off-beat bass should be classified as bass_accent."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [1.0, 2.0, 3.0],
        "beat_count": 3,
    }

    # Create events with one very strong off-beat
    bass_events = [
        {"time": 1.1, "strength": 0.3, "raw_rms": 0.2, "normalized_energy": 0.25, "duration": 0.05,
         "onset_strength": 0.4, "frame_index": 100, "event_kind": "transient"},
        {"time": 1.3, "strength": 0.4, "raw_rms": 0.3, "normalized_energy": 0.35, "duration": 0.05,
         "onset_strength": 0.5, "frame_index": 150, "event_kind": "transient"},
        {"time": 1.6, "strength": 0.95, "raw_rms": 0.8, "normalized_energy": 0.9, "duration": 0.05,
         "onset_strength": 0.9, "frame_index": 200, "event_kind": "transient"},  # Strong off-beat
        {"time": 2.2, "strength": 0.3, "raw_rms": 0.2, "normalized_energy": 0.25, "duration": 0.05,
         "onset_strength": 0.4, "frame_index": 250, "event_kind": "transient"},
    ]

    events, _, _ = fuse_events(beat_info, bass_events)
    accent_events = [e for e in events if e.type == EventType.BASS_ACCENT]
    assert len(accent_events) >= 1, "Strong off-beat bass should be classified as accent"


def test_normalized_energy_preserved():
    """Normalized energy should be preserved in fused events."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [1.0],
        "beat_count": 1,
    }

    bass_events = [
        {
            "time": 1.0,
            "strength": 0.7,
            "raw_rms": 0.5,
            "normalized_energy": 0.65,
            "duration": 0.05,
            "onset_strength": 0.8,
            "frame_index": 100,
            "event_kind": "transient",
        },
    ]

    events, details, _ = fuse_events(beat_info, bass_events)
    bass_event = [e for e in events if e.type == EventType.BASS_BEAT][0]
    assert bass_event.normalized_energy == 0.65


def test_bass_detail_includes_event_kind():
    """BassEventDetail should include event_kind."""
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.8,
        "beats": [1.0],
        "beat_count": 1,
    }

    bass_events = [
        {
            "time": 1.0,
            "strength": 0.7,
            "raw_rms": 0.5,
            "normalized_energy": 0.65,
            "duration": 0.05,
            "onset_strength": 0.8,
            "frame_index": 100,
            "event_kind": "transient",
        },
    ]

    _, details, _ = fuse_events(beat_info, bass_events)
    assert len(details) == 1
    assert details[0].event_kind == "transient"
    assert details[0].normalized_energy == 0.65


# --- Model tests ---

def test_event_type_bass_activity():
    """EventType should include BASS_ACTIVITY."""
    assert EventType.BASS_ACTIVITY.value == "bass_activity"


def test_analysis_result_with_bass_activity():
    """AnalysisResult should accept bass_activity events."""
    from hearbeat.models import AnalysisResult, AnalysisEvent, SourceInfo, RhythmInfo

    result = AnalysisResult(
        source=SourceInfo(filename="test.mp3", duration_seconds=10.0, sample_rate=44100),
        rhythm=RhythmInfo(bpm=120.0, confidence=0.8, beat_count=20, beats=[]),
        events=[
            AnalysisEvent(time=1.0, type="beat", strength=0.8),
            AnalysisEvent(time=1.5, type="bass_activity", strength=0.6, duration=2.0),
        ],
    )
    assert len(result.events) == 2
    activity = [e for e in result.events if e.type == "bass_activity"]
    assert len(activity) == 1
    assert activity[0].duration == 2.0
