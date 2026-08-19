"""Tests for Pydantic models and JSON schema."""

import json

from hearbeat.models import (
    AnalysisEvent,
    AnalysisResult,
    BassEventDetail,
    EventType,
    RhythmInfo,
    SourceInfo,
)


def test_event_type_enum():
    assert EventType.BEAT.value == "beat"
    assert EventType.BASS.value == "bass"
    assert EventType.BASS_BEAT.value == "bass_beat"
    assert EventType.BASS_OFFBEAT.value == "bass_offbeat"
    assert EventType.BASS_ACCENT.value == "bass_accent"


def test_analysis_event_creation():
    event = AnalysisEvent(
        time=1.5,
        type=EventType.BEAT,
        strength=0.8,
    )
    assert event.time == 1.5
    assert event.type == EventType.BEAT
    assert event.strength == 0.8
    assert event.beat_delta_seconds is None


def test_analysis_event_with_all_fields():
    event = AnalysisEvent(
        time=2.347,
        type=EventType.BASS_BEAT,
        strength=0.92,
        raw_rms=0.045,
        beat_delta_seconds=-0.014,
        nearest_beat_time=2.361,
        duration=0.083,
    )
    assert event.beat_delta_seconds == -0.014
    assert event.nearest_beat_time == 2.361


def test_strength_validation():
    # Strength must be 0.0-1.0
    event = AnalysisEvent(time=0.0, type=EventType.BEAT, strength=0.5)
    assert event.strength == 0.5

    # Out of range should fail
    try:
        AnalysisEvent(time=0.0, type=EventType.BEAT, strength=1.5)
        assert False, "Should have raised validation error"
    except Exception:
        pass


def test_json_serialization():
    result = AnalysisResult(
        source=SourceInfo(
            filename="test.mp3",
            duration_seconds=180.5,
            sample_rate=44100,
        ),
        rhythm=RhythmInfo(
            bpm=120.0,
            confidence=0.95,
            beat_count=360,
            beats=[0.5, 1.0, 1.5],
        ),
        events=[
            AnalysisEvent(time=0.5, type=EventType.BEAT, strength=0.95),
            AnalysisEvent(
                time=0.49,
                type=EventType.BASS_BEAT,
                strength=0.82,
                beat_delta_seconds=-0.01,
                nearest_beat_time=0.5,
            ),
        ],
        warnings=["Test warning"],
    )

    json_str = result.model_dump_json(indent=2)
    parsed = json.loads(json_str)

    assert parsed["schema_version"] == "0.1"
    assert parsed["source"]["filename"] == "test.mp3"
    assert parsed["rhythm"]["bpm"] == 120.0
    assert len(parsed["events"]) == 2
    assert parsed["events"][1]["type"] == "bass_beat"
    assert parsed["warnings"] == ["Test warning"]


def test_json_schema_deterministic():
    result = AnalysisResult(
        source=SourceInfo(filename="a.mp3", duration_seconds=100.0, sample_rate=44100),
        rhythm=RhythmInfo(bpm=120.0, confidence=0.9),
    )
    json1 = json.loads(result.model_dump_json())
    json2 = json.loads(result.model_dump_json())
    assert json1 == json2


def test_bass_event_detail():
    detail = BassEventDetail(
        time=1.0,
        strength=0.7,
        raw_rms=0.03,
        duration=0.05,
        onset_strength=0.8,
    )
    assert detail.time == 1.0
    assert detail.onset_strength == 0.8


def test_empty_result():
    result = AnalysisResult(
        source=SourceInfo(filename="empty.mp3", duration_seconds=0.0, sample_rate=44100),
        rhythm=RhythmInfo(bpm=0.0, confidence=0.0),
    )
    assert result.events == []
    assert result.warnings == []
    json_str = result.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["events"] == []
