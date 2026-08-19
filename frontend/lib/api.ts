import { AnalysisJob, AnalysisMode, WaveformData } from './types';
import { HapticTimeline } from './haptic-types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error('Backend unavailable');
  return res.json();
}

export async function analyzeFile(file: File, mode: AnalysisMode = 'music'): Promise<AnalysisJob> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_URL}/analyze?mode=${mode}`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Analysis failed');
  }
  return res.json();
}

export async function getAnalysis(jobId: string): Promise<AnalysisJob> {
  const res = await fetch(`${API_URL}/analysis/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch analysis');
  return res.json();
}

export function getOriginalAudioUrl(jobId: string): string {
  return `${API_URL}/analysis/${jobId}/audio`;
}

export function getDiagnosticAudioUrl(jobId: string, layers: string[] = ['all']): string {
  const layerParam = layers.join(',');
  return `${API_URL}/analysis/${jobId}/diagnostic?layers=${encodeURIComponent(layerParam)}`;
}

export function getClickTrackUrl(jobId: string, multi = false): string {
  const params = multi ? '?multi=true' : '';
  return `${API_URL}/analysis/${jobId}/click-track${params}`;
}

export function getJsonDownloadUrl(jobId: string): string {
  return `${API_URL}/analysis/${jobId}/json`;
}

export function getVisualizeUrl(jobId: string): string {
  return `${API_URL}/visualize/${jobId}`;
}

export async function getWaveformData(
  jobId: string,
  resolution = 2000
): Promise<WaveformData> {
  const res = await fetch(`${API_URL}/analysis/${jobId}/waveform?resolution=${resolution}`);
  if (!res.ok) throw new Error('Failed to fetch waveform data');
  return res.json();
}

export async function getHapticTimeline(
  jobId: string,
  configUpdate?: Record<string, unknown>
): Promise<HapticTimeline> {
  const res = await fetch(`${API_URL}/analysis/${jobId}/haptic`, {
    method: 'POST',
    headers: configUpdate ? { 'Content-Type': 'application/json' } : undefined,
    body: configUpdate ? JSON.stringify(configUpdate) : undefined,
  });
  if (!res.ok) throw new Error('Failed to generate haptic timeline');
  return res.json();
}

export async function getPresets(): Promise<{ presets: string[] }> {
  const res = await fetch(`${API_URL}/presets`);
  if (!res.ok) throw new Error('Failed to fetch presets');
  return res.json();
}

export async function getLoudnessProfile(
  jobId: string
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_URL}/analysis/${jobId}/loudness`);
  if (!res.ok) throw new Error('Failed to fetch loudness profile');
  return res.json();
}
