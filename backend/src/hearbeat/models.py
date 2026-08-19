"""Pydantic models for the analysis JSON schema."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AnalysisMode(str, Enum):
    MUSIC = "music"
    DRUMMING = "drumming"


class EventType(str, Enum):
    BEAT = "beat"
    BASS = "bass"
    BASS_BEAT = "bass_beat"
    BASS_OFFBEAT = "bass_offbeat"
    BASS_ACCENT = "bass_accent"
    BASS_ACTIVITY = "bass_activity"
    SUBBASS_ACTIVITY = "subbass_activity"


class DrumEventType(str, Enum):
    KICK = "kick"
    SNARE = "snare"
    HIHAT = "hihat"
    DRUM_ONSET = "drum_onset"
    CYMBAL = "cymbal"
    PERCUSSION = "percussion"


# Combined event type for serialization
ALL_EVENT_TYPES = (
    [e.value for e in EventType]
    + [e.value for e in DrumEventType]
)


class SourceInfo(BaseModel):
    filename: str
    duration_seconds: float
    sample_rate: int


class RhythmInfo(BaseModel):
    bpm: float
    confidence: float = Field(ge=0.0, le=1.0)
    beat_count: int = 0
    beats: list[float] = Field(default_factory=list)


class AnalysisEvent(BaseModel):
    time: float = Field(description="Timestamp in seconds from audio start")
    type: str
    strength: float = Field(ge=0.0, le=1.0, description="Normalized 0.0-1.0")
    raw_rms: Optional[float] = Field(default=None, description="Raw RMS energy if available")
    normalized_energy: Optional[float] = Field(default=None, description="Energy relative to track peak")
    beat_delta_seconds: Optional[float] = Field(
        default=None,
        description="Time difference to nearest beat (negative = before beat)",
    )
    nearest_beat_time: Optional[float] = Field(default=None)
    duration: Optional[float] = Field(default=None, description="Event duration in seconds")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class BassEventDetail(BaseModel):
    time: float
    strength: float
    raw_rms: float
    duration: float
    normalized_energy: Optional[float] = None
    event_kind: Optional[str] = None
    onset_strength: Optional[float] = None
    spectral_flux: Optional[float] = None


class DrumEventDetail(BaseModel):
    time: float
    type: str
    strength: float
    confidence: float = Field(ge=0.0, le=1.0)
    nearest_beat: float = 0.0
    beat_delta_seconds: float = 0.0
    beat_position: float = Field(ge=0.0, le=1.0, default=0.0)


class AnalysisResult(BaseModel):
    schema_version: str = "0.1"
    mode: str = "music"
    source: SourceInfo
    rhythm: RhythmInfo
    events: list[AnalysisEvent] = Field(default_factory=list)
    bass_events_raw: list[BassEventDetail] = Field(default_factory=list)
    drum_events_raw: list[DrumEventDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AnalysisJob(BaseModel):
    job_id: str
    status: str = "pending"
    filename: str = ""
    mode: str = "music"
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


# --- Haptic models ---


class HapticEventModel(BaseModel):
    """A single haptic event in the timeline."""

    time: float = Field(description="Timestamp in seconds")
    type: str = Field(description="Event type that triggered this haptic")
    intensity: float = Field(ge=0.0, le=1.0, description="Normalized haptic intensity 0.0-1.0")
    duration_ms: int = Field(ge=1, description="Haptic pulse duration in milliseconds")
    is_anticipation: bool = Field(default=False, description="Whether this is an anticipation cue")


class HapticTimelineModel(BaseModel):
    """Complete haptic timeline generated from analysis events."""

    version: str = "0.1"
    duration_seconds: float = 0.0
    config_used: str = "drummer_default"
    events: list[HapticEventModel] = Field(default_factory=list)


class HapticConfigUpdate(BaseModel):
    """User-provided haptic configuration overrides."""

    preset: Optional[str] = None
    beat_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    beat_duration_ms: Optional[int] = Field(default=None, ge=1)
    hihat_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    hihat_duration_ms: Optional[int] = Field(default=None, ge=1)
    kick_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    kick_duration_ms: Optional[int] = Field(default=None, ge=1)
    snare_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    snare_duration_ms: Optional[int] = Field(default=None, ge=1)
    bass_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bass_duration_ms: Optional[int] = Field(default=None, ge=1)
    subbass_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    subbass_duration_ms: Optional[int] = Field(default=None, ge=1)
    anticipation_enabled: Optional[bool] = None
    minimum_gap_ms: Optional[int] = Field(default=None, ge=0)
    master_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Adaptive haptic scaling
    adaptive_enabled: Optional[bool] = None
    adaptive_gain_strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# --- Loudness models ---


class LoudnessCurvePoint(BaseModel):
    """A single point on the loudness visualization curve."""

    time: float = Field(description="Time in seconds")
    short_term_lufs: float = Field(description="Short-term loudness in LUFS")


class LoudnessData(BaseModel):
    """Complete loudness profile for a track.

    Uses ITU-R BS.1770-style measurement.
    """

    integrated_lufs: float = Field(description="Integrated loudness (LUFS)")
    true_peak_dbtp: float = Field(description="True peak (dBTP)")

    short_term_p10: float = Field(description="10th percentile of short-term loudness")
    short_term_p50: float = Field(description="50th percentile (median) of short-term loudness")
    short_term_p90: float = Field(description="90th percentile of short-term loudness")

    momentary_max: float = Field(description="Maximum momentary loudness")

    curve: list[LoudnessCurvePoint] = Field(
        default_factory=list,
        description="Downsampled loudness curve for visualization",
    )


class AdaptiveDebugEvent(BaseModel):
    """Debug info for a single haptic event after adaptive scaling."""

    time: float
    type: str
    base_intensity: float
    adaptive_gain: float
    final_intensity: float
    base_duration_ms: int
    duration_gain: float
    final_duration_ms: int
    local_short_term_lufs: float
