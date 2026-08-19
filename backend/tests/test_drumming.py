"""Tests for drum analysis pipeline and diagnostic sounds."""

import numpy as np

from hearbeat.drum_analyzer import DrumAnalyzer
from hearbeat.drum_sounds import (
    SOUND_DEFS,
    LayerConfig,
    generate_sound,
    get_layer_volume,
)
from hearbeat.diagnostic_player import (
    generate_drum_diagnostic,
    generate_layer,
    generate_music_diagnostic,
)
from hearbeat.models import AnalysisMode, AnalysisResult, DrumEventDetail, DrumEventType


# --- Drum sound generation tests ---

def test_generate_sine_sound():
    cfg = SOUND_DEFS["beat"]
    audio = generate_sound(cfg, volume=0.5, sr=44100)
    assert len(audio) > 0
    assert audio.dtype == np.float32
    assert np.max(np.abs(audio)) <= 0.5 + 1e-6


def test_generate_triangle_sound():
    cfg = SOUND_DEFS["kick"]
    audio = generate_sound(cfg, volume=0.8, sr=44100)
    assert len(audio) > 0
    assert np.max(np.abs(audio)) <= 0.8 + 1e-6


def test_generate_noise_burst():
    cfg = SOUND_DEFS["snare"]
    audio = generate_sound(cfg, volume=0.6, sr=44100)
    assert len(audio) > 0


def test_sound_volume_zero():
    cfg = SOUND_DEFS["beat"]
    audio = generate_sound(cfg, volume=0.0, sr=44100)
    assert np.max(np.abs(audio)) == 0.0


def test_layer_config_defaults():
    cfg = LayerConfig()
    assert cfg.beat == 0.45
    assert cfg.drum == 0.60
    assert cfg.bass == 0.90
    assert cfg.kick == 0.70
    assert cfg.snare == 0.65
    assert cfg.hihat == 0.40


def test_get_layer_volume():
    cfg = LayerConfig()
    assert get_layer_volume("beat", cfg) == 0.45
    assert get_layer_volume("kick", cfg) == 0.70
    assert get_layer_volume("snare", cfg) == 0.65
    assert get_layer_volume("hihat", cfg) == 0.40
    assert get_layer_volume("bass", cfg) == 0.90
    assert get_layer_volume("unknown_type", cfg) == 0.5


# --- Diagnostic player tests ---

def test_generate_layer_empty():
    audio = generate_layer([], "beat", sr=44100)
    assert len(audio) == 0


def test_generate_layer_single_hit():
    audio = generate_layer([1.0], "beat", sr=44100)
    assert len(audio) > 44100  # at least 1s + padding


def test_generate_layer_multiple_hits():
    audio = generate_layer([0.5, 1.0, 1.5], "kick", sr=44100)
    assert len(audio) > 0


def test_generate_drum_diagnostic_empty():
    audio, sr = generate_drum_diagnostic([], sr=44100)
    assert len(audio) == 0
    assert sr == 44100


def test_generate_drum_diagnostic_with_events():
    events = [
        {"time": 0.5, "type": "kick"},
        {"time": 1.0, "type": "snare"},
        {"time": 1.5, "type": "hihat"},
        {"time": 2.0, "type": "kick"},
    ]
    audio, sr = generate_drum_diagnostic(events, sr=44100)
    assert len(audio) > 0
    peak = np.max(np.abs(audio))
    assert peak <= 1.0 + 1e-6


def test_generate_drum_diagnostic_filtered_layers():
    events = [
        {"time": 0.5, "type": "kick"},
        {"time": 1.0, "type": "snare"},
        {"time": 1.5, "type": "hihat"},
    ]
    audio_kick_only, _ = generate_drum_diagnostic(events, sr=44100, active_layers={"kick"})
    audio_all, _ = generate_drum_diagnostic(events, sr=44100)
    # Kick-only should have less energy
    assert np.sum(np.abs(audio_kick_only)) < np.sum(np.abs(audio_all))


def test_generate_music_diagnostic_empty():
    audio, sr = generate_music_diagnostic([], sr=44100)
    assert len(audio) == 0


