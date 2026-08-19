"""Haptic configuration and presets."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HapticEventConfig:
    """Configuration for a single haptic event type."""

    intensity: float = 0.5
    duration_ms: int = 50

    def __post_init__(self) -> None:
        self.intensity = max(0.0, min(1.0, self.intensity))
        self.duration_ms = max(1, self.duration_ms)


@dataclass
class AnticipationConfig:
    """Configuration for beat anticipation cues."""

    enabled: bool = False
    offsets_ms: list[int] = field(default_factory=lambda: [250, 120])
    intensities: list[float] = field(default_factory=lambda: [0.05, 0.10])


@dataclass
class HapticConfig:
    """Complete haptic configuration.

    All values are configurable and centralized here.
    Do not scatter constants throughout the codebase.
    """

    beat: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.15, duration_ms=30))
    hihat: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.40, duration_ms=22))
    kick: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.70, duration_ms=65))
    snare: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.55, duration_ms=40))
    bass: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.80, duration_ms=85))
    subbass: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.72, duration_ms=110))
    bass_beat: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.75, duration_ms=70))
    bass_offbeat: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.50, duration_ms=50))
    bass_accent: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.85, duration_ms=90))
    bass_activity: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.65, duration_ms=100))
    drum_onset: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.50, duration_ms=155))
    cymbal: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.45, duration_ms=30))
    percussion: HapticEventConfig = field(default_factory=lambda: HapticEventConfig(intensity=0.50, duration_ms=35))

    anticipation: AnticipationConfig = field(default_factory=AnticipationConfig)

    minimum_gap_ms: int = 20
    master_intensity: float = 1.0

    def __post_init__(self) -> None:
        self.minimum_gap_ms = max(0, self.minimum_gap_ms)
        self.master_intensity = max(0.0, min(1.0, self.master_intensity))

    def for_event_type(self, event_type: str) -> HapticEventConfig:
        """Get the haptic config for a given event type."""
        mapping = {
            "beat": self.beat,
            "hihat": self.hihat,
            "kick": self.kick,
            "snare": self.snare,
            "bass": self.bass,
            "subbass": self.subbass,
            "bass_beat": self.bass_beat,
            "bass_offbeat": self.bass_offbeat,
            "bass_accent": self.bass_accent,
            "bass_activity": self.bass_activity,
            "drum_onset": self.drum_onset,
            "cymbal": self.cymbal,
            "percussion": self.percussion,
        }
        return mapping.get(event_type, self.beat)


# --- Presets ---


def drummer_default() -> HapticConfig:
    """Default preset optimized for drumming mode."""
    return HapticConfig(
        beat=HapticEventConfig(intensity=0.15, duration_ms=30),
        hihat=HapticEventConfig(intensity=0.40, duration_ms=22),
        kick=HapticEventConfig(intensity=0.70, duration_ms=65),
        snare=HapticEventConfig(intensity=0.55, duration_ms=40),
        bass=HapticEventConfig(intensity=0.80, duration_ms=85),
        subbass=HapticEventConfig(intensity=0.72, duration_ms=110),
        bass_beat=HapticEventConfig(intensity=0.75, duration_ms=70),
        bass_offbeat=HapticEventConfig(intensity=0.50, duration_ms=50),
        bass_accent=HapticEventConfig(intensity=0.85, duration_ms=90),
        bass_activity=HapticEventConfig(intensity=0.65, duration_ms=100),
        drum_onset=HapticEventConfig(intensity=0.50, duration_ms=155),
        cymbal=HapticEventConfig(intensity=0.45, duration_ms=30),
        percussion=HapticEventConfig(intensity=0.50, duration_ms=35),
        anticipation=AnticipationConfig(enabled=False),
        minimum_gap_ms=20,
        master_intensity=1.0,
    )


def music_enjoyment() -> HapticConfig:
    """Preset for music enjoyment mode — emphasis on bass structure."""
    return HapticConfig(
        beat=HapticEventConfig(intensity=0.12, duration_ms=25),
        hihat=HapticEventConfig(intensity=0.30, duration_ms=20),
        kick=HapticEventConfig(intensity=0.60, duration_ms=55),
        snare=HapticEventConfig(intensity=0.50, duration_ms=35),
        bass=HapticEventConfig(intensity=0.85, duration_ms=90),
        subbass=HapticEventConfig(intensity=0.78, duration_ms=120),
        bass_beat=HapticEventConfig(intensity=0.80, duration_ms=75),
        bass_offbeat=HapticEventConfig(intensity=0.55, duration_ms=55),
        bass_accent=HapticEventConfig(intensity=0.90, duration_ms=95),
        bass_activity=HapticEventConfig(intensity=0.70, duration_ms=110),
        drum_onset=HapticEventConfig(intensity=0.45, duration_ms=140),
        cymbal=HapticEventConfig(intensity=0.40, duration_ms=25),
        percussion=HapticEventConfig(intensity=0.45, duration_ms=30),
        anticipation=AnticipationConfig(
            enabled=True,
            offsets_ms=[250, 120],
            intensities=[0.05, 0.10],
        ),
        minimum_gap_ms=20,
        master_intensity=1.0,
    )


def minimal() -> HapticConfig:
    """Minimal preset — reduced intensity, longer gaps."""
    cfg = drummer_default()
    cfg.master_intensity = 0.6
    cfg.minimum_gap_ms = 40
    cfg.anticipation.enabled = False
    return cfg


def strong() -> HapticConfig:
    """Strong preset — increased intensity for testing."""
    cfg = drummer_default()
    cfg.master_intensity = 1.0
    cfg.beat.intensity = 0.25
    cfg.kick.intensity = 0.85
    cfg.bass.intensity = 0.90
    cfg.subbass.intensity = 0.85
    return cfg


PRESETS: dict[str, HapticConfig] = {
    "drummer_default": drummer_default,
    "music_enjoyment": music_enjoyment,
    "minimal": minimal,
    "strong": strong,
}


def get_preset(name: str) -> HapticConfig:
    """Get a preset by name. Falls back to drummer_default."""
    factory = PRESETS.get(name, drummer_default)
    return factory()


def list_presets() -> list[str]:
    """List available preset names."""
    return list(PRESETS.keys())
