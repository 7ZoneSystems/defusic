/** Haptic event type and configuration types. */

export interface HapticEvent {
  time: number;
  type: string;
  intensity: number;
  duration_ms: number;
  is_anticipation: boolean;
}

export interface HapticTimeline {
  version: string;
  duration_seconds: number;
  config_used: string;
  events: HapticEvent[];
}

export interface HapticEventConfig {
  intensity: number;
  duration_ms: number;
}

export interface HapticConfig {
  beat: HapticEventConfig;
  hihat: HapticEventConfig;
  kick: HapticEventConfig;
  snare: HapticEventConfig;
  bass: HapticEventConfig;
  subbass: HapticEventConfig;
  bass_beat: HapticEventConfig;
  bass_offbeat: HapticEventConfig;
  bass_accent: HapticEventConfig;
  bass_activity: HapticEventConfig;
  drum_onset: HapticEventConfig;
  cymbal: HapticEventConfig;
  percussion: HapticEventConfig;
  anticipation_enabled: boolean;
  minimum_gap_ms: number;
  master_intensity: number;
}

export type HapticCapability = 'full' | 'vibrate-only' | 'none';

export interface HapticDriverResult {
  supported: boolean;
  capability: HapticCapability;
}

export const DEFAULT_HAPTIC_CONFIG: HapticConfig = {
  beat: { intensity: 0.15, duration_ms: 30 },
  hihat: { intensity: 0.40, duration_ms: 22 },
  kick: { intensity: 0.70, duration_ms: 65 },
  snare: { intensity: 0.55, duration_ms: 40 },
  bass: { intensity: 0.80, duration_ms: 85 },
  subbass: { intensity: 0.72, duration_ms: 110 },
  bass_beat: { intensity: 0.75, duration_ms: 70 },
  bass_offbeat: { intensity: 0.50, duration_ms: 50 },
  bass_accent: { intensity: 0.85, duration_ms: 90 },
  bass_activity: { intensity: 0.65, duration_ms: 100 },
  drum_onset: { intensity: 0.50, duration_ms: 35 },
  cymbal: { intensity: 0.45, duration_ms: 30 },
  percussion: { intensity: 0.50, duration_ms: 35 },
  anticipation_enabled: false,
  minimum_gap_ms: 20,
  master_intensity: 1.0,
};
