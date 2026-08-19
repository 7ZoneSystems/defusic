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
            events.append(AnalysisEvent(
                time=be["time"],
                type=EventType.BASS,
                strength=be["strength"],
                raw_rms=be["raw_rms"],
                duration=be["duration"],
            ))
            bass_details.append(_bass_event_detail(be))
        return events, bass_details, warnings

    # For each bass event, find nearest beat and classify
    for be in bass_events:
        bass_time = be["time"]
        nearest_idx = int(np.argmin(np.abs(beats - bass_time)))
        nearest_beat = float(beats[nearest_idx])
        delta = bass_time - nearest_beat

        is_on_beat = abs(delta) <= beat_tolerance
        is_offbeat = not is_on_beat

        # Determine event type
        if is_on_beat:
            event_type = EventType.BASS_BEAT
        else:
            event_type = EventType.BASS_OFFBEAT

        # Check if this is a strong bass accent (top 20% strength)
        # relative to all bass events — only when there are enough events
        if len(bass_events) >= 3:
            all_strengths = [b["strength"] for b in bass_events]
            p80 = float(np.percentile(all_strengths, 80))
            if be["strength"] >= p80 and not is_on_beat:
                event_type = EventType.BASS_ACCENT

        events.append(AnalysisEvent(
            time=bass_time,
            type=event_type,
            strength=be["strength"],
            raw_rms=be["raw_rms"],
            beat_delta_seconds=round(delta, 6),
            nearest_beat_time=round(nearest_beat, 6),
            duration=be["duration"],
        ))

        bass_details.append(_bass_event_detail(be))

    # Stats
    on_beat_count = sum(
        1 for e in events if e.type in (EventType.BASS_BEAT, EventType.BASS_ACCENT)
    )
    total_bass = len(bass_events)
    if total_bass > 0:
        logger.info(
            "Fusion: %d bass events, %d on-beat (%.0f%%)",
            total_bass,
            on_beat_count,
            100 * on_beat_count / total_bass,
        )

    return events, bass_details, warnings


def _bass_event_detail(be: dict) -> BassEventDetail:
    """Convert a raw bass event dict to a BassEventDetail model."""
    return BassEventDetail(
        time=be["time"],
        strength=be["strength"],
        raw_rms=be["raw_rms"],
        duration=be["duration"],
        onset_strength=be.get("onset_strength"),
    )
