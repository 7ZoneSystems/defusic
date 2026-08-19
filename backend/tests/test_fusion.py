"""Tests for beat/bass event fusion logic."""

import numpy as np

from hearbeat.event_fusion import fuse_events, BEAT_ON_TOLERANCE
from hearbeat.models import EventType


def test_fuse_empty_bass():
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5, 2.0],
        "beat_count": 4,
    }
    events, details, warnings = fuse_events(beat_info, [])
    # Should have 4 beat events only
    beat_events = [e for e in events if e.type == EventType.BEAT]
    assert len(beat_events) == 4
    assert any("No bass events" in w for w in warnings)


def test_fuse_empty_beats():
    beat_info = {
        "bpm": 0.0,
        "confidence": 0.0,
        "beats": [],
        "beat_count": 0,
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
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5],
        "beat_count": 3,
    }
    # Bass event very close to a beat
    bass_events = [
        {"time": 0.505, "strength": 0.8, "raw_rms": 0.05, "duration": 0.1},
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)
    bass_evts = [e for e in events if e.type == EventType.BASS_BEAT]
    assert len(bass_evts) == 1
    assert abs(bass_evts[0].beat_delta_seconds) < BEAT_ON_TOLERANCE


def test_fuse_offbeat():
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5],
        "beat_count": 3,
    }
    # Bass event exactly between beats (0.75 is midway between 0.5 and 1.0)
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
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5, 2.0],
        "beat_count": 4,
    }
    bass_events = [
        {"time": 0.502, "strength": 0.9, "raw_rms": 0.06, "duration": 0.1},   # on beat
        {"time": 0.75, "strength": 0.4, "raw_rms": 0.02, "duration": 0.05},   # offbeat
        {"time": 1.001, "strength": 0.85, "raw_rms": 0.055, "duration": 0.09}, # on beat
        {"time": 1.25, "strength": 0.7, "raw_rms": 0.04, "duration": 0.06},   # offbeat
    ]
    events, details, warnings = fuse_events(beat_info, bass_events)

    on_beat = [e for e in events if e.type == EventType.BASS_BEAT]
    offbeat = [e for e in events if e.type == EventType.BASS_OFFBEAT]
    assert len(on_beat) == 2
    assert len(offbeat) == 2
    assert len(details) == 4


def test_beat_delta_calculation():
    beat_info = {
        "bpm": 100.0,
        "confidence": 0.85,
        "beats": [0.6, 1.2, 1.8],
        "beat_count": 3,
    }
    # Bass at 0.63, nearest beat is 0.6, delta should be +0.03
    bass_events = [
        {"time": 0.63, "strength": 0.7, "raw_rms": 0.04, "duration": 0.05},
    ]
    events, _, _ = fuse_events(beat_info, bass_events)
    bass_evt = [e for e in events if e.type == EventType.BASS_BEAT][0]
    assert bass_evt.beat_delta_seconds is not None
    assert abs(bass_evt.beat_delta_seconds - 0.03) < 0.001
    assert bass_evt.nearest_beat_time == 0.6


def test_strength_normalized():
    beat_info = {
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0],
        "beat_count": 2,
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
        "bpm": 120.0,
        "confidence": 0.9,
        "beats": [0.5, 1.0, 1.5],
        "beat_count": 3,
    }
    bass_events = [
        {"time": 0.5, "strength": 0.8, "raw_rms": 0.05, "duration": 0.1},
        {"time": 0.75, "strength": 0.5, "raw_rms": 0.03, "duration": 0.06},
    ]
    events, _, _ = fuse_events(beat_info, bass_events)
    # 3 beats + 2 bass, but bass at t=0.5 merges with beat at t=0.5
    assert len(events) >= 4
