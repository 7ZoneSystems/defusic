"""Tests for haptic translation engine."""

import json

import pytest

from hearbeat.haptic_config import (
    HapticConfig,
    HapticEventConfig,
    AnticipationConfig,
    drummer_default,
    music_enjoyment,
    minimal,
    strong,
    get_preset,
    list_presets,
)
from hearbeat.haptic_mapper import HapticMapper, HapticEvent, HapticTimeline
from hearbeat.models import AnalysisEvent, HapticEventModel, HapticTimelineModel, HapticConfigUpdate


# --- Config tests ---


def test_haptic_config_defaults():
    cfg = HapticConfig()
    assert cfg.beat.intensity == 0.15
    assert cfg.beat.duration_ms == 65
    assert cfg.kick.intensity == 0.70
    assert cfg.kick.duration_ms == 200
    assert cfg.bass.intensity == 0.80
    assert cfg.bass.duration_ms == 200
    assert cfg.minimum_gap_ms == 20
    assert cfg.master_intensity == 1.0


def test_haptic_config_clamping():
    cfg = HapticConfig()
    cfg.beat.intensity = 5.0
    cfg.beat.__post_init__()
    assert cfg.beat.intensity == 1.0

    cfg.beat.intensity = -1.0
    cfg.beat.__post_init__()
    assert cfg.beat.intensity == 0.0


def test_haptic_config_for_event_type():
    cfg = HapticConfig()
    beat = cfg.for_event_type("beat")
    assert beat.intensity == 0.15
    assert beat.duration_ms == 65

    kick = cfg.for_event_type("kick")
    assert kick.intensity == 0.70
    assert kick.duration_ms == 200

    # Unknown type falls back to beat
    unknown = cfg.for_event_type("nonexistent")
    assert unknown.intensity == beat.intensity


# --- Preset tests ---


def test_list_presets():
    presets = list_presets()
    assert "drummer_default" in presets
    assert "music_enjoyment" in presets
    assert "minimal" in presets
    assert "strong" in presets


def test_get_preset_drumer_default():
    cfg = get_preset("drummer_default")
    assert isinstance(cfg, HapticConfig)
    assert cfg.beat.intensity == 0.15
    assert cfg.kick.intensity == 0.70


def test_get_preset_music_enjoyment():
    cfg = get_preset("music_enjoyment")
    assert cfg.bass.intensity == 0.85
    assert cfg.anticipation.enabled is True


def test_get_preset_unknown():
    cfg = get_preset("nonexistent")
    assert cfg.beat.intensity == 0.15  # Falls back to drummer_default


def test_minimal_preset():
    cfg = get_preset("minimal")
    assert cfg.master_intensity == 0.6
    assert cfg.minimum_gap_ms == 40


def test_strong_preset():
    cfg = get_preset("strong")
    assert cfg.kick.intensity == 0.85
    assert cfg.bass.intensity == 0.90


# --- Mapper tests ---


def _make_event(time: float, event_type: str, strength: float = 0.5) -> AnalysisEvent:
    return AnalysisEvent(time=time, type=event_type, strength=strength)


