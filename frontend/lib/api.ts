import { AnalysisJob, AnalysisMode, WaveformData } from './types';
import { HapticTimeline } from './haptic-types';
import { API_BASE } from './config';

// --- Analysis endpoints ---

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Backend unavailable');
  return res.json();
}

export async function analyzeFile(file: File, mode: AnalysisMode = 'music'): Promise<AnalysisJob> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/analyze?mode=${mode}`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Analysis failed');
  }
  return res.json();
}

export async function getAnalysis(jobId: string): Promise<AnalysisJob> {
  const res = await fetch(`${API_BASE}/analysis/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch analysis');
  return res.json();
}

export function getOriginalAudioUrl(jobId: string): string {
  return `${API_BASE}/analysis/${jobId}/audio`;
}

export function getDiagnosticAudioUrl(jobId: string, layers: string[] = ['all']): string {
  const layerParam = layers.join(',');
  return `${API_BASE}/analysis/${jobId}/diagnostic?layers=${encodeURIComponent(layerParam)}`;
}

export function getClickTrackUrl(jobId: string, multi = false): string {
  const params = multi ? '?multi=true' : '';
  return `${API_BASE}/analysis/${jobId}/click-track${params}`;
}

export function getJsonDownloadUrl(jobId: string): string {
  return `${API_BASE}/analysis/${jobId}/json`;
}

export function getVisualizeUrl(jobId: string): string {
  return `${API_BASE}/visualize/${jobId}`;
}

export async function getWaveformData(
  jobId: string,
  resolution = 2000
): Promise<WaveformData> {
  const res = await fetch(`${API_BASE}/analysis/${jobId}/waveform?resolution=${resolution}`);
  if (!res.ok) throw new Error('Failed to fetch waveform data');
  return res.json();
}

export async function getHapticTimeline(
  jobId: string,
  configUpdate?: Record<string, unknown>
): Promise<HapticTimeline> {
  const res = await fetch(`${API_BASE}/analysis/${jobId}/haptic`, {
    method: 'POST',
    headers: configUpdate ? { 'Content-Type': 'application/json' } : undefined,
    body: configUpdate ? JSON.stringify(configUpdate) : undefined,
  });
  if (!res.ok) throw new Error('Failed to generate haptic timeline');
  return res.json();
}

export async function getPresets(): Promise<{ presets: string[] }> {
  const res = await fetch(`${API_BASE}/presets`);
  if (!res.ok) throw new Error('Failed to fetch presets');
  return res.json();
}

export async function getLoudnessProfile(
  jobId: string
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/analysis/${jobId}/loudness`);
  if (!res.ok) throw new Error('Failed to fetch loudness profile');
  return res.json();
}

// --- Library endpoints ---

export interface LibrarySong {
  id: number;
  filename: string;
  file_hash: string;
  file_size: number;
  duration_seconds: number | null;
  analysis_mode: string;
  has_analysis: boolean;
  created_at: string | null;
  last_played: string | null;
}

export interface LibraryPreset {
  id: number;
  name: string;
  description: string | null;
  config: Record<string, unknown>;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export async function fetchLibrarySongs(): Promise<LibrarySong[]> {
  const res = await fetch(`${API_BASE}/library/songs`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch songs");
  const data = await res.json();
  return data.songs;
}

export async function saveSongToLibrary(
  file: File,
  mode: string = "music"
): Promise<{ song_id: number; file_hash: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/library/songs?mode=${mode}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to save song");
  return res.json();
}

export async function deleteLibrarySong(songId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/library/songs/${songId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete song");
}

export async function markSongPlayed(songId: number): Promise<void> {
  await fetch(`${API_BASE}/library/songs/${songId}/play`, {
    method: "POST",
    credentials: "include",
  });
}

export async function fetchLibraryPresets(): Promise<LibraryPreset[]> {
  const res = await fetch(`${API_BASE}/library/presets`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch presets");
  const data = await res.json();
  return data.presets;
}

export async function savePresetToLibrary(
  name: string,
  config: Record<string, unknown>,
  description?: string
): Promise<{ preset_id: number }> {
  const params = new URLSearchParams({ name });
  if (description) params.set("description", description);
  const res = await fetch(`${API_BASE}/library/presets?${params}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save preset");
  return res.json();
}

export async function deleteLibraryPreset(presetId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/library/presets/${presetId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete preset");
}