def test_generate_music_diagnostic_with_events():
    class FakeEvent:
        def __init__(self, time, type_):
            self.time = time
            self.type = type_

    events = [
        FakeEvent(0.5, "beat"),
        FakeEvent(1.0, "bass_beat"),
        FakeEvent(1.5, "bass_offbeat"),
    ]
    audio, sr = generate_music_diagnostic(events, sr=44100)
    assert len(audio) > 0
    assert np.max(np.abs(audio)) <= 1.0 + 1e-6


# --- Drum event type tests ---

def test_drum_event_type_enum():
    assert DrumEventType.KICK.value == "kick"
    assert DrumEventType.SNARE.value == "snare"
    assert DrumEventType.HIHAT.value == "hihat"
    assert DrumEventType.DRUM_ONSET.value == "drum_onset"


def test_drum_event_detail_creation():
    detail = DrumEventDetail(
        time=1.5,
        type="kick",
        strength=0.8,
        confidence=0.75,
        nearest_beat=1.48,
        beat_delta_seconds=0.02,
        beat_position=0.1,
    )
    assert detail.time == 1.5
    assert detail.type == "kick"
    assert detail.confidence == 0.75


def test_drum_event_detail_defaults():
    detail = DrumEventDetail(time=0.0, type="snare", strength=0.5, confidence=0.5)
    assert detail.nearest_beat == 0.0
    assert detail.beat_delta_seconds == 0.0
    assert detail.beat_position == 0.0


# --- Mode tests ---

def test_analysis_mode_enum():
    assert AnalysisMode.MUSIC.value == "music"
    assert AnalysisMode.DRUMMING.value == "drumming"


def test_result_mode_field():
    result = AnalysisResult(
        source={"filename": "test.mp3", "duration_seconds": 10.0, "sample_rate": 44100},
        rhythm={"bpm": 120.0, "confidence": 0.8, "beat_count": 20, "beats": []},
        mode="drumming",
        schema_version="0.2",
    )
    assert result.mode == "drumming"
    assert result.schema_version == "0.2"


def test_result_drum_events_empty():
    result = AnalysisResult(
        source={"filename": "test.mp3", "duration_seconds": 10.0, "sample_rate": 44100},
        rhythm={"bpm": 120.0, "confidence": 0.8, "beat_count": 20, "beats": []},
    )
    assert result.drum_events_raw == []


# --- Drum analyzer classification tests ---

def test_drum_analyzer_classify_kick():
    analyzer = DrumAnalyzer()
    # Low centroid, high low-band energy = kick
    feat = {
        "spectral_centroid": 100.0,
        "spectral_bandwidth": 300.0,
        "low_band_energy": 0.8,
        "mid_band_energy": 0.1,
        "high_band_energy": 0.05,
        "total_energy": 1.0,
    }
    event_type, confidence = analyzer._classify_event(feat)
    assert event_type == "kick"
    assert confidence >= 0.6


def test_drum_analyzer_classify_hihat():
    analyzer = DrumAnalyzer()
    # High centroid, high high-band energy = hihat
    feat = {
        "spectral_centroid": 5000.0,
        "spectral_bandwidth": 2000.0,
        "low_band_energy": 0.05,
        "mid_band_energy": 0.1,
        "high_band_energy": 0.8,
        "total_energy": 1.0,
    }
    event_type, confidence = analyzer._classify_event(feat)
    assert event_type == "hihat"
    assert confidence >= 0.6


def test_drum_analyzer_classify_fallback():
    analyzer = DrumAnalyzer()
    # Ambiguous features = drum_onset
    feat = {
        "spectral_centroid": 500.0,
        "spectral_bandwidth": 800.0,
        "low_band_energy": 0.3,
        "mid_band_energy": 0.3,
        "high_band_energy": 0.2,
        "total_energy": 1.0,
    }
    event_type, confidence = analyzer._classify_event(feat)
    # May or may not classify specifically, but should return something valid
    assert event_type in ("kick", "snare", "hihat", "drum_onset")
