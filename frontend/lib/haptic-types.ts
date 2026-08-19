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
  adaptive_debug?: AdaptiveDebugEvent[];
  loudness?: LoudnessSummary;
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
  subbass_activity: HapticEventConfig;
  drum_onset: HapticEventConfig;
  cymbal: HapticEventConfig;
  percussion: HapticEventConfig;
  anticipation_enabled: boolean;
  minimum_gap_ms: number;
  master_intensity: number;
  adaptive_enabled: boolean;
  adaptive_gain_strength: number;
}

export type HapticCapability = 'full' | 'vibrate-only' | 'none';

export interface HapticDriverResult {
  supported: boolean;
  capability: HapticCapability;
}

export interface AdaptiveDebugEvent {
  time: number;
  type: string;
  base_intensity: number;
  adaptive_gain: number;
  final_intensity: number;
  base_duration_ms: number;
  duration_gain: number;
  final_duration_ms: number;
  local_short_term_lufs: number;
}

export interface LoudnessSummary {
  integrated_lufs: number;
  true_peak_dbtp: number;
  short_term_p10: number;
  short_term_p50: number;
  short_term_p90: number;
}

export interface LoudnessCurvePoint {
  time: number;
  short_term_lufs: number;
}

export const DEFAULT_HAPTIC_CONFIG: HapticConfig = {
  beat: { intensity: 0.15, duration_ms: 65 },
  hihat: { intensity: 0.40, duration_ms: 144 },
  kick: { intensity: 0.70, duration_ms: 200 },
  snare: { intensity: 0.55, duration_ms: 167 },
  bass: { intensity: 0.80, duration_ms: 200 },
  subbass: { intensity: 0.72, duration_ms: 170 },
  bass_beat: { intensity: 0.75, duration_ms: 150 },
  bass_offbeat: { intensity: 0.50, duration_ms: 100 },
  bass_accent: { intensity: 0.85, duration_ms: 180 },
  bass_activity: { intensity: 0.25, duration_ms: 200 },
  subbass_activity: { intensity: 0.50, duration_ms: 170 },
  drum_onset: { intensity: 0.50, duration_ms: 155 },
  cymbal: { intensity: 0.45, duration_ms: 100 },
  percussion: { intensity: 0.50, duration_ms: 120 },
  anticipation_enabled: false,
  minimum_gap_ms: 20,
  master_intensity: 1.0,
  adaptive_enabled: true,
  adaptive_gain_strength: 1.0,
};
