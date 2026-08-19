export type AnalysisMode = 'music' | 'drumming';

export type EventType =
  | 'beat' | 'bass' | 'bass_beat' | 'bass_offbeat' | 'bass_accent' | 'bass_activity'
  | 'kick' | 'snare' | 'hihat' | 'drum_onset' | 'cymbal' | 'percussion';

export interface SourceInfo {
  filename: string;
  duration_seconds: number;
  sample_rate: number;
}

export interface RhythmInfo {
  bpm: number;
  confidence: number;
  beat_count: number;
  beats: number[];
}

export interface AnalysisEvent {
  time: number;
  type: EventType;
  strength: number;
  raw_rms?: number | null;
  normalized_energy?: number | null;
  beat_delta_seconds?: number | null;
  nearest_beat_time?: number | null;
  duration?: number | null;
  confidence?: number | null;
}

export interface BassEventDetail {
  time: number;
  strength: number;
  raw_rms: number;
  duration: number;
  normalized_energy?: number | null;
  event_kind?: string | null;
  onset_strength?: number | null;
  spectral_flux?: number | null;
}

export interface DrumEventDetail {
  time: number;
  type: string;
  strength: number;
  confidence: number;
  nearest_beat: number;
  beat_delta_seconds: number;
  beat_position: number;
}

export interface AnalysisResult {
  schema_version: string;
  mode: AnalysisMode;
  source: SourceInfo;
  rhythm: RhythmInfo;
  events: AnalysisEvent[];
  bass_events_raw: BassEventDetail[];
  drum_events_raw: DrumEventDetail[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface AnalysisJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename: string;
  mode: AnalysisMode;
  result: AnalysisResult | null;
  error: string | null;
}

export type AppState = 'idle' | 'file_selected' | 'analyzing' | 'complete' | 'error';

export interface WaveformData {
  waveform: number[];
  duration: number;
  sample_rate: number;
  resolution: number;
}

export interface DiagnosticLayer {
  id: string;
  label: string;
  color: string;
  enabled: boolean;
}

export const DRUM_LAYERS: DiagnosticLayer[] = [
  { id: 'beat', label: 'Beat', color: 'var(--beat-color)', enabled: true },
  { id: 'kick', label: 'Kick', color: '#CE4A4A', enabled: true },
  { id: 'snare', label: 'Snare', color: '#CEAE4A', enabled: true },
  { id: 'hihat', label: 'Hi-hat', color: '#4ACE7A', enabled: true },
  { id: 'drum_onset', label: 'Drum', color: '#9A6ACE', enabled: true },
  { id: 'bass', label: 'Bass', color: 'var(--bass-beat-color)', enabled: false },
];

export const MUSIC_LAYERS: DiagnosticLayer[] = [
  { id: 'beat', label: 'Beat', color: 'var(--beat-color)', enabled: true },
  { id: 'bass_beat', label: 'Bass+Beat', color: 'var(--bass-beat-color)', enabled: true },
  { id: 'bass_offbeat', label: 'Offbeat', color: 'var(--bass-offbeat-color)', enabled: false },
  { id: 'bass_accent', label: 'Accent', color: 'var(--bass-accent-color)', enabled: false },
  { id: 'bass', label: 'Bass', color: 'var(--bass-beat-color)', enabled: false },
];
