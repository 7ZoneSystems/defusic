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