def test_mapper_basic_beat():
    mapper = HapticMapper()
    events = [_make_event(1.0, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    assert len(timeline.events) == 1
    h = timeline.events[0]
    assert h.time == 1.0
    assert h.type == "beat"
    assert h.intensity > 0
    assert h.duration_ms == 65


def test_mapper_kick_stronger_than_beat():
    mapper = HapticMapper()
    beat = _make_event(1.0, "beat", 0.5)
    kick = _make_event(2.0, "kick", 0.5)

    timeline, _ = mapper.map_events([beat, kick], duration_seconds=10.0)
    beat_h = next(e for e in timeline.events if e.type == "beat")
    kick_h = next(e for e in timeline.events if e.type == "kick")

    assert kick_h.intensity > beat_h.intensity
    assert kick_h.duration_ms > beat_h.duration_ms


def test_mapper_bass_stronger_than_beat():
    mapper = HapticMapper()
    beat = _make_event(1.0, "beat", 0.5)
    bass = _make_event(2.0, "bass", 0.5)

    timeline, _ = mapper.map_events([beat, bass], duration_seconds=10.0)
    beat_h = next(e for e in timeline.events if e.type == "beat")
    bass_h = next(e for e in timeline.events if e.type == "bass")

    assert bass_h.intensity > beat_h.intensity
    assert bass_h.duration_ms > beat_h.duration_ms


def test_mapper_hihat_sharp():
    mapper = HapticMapper()
    hihat = _make_event(1.0, "hihat", 0.5)
    kick = _make_event(2.0, "kick", 0.5)

    timeline, _ = mapper.map_events([hihat, kick], duration_seconds=10.0)
    hihat_h = next(e for e in timeline.events if e.type == "hihat")
    kick_h = next(e for e in timeline.events if e.type == "kick")

    # Hi-hat shorter than kick
    assert hihat_h.duration_ms < kick_h.duration_ms


def test_mapper_subbass_long():
    mapper = HapticMapper()
    sub = _make_event(1.0, "subbass", 0.5)

    timeline, _ = mapper.map_events([sub], duration_seconds=10.0)
    sub_h = timeline.events[0]

    assert sub_h.duration_ms == 170
    assert sub_h.intensity > 0


def test_mapper_strength_scales_intensity():
    mapper = HapticMapper()
    weak = _make_event(1.0, "kick", 0.2)
    strong = _make_event(2.0, "kick", 0.9)

    timeline, _ = mapper.map_events([weak, strong], duration_seconds=10.0)
    weak_h = timeline.events[0]
    strong_h = timeline.events[1]

    assert strong_h.intensity > weak_h.intensity


def test_mapper_master_intensity_scales():
    cfg = HapticConfig(master_intensity=0.5)
    mapper = HapticMapper(config=cfg)
    kick = _make_event(1.0, "kick", 0.5)

    timeline, _ = mapper.map_events([kick], duration_seconds=10.0)
    h = timeline.events[0]

    # With master 0.5, intensity should be roughly halved
    full_cfg = HapticConfig()
    full_mapper = HapticMapper(config=full_cfg)
    full_timeline, _ = full_mapper.map_events([kick], duration_seconds=10.0)
    full_h = full_timeline.events[0]

    assert h.intensity < full_h.intensity


def test_mapper_empty_events():
    mapper = HapticMapper()
    timeline, _ = mapper.map_events([], duration_seconds=10.0)
    assert len(timeline.events) == 0
    assert timeline.duration_seconds == 10.0


def test_mapper_timeline_metadata():
    mapper = HapticMapper(preset_name="test_preset")
    events = [_make_event(1.0, "beat")]
    timeline, _ = mapper.map_events(events, duration_seconds=120.0)

    assert timeline.version == "0.1"
    assert timeline.config_used == "test_preset"
    assert timeline.duration_seconds == 120.0


# --- Collision handling tests ---


def test_collision_simultaneous_events_merge():
    """beat + kick + bass at same time should merge into one event."""
    mapper = HapticMapper()
    events = [
        _make_event(1.0, "beat", 0.5),
        _make_event(1.0, "kick", 0.5),
        _make_event(1.0, "bass", 0.5),
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    # Should have only 1 event (all merged)
    assert len(timeline.events) == 1
    h = timeline.events[0]
    # Bass has higher priority (4) than kick (5) and beat (12)
    assert h.type == "bass"
    # Intensity should be the max
    assert h.intensity > 0


def test_collision_close_events_merge():
    """Events within minimum_gap should merge."""
    cfg = HapticConfig(minimum_gap_ms=50)
    mapper = HapticMapper(config=cfg)
    events = [
        _make_event(1.000, "beat", 0.5),
        _make_event(1.010, "kick", 0.5),  # 10ms apart, within 50ms gap
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 1
    assert timeline.events[0].type == "kick"


def test_collision_distant_events_separate():
    """Events far apart should remain separate."""
    cfg = HapticConfig(minimum_gap_ms=20)
    mapper = HapticMapper(config=cfg)
    events = [
        _make_event(1.000, "beat", 0.5),
        _make_event(1.100, "kick", 0.5),  # 100ms apart
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 2


# --- Anticipation tests ---


def test_anticipation_disabled():
    cfg = HapticConfig()
    cfg.anticipation.enabled = False
    mapper = HapticMapper(config=cfg)
    events = [_make_event(2.0, "beat", 0.5)]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 0


def test_anticipation_generates_cues():
    cfg = HapticConfig()
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [250, 120]
    cfg.anticipation.intensities = [0.05, 0.10]
    mapper = HapticMapper(config=cfg)

    events = [_make_event(2.0, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 2

    # Check timing
    times = sorted([a.time for a in anticipations])
    assert abs(times[0] - 1.75) < 0.001  # 2.0 - 0.250
    assert abs(times[1] - 1.88) < 0.001  # 2.0 - 0.120


def test_anticipation_weak():
    cfg = HapticConfig()
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [250]
    cfg.anticipation.intensities = [0.05]
    mapper = HapticMapper(config=cfg)

    events = [_make_event(2.0, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 1
    # Anticipation should be weaker than the beat
    beat_h = next(e for e in timeline.events if e.type == "beat")
    assert anticipations[0].intensity < beat_h.intensity


def test_anticipation_before_kick():
    cfg = HapticConfig()
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [200]
    cfg.anticipation.intensities = [0.08]
    mapper = HapticMapper(config=cfg)

    events = [_make_event(3.0, "kick", 0.7)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 1
    assert abs(anticipations[0].time - 2.8) < 0.001


def test_anticipation_skips_negative_time():
    cfg = HapticConfig()
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [500]
    cfg.anticipation.intensities = [0.05]
    mapper = HapticMapper(config=cfg)

    # Beat at 0.2s, anticipation at -0.3s should be skipped
    events = [_make_event(0.2, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 0


def test_anticipation_master_intensity_scales():
    cfg = HapticConfig(master_intensity=0.5)
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [200]
    cfg.anticipation.intensities = [0.10]
    mapper = HapticMapper(config=cfg)

    events = [_make_event(2.0, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    anticipations = [e for e in timeline.events if e.is_anticipation]
    assert len(anticipations) == 1
    assert anticipations[0].intensity == pytest.approx(0.05, abs=0.001)


# --- Rate limiting tests ---


def test_rate_limiting_enforces_gap():
    cfg = HapticConfig(minimum_gap_ms=50)
    mapper = HapticMapper(config=cfg)
    events = [
        _make_event(1.000, "beat", 0.5),
        _make_event(1.030, "hihat", 0.5),  # 30ms apart
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    # Only one should survive
    assert len(timeline.events) == 1


def test_rate_limiting_keeps_priority():
    cfg = HapticConfig(minimum_gap_ms=50)
    mapper = HapticMapper(config=cfg)
    events = [
        _make_event(1.000, "beat", 0.5),
        _make_event(1.030, "kick", 0.5),  # 30ms apart
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 1
    assert timeline.events[0].type == "kick"  # Higher priority


def test_rate_limiting_anticipation_suppressed():
    cfg = HapticConfig(minimum_gap_ms=50)
    cfg.anticipation.enabled = True
    cfg.anticipation.offsets_ms = [30]
    cfg.anticipation.intensities = [0.10]
    mapper = HapticMapper(config=cfg)

    # Beat at 2.0, anticipation at 1.97 (30ms before)
    events = [_make_event(2.0, "beat", 0.5)]
    timeline, _ = mapper.map_events(events, duration_seconds=10.0)

    # The anticipation at 1.97 should be suppressed (too close to beat at 2.0)
    anticipations = [e for e in timeline.events if e.is_anticipation]
    # Either 0 or 1, but if 1 it should be > 50ms from the beat
    for a in anticipations:
        beat_time = 2.0
        assert (beat_time - a.time) * 1000 >= 50


# --- Event priority tests ---


def test_priority_kick_over_beat():
    """Kick should take priority over beat when simultaneous."""
    mapper = HapticMapper()
    events = [
        _make_event(1.0, "beat", 0.5),
        _make_event(1.0, "kick", 0.5),
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 1
    assert timeline.events[0].type == "kick"


def test_priority_bass_over_beat():
    """Bass should take priority over beat."""
    mapper = HapticMapper()
    events = [
        _make_event(1.0, "beat", 0.5),
        _make_event(1.0, "bass", 0.5),
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 1
    assert timeline.events[0].type == "bass"


def test_priority_subbass_over_bass():
    """Sub-bass should take priority over bass."""
    mapper = HapticMapper()
    events = [
        _make_event(1.0, "bass", 0.5),
        _make_event(1.0, "subbass", 0.5),
    ]

    timeline, _ = mapper.map_events(events, duration_seconds=10.0)
    assert len(timeline.events) == 1
    assert timeline.events[0].type == "subbass"


# --- Deterministic output tests ---


def test_deterministic_output():
    """Same input should produce same output."""
    mapper = HapticMapper()
    events = [
        _make_event(1.0, "beat", 0.5),
        _make_event(1.5, "kick", 0.7),
        _make_event(2.0, "bass", 0.6),
    ]

    t1, _ = mapper.map_events(events, duration_seconds=10.0)
    t2, _ = mapper.map_events(events, duration_seconds=10.0)

    assert len(t1.events) == len(t2.events)
    for e1, e2 in zip(t1.events, t2.events):
        assert e1.time == e2.time
        assert e1.type == e2.type
        assert e1.intensity == pytest.approx(e2.intensity, abs=0.0001)
        assert e1.duration_ms == e2.duration_ms


# --- Serialization tests ---


def test_haptic_event_to_dict():
    h = HapticEvent(time=1.5, type="kick", intensity=0.7, duration_ms=65)
    d = h.to_dict()
    assert d["time"] == 1.5
    assert d["type"] == "kick"
    assert d["intensity"] == 0.7
    assert d["duration_ms"] == 65
    assert d["is_anticipation"] is False


def test_haptic_event_anticipation_to_dict():
    h = HapticEvent(time=1.5, type="anticipation", intensity=0.05, duration_ms=15, is_anticipation=True)
    d = h.to_dict()
    assert d["is_anticipation"] is True


def test_haptic_timeline_to_dict():
    timeline = HapticTimeline(
        duration_seconds=120.0,
        events=[
            HapticEvent(time=1.0, type="beat", intensity=0.15, duration_ms=30),
            HapticEvent(time=1.5, type="kick", intensity=0.70, duration_ms=65),
        ],
        config_used="test",
    )
    d = timeline.to_dict()
    assert d["version"] == "0.1"
    assert d["duration_seconds"] == 120.0
    assert len(d["events"]) == 2
    assert d["events"][0]["type"] == "beat"


def test_haptic_timeline_json_serializable():
    timeline = HapticTimeline(
        duration_seconds=120.0,
        events=[
            HapticEvent(time=1.0, type="beat", intensity=0.15, duration_ms=30),
        ],
    )
    json_str = json.dumps(timeline.to_dict())
    assert "beat" in json_str


# --- Pydantic model tests ---


def test_haptic_event_model():
    m = HapticEventModel(time=1.0, type="beat", intensity=0.5, duration_ms=30)
    assert m.intensity >= 0.0
    assert m.intensity <= 1.0
    assert m.is_anticipation is False


def test_haptic_timeline_model():
    m = HapticTimelineModel(
        duration_seconds=120.0,
        events=[HapticEventModel(time=1.0, type="beat", intensity=0.5, duration_ms=30)],
    )
    assert len(m.events) == 1


def test_haptic_config_update():
    u = HapticConfigUpdate(
        preset="drummer_default",
        beat_intensity=0.20,
        kick_duration_ms=80,
        anticipation_enabled=True,
    )
    assert u.preset == "drummer_default"
    assert u.beat_intensity == 0.20
    assert u.kick_duration_ms == 80
    assert u.anticipation_enabled is True
