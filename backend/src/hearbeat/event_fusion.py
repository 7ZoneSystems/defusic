"""Event fusion: combines beat, bass, and drum events with temporal relationships.

Handles:
- Beat events from Essentia
- Bass events (transients + activity) from filter-bank bass analyzer
- Drum events (hihat, snare, kick, drum_onset) from drum analyzer + kick detector
- Deduplication of nearby events
"""

from __future__ import annotations

import logging

import numpy as np

from hearbeat.models import (
    AnalysisEvent,
    BassEventDetail,
    EventType,
)

logger = logging.getLogger(__name__)

# Tolerance for "on beat" in seconds
BEAT_ON_TOLERANCE = 0.06  # 60ms

# Minimum gap between events of the same type (seconds)
DEDUP_GAP = 0.03


def fuse_events(
    beat_info: dict,
    bass_events: list[dict],
    drum_events: list[dict] | None = None,
    beat_tolerance: float = BEAT_ON_TOLERANCE,
) -> tuple[list[AnalysisEvent], list[BassEventDetail], list[str]]:
    """Fuse beat, bass, and drum events into a unified event list.

    Args:
        beat_info: Output from BeatAnalyzer.analyze()
        bass_events: List of bass event dicts from BassAnalyzer
        drum_events: List of drum event dicts from DrumAnalyzer (optional)
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

    # Add bass events
    if len(bass_events) > 0:
        if len(beats) == 0:
            warnings.append("No beats detected; bass events will lack beat relationships")

        for be in bass_events:
            event_type = _classify_bass_event(be, beats if len(beats) > 0 else None, bass_events, beat_tolerance)
            bass_time = be["time"]

            nearest_beat = 0.0
            delta = 0.0
            if event_type != EventType.BASS_ACTIVITY and len(beats) > 0:
                nearest_idx = int(np.argmin(np.abs(beats - bass_time)))
                nearest_beat = float(beats[nearest_idx])
                delta = bass_time - nearest_beat

            events.append(AnalysisEvent(
                time=bass_time,
                type=event_type,
                strength=be["strength"],
                raw_rms=be.get("raw_rms"),
                normalized_energy=be.get("normalized_energy"),
                beat_delta_seconds=round(delta, 6) if event_type != EventType.BASS_ACTIVITY else None,
                nearest_beat_time=round(nearest_beat, 6) if event_type != EventType.BASS_ACTIVITY else None,
                duration=be["duration"],
            ))

            bass_details.append(BassEventDetail(
                time=be["time"],
                strength=be["strength"],
                raw_rms=be.get("raw_rms", 0.0),
                duration=be["duration"],
                normalized_energy=be.get("normalized_energy"),
                event_kind=be.get("event_kind"),
                onset_strength=be.get("onset_strength"),
            ))
    else:
        warnings.append("No bass events detected")

    # Add drum events
    if drum_events:
        for de in drum_events:
            events.append(AnalysisEvent(
                time=de["time"],
                type=de["type"],
                strength=de["strength"],
                confidence=de.get("confidence"),
                nearest_beat_time=de.get("nearest_beat"),
                beat_delta_seconds=de.get("beat_delta_seconds"),
            ))

    # Deduplicate: remove events that are too close together
    events = _deduplicate_events(events)

    # Stats
    type_counts: dict[str, int] = {}
    for e in events:
        type_counts[e.type] = type_counts.get(e.type, 0) + 1
    logger.info("Fusion result: %s", type_counts)

    return events, bass_details, warnings


def _classify_bass_event(
    be: dict,
    beats: np.ndarray | None,
    all_bass_events: list[dict],
    beat_tolerance: float,
) -> EventType:
    """Classify a bass event based on its characteristics."""
    if be.get("event_kind") == "activity":
        # Use the event_type from bass analyzer (subbass_activity vs bass_activity)
        activity_type = be.get("event_type", "bass_activity")
        if activity_type == "subbass_activity":
            return EventType.SUBBASS_ACTIVITY
        return EventType.BASS_ACTIVITY

    if beats is None or len(beats) == 0:
        return EventType.BASS

    bass_time = be["time"]
    nearest_idx = int(np.argmin(np.abs(beats - bass_time)))
    nearest_beat = float(beats[nearest_idx])
    delta = bass_time - nearest_beat

    is_on_beat = abs(delta) <= beat_tolerance

    if is_on_beat:
        event_type = EventType.BASS_BEAT
    else:
        event_type = EventType.BASS_OFFBEAT

    # Strong off-beat accent
    if len(all_bass_events) >= 3:
        all_strengths = [e["strength"] for e in all_bass_events]
        p80 = float(np.percentile(all_strengths, 80))
        if be["strength"] >= p80 and not is_on_beat:
            event_type = EventType.BASS_ACCENT

    return event_type


def _deduplicate_events(events: list[AnalysisEvent]) -> list[AnalysisEvent]:
    """Remove events that are too close together.

    Higher-priority events survive over lower-priority ones.
    Priority: subbass > bass_activity > bass_accent > bass_beat >
              bass > kick > snare > hihat > bass_offbeat >
              drum_onset > cymbal > percussion > beat
    """
    if not events:
        return []

    priority = {
        "subbass": 0,
        "bass_accent": 1,
        "bass_beat": 2,
        "bass": 3,
        "kick": 4,
        "snare": 5,
        "hihat": 6,
        "bass_offbeat": 7,
        "drum_onset": 8,
        "subbass_activity": 9,
        "bass_activity": 10,
        "cymbal": 11,
        "percussion": 12,
        "beat": 13,
    }

    events.sort(key=lambda e: (e.time, priority.get(e.type, 99)))

    result: list[AnalysisEvent] = []
    for event in events:
        if result:
            last = result[-1]
            gap = event.time - last.time
            last_is_priority = priority.get(last.type, 99) <= priority.get(event.type, 99)

            if gap < DEDUP_GAP:
                # Keep the higher-priority event
                if not last_is_priority:
                    result[-1] = event
                continue

        result.append(event)

    return result
