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
  drive_file_id: string | null;
  analysis_drive_file_id: string | null;
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

export async function saveSongAnalysis(
  file: File,
  analysisJson: string,
  mode: string = "music",
  filename: string = ""
): Promise<{ song_id: number; file_hash: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("analysis_json", analysisJson);
  form.append("mode", mode);
  form.append("filename", filename || file.name);
  const res = await fetch(`${API_BASE}/library/songs/save-analysis`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to save song");
  }
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

// --- Google Drive endpoints ---

export async function getDriveStatus(): Promise<{
  connected: boolean;
  has_songs: boolean;
  folder_id: string | null;
  songs_folder_id: string | null;
  connection_file_id: string | null;
}> {
  const res = await fetch(`${API_BASE}/drive/status`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to check Drive status");
  return res.json();
}

export async function exchangeDriveCode(code: string): Promise<{
  status: string;
  folder_id: string;
  songs_folder_id: string;
  connection_file_id: string;
}> {
  const res = await fetch(`${API_BASE}/drive/exchange?code=${encodeURIComponent(code)}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to exchange Drive code");
  return res.json();
}

export async function disconnectDrive(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/drive/disconnect`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to disconnect Drive");
  return res.json();
}

export async function uploadToDrive(file: File): Promise<{ drive_file_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/drive/upload`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to upload to Drive");
  return res.json();
}

export function getDriveDownloadUrl(fileId: string): string {
  return `${API_BASE}/drive/download/${fileId}`;
}

export async function deleteDriveFile(fileId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/drive/file/${fileId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete from Drive");
  return res.json();
}

// --- Drive songs listing ---

export interface DriveSongFile {
  id: string;
  name: string;
  size: string;
  mimeType: string;
  createdTime: string;
}

export async function listDriveSongs(): Promise<DriveSongFile[]> {
  const res = await fetch(`${API_BASE}/drive/songs`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to list Drive songs");
  const data = await res.json();
  return data.songs;
}

export async function analyzeDriveSong(
  fileId: string,
  mode: string = "music"
): Promise<{ song_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/drive/analyze/${encodeURIComponent(fileId)}?mode=${mode}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to analyze Drive song");
  return res.json();
}

// --- Library analysis retrieval ---

export interface LibrarySongAnalysis {
  song_id: number;
  filename: string;
  file_hash: string;
  duration_seconds: number | null;
  analysis_mode: string;
  drive_file_id: string | null;
  analysis_drive_file_id: string | null;
  analysis: Record<string, unknown>;
}

export async function getLibrarySongAnalysis(songId: number): Promise<LibrarySongAnalysis> {
  const res = await fetch(`${API_BASE}/library/songs/${songId}/analysis`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch analysis");
  return res.json();
}

export async function reprocessLibrarySong(
  songId: number,
  mode?: string
): Promise<{ song_id: number; status: string }> {
  const params = mode ? `?mode=${mode}` : "";
  const res = await fetch(`${API_BASE}/library/songs/${songId}/reprocess${params}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to reprocess song");
  return res.json();
}
