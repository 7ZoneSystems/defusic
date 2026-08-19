export type EventType = 'beat' | 'bass' | 'bass_beat' | 'bass_offbeat' | 'bass_accent';

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
  beat_delta_seconds?: number | null;
  nearest_beat_time?: number | null;
  duration?: number | null;
}

export interface BassEventDetail {
  time: number;
  strength: number;
  raw_rms: number;
  duration: number;
  onset_strength?: number | null;
  spectral_flux?: number | null;
}

export interface AnalysisResult {
  schema_version: string;
  source: SourceInfo;
  rhythm: RhythmInfo;
  events: AnalysisEvent[];
  bass_events_raw: BassEventDetail[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface AnalysisJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename: string;
  result: AnalysisResult | null;
  error: string | null;
}

export type AppState = 'idle' | 'file_selected' | 'analyzing' | 'complete' | 'error';
