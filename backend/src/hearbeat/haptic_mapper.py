"""Haptic event mapper — translates musical events to haptic events.

This module does NOT perform audio analysis.
It operates on existing AnalysisEvent lists and produces HapticEvent lists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from hearbeat.haptic_config import HapticConfig
from hearbeat.models import AnalysisEvent, EventType

logger = logging.getLogger(__name__)

# Priority hierarchy: lower number = higher priority
_EVENT_PRIORITY: dict[str, int] = {
    "subbass": 0,
    "bass_activity": 1,
    "bass_accent": 2,
    "bass_beat": 3,
    "bass": 4,
    "kick": 5,
    "snare": 6,
    "hihat": 7,
    "bass_offbeat": 8,
    "drum_onset": 9,
    "cymbal": 10,
    "percussion": 11,
    "beat": 12,
}


@dataclass
class HapticEvent:
    """A single haptic event ready for device playback."""

    time: float
    type: str
    intensity: float
    duration_ms: int
    is_anticipation: bool = False

    def to_dict(self) -> dict:
        return {
            "time": round(self.time, 6),
            "type": self.type,
            "intensity": round(self.intensity, 4),
            "duration_ms": self.duration_ms,
            "is_anticipation": self.is_anticipation,
        }


@dataclass
class HapticTimeline:
    """A complete haptic timeline ready for device scheduling."""

    version: str = "0.1"
    duration_seconds: float = 0.0
    events: list[HapticEvent] = None  # type: ignore[assignment]
    config_used: str = "drummer_default"

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "duration_seconds": round(self.duration_seconds, 6),
            "config_used": self.config_used,
            "events": [e.to_dict() for e in self.events],
        }


class HapticMapper:
    """Maps musical analysis events to haptic events.

    Handles:
    - Event type to haptic parameter mapping
    - Collision merging for simultaneous events
    - Beat anticipation generation
    - Rate limiting / minimum gap enforcement
    """

    def __init__(
        self,
        config: HapticConfig | None = None,
        preset_name: str = "drummer_default",
    ) -> None:
        self.config = config or HapticConfig()
        self.preset_name = preset_name

    def map_events(
        self,
        events: list[AnalysisEvent],
        duration_seconds: float,
    ) -> HapticTimeline:
        """Convert a list of analysis events to a haptic timeline."""
        # Step 1: Map each event to a haptic event
        raw_haptic: list[HapticEvent] = []
        for event in events:
            haptic = self._map_single_event(event)
            if haptic is not None:
                raw_haptic.append(haptic)

        # Step 2: Collision handling — merge simultaneous events
        merged = self._handle_collisions(raw_haptic)

        # Step 3: Generate anticipation cues
        with_anticipation = self._add_anticipation(merged, duration_seconds)

        # Step 4: Rate limiting — enforce minimum gap
        rate_limited = self._rate_limit(with_anticipation)

        # Sort by time
        rate_limited.sort(key=lambda e: (e.time, _EVENT_PRIORITY.get(e.type, 99)))

        timeline = HapticTimeline(
            duration_seconds=duration_seconds,
            events=rate_limited,
            config_used=self.preset_name,
        )

        logger.info(
            "Mapped %d analysis events -> %d haptic events (duration=%.1fs)",
            len(events),
            len(rate_limited),
            duration_seconds,
        )
        return timeline

    def _map_single_event(self, event: AnalysisEvent) -> HapticEvent | None:
        """Map a single analysis event to a haptic event."""
        event_type = event.type if isinstance(event.type, str) else event.type.value

        cfg = self.config.for_event_type(event_type)

        # Scale intensity by the event's strength and master intensity
        base_intensity = cfg.intensity
        event_strength = event.strength if event.strength else 0.5
        intensity = base_intensity * event_strength * self.config.master_intensity
        intensity = max(0.0, min(1.0, intensity))

        # Duration
        duration_ms = cfg.duration_ms

        return HapticEvent(
            time=event.time,
            type=event_type,
            intensity=intensity,
            duration_ms=duration_ms,
        )

    def _handle_collisions(self, events: list[HapticEvent]) -> list[HapticEvent]:
        """Merge events that occur within the minimum gap.

        Strategy: keep the highest-priority event, merge intensity/duration
        if multiple events are simultaneous.
        """
        if not events:
            return []

        min_gap_s = self.config.minimum_gap_ms / 1000.0
        merged: list[HapticEvent] = []

        i = 0
        while i < len(events):
            current = events[i]
            group = [current]

            # Find all events within min_gap of current
            j = i + 1
            while j < len(events):
                if events[j].time - current.time <= min_gap_s:
                    group.append(events[j])
                    j += 1
                else:
                    break

            if len(group) == 1:
                merged.append(current)
            else:
                merged.append(self._merge_group(group))

            i = j

        return merged

    def _merge_group(self, group: list[HapticEvent]) -> HapticEvent:
        """Merge a group of simultaneous events into one.

        Uses the highest-priority event as the base, takes max intensity,
        and the longest duration.
        """
        # Sort by priority (lower number = higher priority)
        group.sort(key=lambda e: _EVENT_PRIORITY.get(e.type, 99))
        base = group[0]

        max_intensity = max(e.intensity for e in group)
        max_duration = max(e.duration_ms for e in group)

        # If the highest-priority event is beat, but a stronger event exists,
        # use the stronger event's type label
        if base.type == "beat" and len(group) > 1:
            for e in group:
                if e.type != "beat":
                    base = e
                    break

        return HapticEvent(
            time=base.time,
            type=base.type,
            intensity=max_intensity,
            duration_ms=max_duration,
        )

    def _add_anticipation(
        self, events: list[HapticEvent], duration_seconds: float
    ) -> list[HapticEvent]:
        """Add anticipation cues before important beats."""
        if not self.config.anticipation.enabled:
            return events

        acfg = self.config.anticipation
        output = list(events)

        # Find beat/kick/bass events and add anticipation before them
        important_times = sorted(
            {
                e.time
                for e in events
                if e.type in ("beat", "kick", "bass", "bass_beat", "bass_accent")
                and not e.is_anticipation
            }
        )

        for beat_time in important_times:
            for offset_ms, intensity in zip(acfg.offsets_ms, acfg.intensities):
                cue_time = beat_time - (offset_ms / 1000.0)
                if cue_time < 0:
                    continue

                # Scale anticipation intensity by master
                scaled_intensity = intensity * self.config.master_intensity
                if scaled_intensity <= 0:
                    continue

                output.append(
                    HapticEvent(
                        time=cue_time,
                        type="anticipation",
                        intensity=scaled_intensity,
                        duration_ms=15,
                        is_anticipation=True,
                    )
                )

        return output

    def _rate_limit(self, events: list[HapticEvent]) -> list[HapticEvent]:
        """Enforce minimum gap between events.

        If two events are closer than minimum_gap_ms, drop the lower-priority one.
        Anticipation events are dropped if too close to a real event in either direction.
        """
        if not events:
            return []

        min_gap_s = self.config.minimum_gap_ms / 1000.0
        events.sort(key=lambda e: (e.time, _EVENT_PRIORITY.get(e.type, 99)))

        output: list[HapticEvent] = []
        last_time = -999.0
        last_real_time = -999.0  # Track last non-anticipation event separately

        for event in events:
            gap = event.time - last_time
            gap_from_real = event.time - last_real_time

            if event.is_anticipation:
                # Anticipation must be far enough from the previous real event
                # and from the next real event (checked when real event is added)
                if gap_from_real < min_gap_s:
                    continue
            else:
                # Real event must be far enough from the previous real event
                if gap_from_real < min_gap_s:
                    # Too close to previous real event
                    curr_priority = _EVENT_PRIORITY.get(event.type, 99)
                    if output and not output[-1].is_anticipation:
                        prev_priority = _EVENT_PRIORITY.get(output[-1].type, 99)
                        if curr_priority < prev_priority:
                            output[-1] = event
                            last_real_time = event.time
                            last_time = event.time
                        continue
                    continue
                # Also check: real event shouldn't be too close to the last anticipation
                if output and output[-1].is_anticipation:
                    gap_from_last_anticip = event.time - output[-1].time
                    if gap_from_last_anticip < min_gap_s:
                        # Remove the anticipation that's too close
                        output.pop()

            output.append(event)
            if event.is_anticipation:
                last_time = event.time
            else:
                last_real_time = event.time
                last_time = event.time

        return output
