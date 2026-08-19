"""Event fusion: combines beat and bass events with temporal relationships."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from hearbeat.models import (
    AnalysisEvent,
    BassEventDetail,
    EventType,
    RhythmInfo,
)

logger = logging.getLogger(__name__)

# Tolerance for "on beat" in seconds
BEAT_ON_TOLERANCE = 0.06  # 60ms


def fuse_events(
    beat_info: dict,
    bass_events: list[dict],
    beat_tolerance: float = BEAT_ON_TOLERANCE,
) -> tuple[list[AnalysisEvent], list[BassEventDetail], list[str]]:
    """Fuse beat and bass events into a unified event list.

    Args:
        beat_info: Output from BeatAnalyzer.analyze()
        bass_events: List of bass event dicts from BassAnalyzer
        beat_tolerance: How close to a beat to count as "on beat"

    Returns:
        Tuple of (analysis_events, bass_event_details, warnings)
    """
    warnings: list[str] = []
    events: list[AnalysisEvent] = []
    bass_details: list[BassEventDetail] = []

    beats = np.array(beat_info["beats"], dtype=np.float64)
    bpm = beat_info["bpm"]
    confidence = beat_info["confidence"]

    # Add beat events
    for beat_time in beats:
        events.append(AnalysisEvent(
            time=float(beat_time),
            type=EventType.BEAT,
            strength=confidence,
        ))

    if len(bass_events) == 0:
        warnings.append("No bass events detected")
        return events, bass_details, warnings

    if len(beats) == 0:
        warnings.append("No beats detected; bass events will lack beat relationships")
        for be in bass_events:
            event_type = _classify_bass_event(be, None, bass_events, beat_tolerance)
            events.append(AnalysisEvent(
                time=be["time"],
                type=event_type,
                strength=be["strength"],
                raw_rms=be["raw_rms"],
                normalized_energy=be.get("normalized_energy"),
                duration=be["duration"],
            ))
            bass_details.append(_bass_event_detail(be))
        return events, bass_details, warnings

    # For each bass event, find nearest beat and classify
    for be in bass_events:
        event_type = _classify_bass_event(be, beats, bass_events, beat_tolerance)
        bass_time = be["time"]

        # Beat alignment (skip for activity events that span multiple beats)
        nearest_beat = 0.0
        delta = 0.0
        if event_type != EventType.BASS_ACTIVITY:
            nearest_idx = int(np.argmin(np.abs(beats - bass_time)))
            nearest_beat = float(beats[nearest_idx])
            delta = bass_time - nearest_beat

        events.append(AnalysisEvent(
            time=bass_time,
            type=event_type,
            strength=be["strength"],
            raw_rms=be["raw_rms"],
            normalized_energy=be.get("normalized_energy"),
            beat_delta_seconds=round(delta, 6) if event_type != EventType.BASS_ACTIVITY else None,
            nearest_beat_time=round(nearest_beat, 6) if event_type != EventType.BASS_ACTIVITY else None,
            duration=be["duration"],
        ))

        bass_details.append(_bass_event_detail(be))

    # Stats
    on_beat_count = sum(
        1 for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_ACCENT)
    )
    activity_count = sum(
        1 for e in events if e.type == EventType.BASS_ACTIVITY
    )
    total_bass = len(bass_events)
    if total_bass > 0:
        logger.info(
            "Fusion: %d bass events, %d on-beat, %d activity",
            total_bass, on_beat_count, activity_count,
        )

    return events, bass_details, warnings


def _classify_bass_event(
    be: dict,
    beats: np.ndarray | None,
    all_bass_events: list[dict],
    beat_tolerance: float,
) -> EventType:
    """Classify a bass event based on its characteristics."""
    # Activity events are pre-classified
    if be.get("event_kind") == "activity":
        return EventType.BASS_ACTIVITY

    # If no beats available, use generic bass type
    if beats is None or len(beats) == 0:
        return EventType.BASS

    bass_time = be["time"]
    nearest_idx = int(np.argmin(np.abs(beats - bass_time)))
    nearest_beat = float(beats[nearest_idx])
    delta = bass_time - nearest_beat

    is_on_beat = abs(delta) <= beat_tolerance

    # Determine event type
    if is_on_beat:
        event_type = EventType.BASS_BEAT
    else:
        event_type = EventType.BASS_OFFBEAT

    # Check if this is a strong bass accent (top 20% strength)
    if len(all_bass_events) >= 3:
        all_strengths = [e["strength"] for e in all_bass_events]
        p80 = float(np.percentile(all_strengths, 80))
        if be["strength"] >= p80 and not is_on_beat:
            event_type = EventType.BASS_ACCENT

    return event_type


def _bass_event_detail(be: dict) -> BassEventDetail:
    """Convert a raw bass event dict to a BassEventDetail model."""
    return BassEventDetail(
        time=be["time"],
        strength=be["strength"],
        raw_rms=be["raw_rms"],
        duration=be["duration"],
        normalized_energy=be.get("normalized_energy"),
        event_kind=be.get("event_kind"),
        onset_strength=be.get("onset_strength"),
    )
