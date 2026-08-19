import { AnalysisJob } from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error('Backend unavailable');
  return res.json();
}

export async function analyzeFile(file: File): Promise<AnalysisJob> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_URL}/analyze`, { method: 'POST', body: form });
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
