'use client';

import { useState, useCallback } from 'react';
import { AlertTriangle, FileAudio } from 'lucide-react';
import Header from '@/components/Header';
import TrackUpload from '@/components/TrackUpload';
import MetricsStrip from '@/components/MetricsStrip';
import Timeline from '@/components/Timeline';
import EventInspector from '@/components/EventInspector';
import JsonInspector from '@/components/JsonInspector';
import PlaybackControls from '@/components/PlaybackControls';
import AnalysisProgress from '@/components/AnalysisProgress';
import { analyzeFile, checkHealth, getJsonDownloadUrl } from '@/lib/api';
import { AnalysisResult, AppState } from '@/lib/types';

export default function Home() {
  const [state, setState] = useState<AppState>('idle');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [jobId, setJobId] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [engineStatus, setEngineStatus] = useState<'online' | 'offline' | 'analyzing'>('online');

  const handleFileSelected = useCallback(async (file: File) => {
    setSelectedFile(file);
    setState('file_selected');
    setError('');

    // Check backend health
    try {
      await checkHealth();
    } catch {
      setEngineStatus('offline');
      setError('Backend is not available. Start the backend server first.');
      setState('error');
      return;
    }
    setEngineStatus('online');
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!selectedFile) return;
    setState('analyzing');
    setEngineStatus('analyzing');
    setError('');

    try {
      const job = await analyzeFile(selectedFile);
      setJobId(job.job_id);

      if (job.status === 'completed' && job.result) {
        setResult(job.result);
        setState('complete');
        setEngineStatus('online');
      } else if (job.status === 'failed') {
        setError(job.error || 'Analysis failed');
        setState('error');
        setEngineStatus('online');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setState('error');
      setEngineStatus('online');
    }
  }, [selectedFile]);

  const handleReset = useCallback(() => {
    setState('idle');
    setResult(null);
    setJobId('');
    setError('');
    setSelectedFile(null);
    setCurrentTime(0);
  }, []);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <Header status={engineStatus} />

      <main className="flex-1 flex flex-col">
        {/* Upload Section */}
        {state === 'idle' && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg">
              <div className="mb-6 text-center">
                <h1
                  className="text-lg font-semibold tracking-wider uppercase mb-2"
                  style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
                >
                  Analyze Track
                </h1>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Upload an audio or video file for beat and bass analysis
                </p>
              </div>
              <TrackUpload onFileSelected={handleFileSelected} />
            </div>
          </div>
        )}

        {/* File Selected */}
        {state === 'file_selected' && selectedFile && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg panel-elevated p-6">
              <div className="flex items-center gap-3 mb-4">
                <FileAudio size={20} style={{ color: 'var(--accent)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                    {selectedFile.name}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAnalyze}
                  className="flex-1 px-4 py-2 text-xs uppercase tracking-wider"
                  style={{
                    background: 'var(--accent-dim)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--accent)',
                    borderRadius: '2px',
                    fontFamily: 'var(--font-geist-mono)',
                  }}
                >
                  Analyze track
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 text-xs uppercase tracking-wider"
                  style={{
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border)',
                    borderRadius: '2px',
                    fontFamily: 'var(--font-geist-mono)',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Analyzing */}
        {state === 'analyzing' && (
          <div className="flex-1 flex items-center justify-center p-8">
            <AnalysisProgress />
          </div>
        )}

        {/* Error */}
        {state === 'error' && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg panel-elevated p-6">
              <div className="flex items-center gap-3 mb-4">
                <AlertTriangle size={20} style={{ color: 'var(--danger)' }} />
                <span className="text-sm" style={{ color: 'var(--danger)' }}>Analysis Error</span>
              </div>
              <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>{error}</p>
              <button
                onClick={handleReset}
                className="px-4 py-2 text-xs uppercase tracking-wider"
                style={{
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: '2px',
                  fontFamily: 'var(--font-geist-mono)',
                }}
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {/* Analysis Workspace */}
        {state === 'complete' && result && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Track info bar */}
            <div
              className="panel flex items-center justify-between px-4 py-2"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileAudio size={14} style={{ color: 'var(--accent)' }} />
                <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                  {result.source.filename}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {result.source.duration_seconds.toFixed(1)}s / {result.source.sample_rate} Hz
                </span>
              </div>
              <div className="flex items-center gap-2">
                {result.warnings.length > 0 && (
                  <span className="text-xs" style={{ color: 'var(--warning)' }}>
                    {result.warnings.length} warning{result.warnings.length > 1 ? 's' : ''}
                  </span>
                )}
                {jobId && (
                  <a
                    href={getJsonDownloadUrl(jobId)}
                    className="px-2 py-1 text-xs"
                    style={{
                      color: 'var(--text-muted)',
                      border: '1px solid var(--border)',
                      borderRadius: '2px',
                      fontFamily: 'var(--font-geist-mono)',
                      textDecoration: 'none',
                    }}
                  >
                    JSON
                  </a>
                )}
                <button
                  onClick={handleReset}
                  className="px-2 py-1 text-xs"
                  style={{
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border)',
                    borderRadius: '2px',
                    fontFamily: 'var(--font-geist-mono)',
                  }}
                >
                  New track
                </button>
              </div>
            </div>

            {/* Metrics */}
            <MetricsStrip result={result} />

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div
                className="px-4 py-2 flex items-start gap-2"
                style={{ background: 'rgba(206, 158, 74, 0.08)', borderBottom: '1px solid var(--border)' }}
              >
                <AlertTriangle size={12} style={{ color: 'var(--warning)', marginTop: '2px' }} />
                <div className="flex-1">
                  {result.warnings.map((w, i) => (
                    <p key={i} className="text-xs" style={{ color: 'var(--warning)' }}>{w}</p>
                  ))}
                </div>
              </div>
            )}

            {/* Main content area */}
            <div className="flex-1 overflow-auto p-4 flex flex-col gap-4">
              {/* Timeline */}
              <Timeline result={result} currentTime={currentTime} onSeek={setCurrentTime} />

              {/* Playback */}
              {jobId && (
                <PlaybackControls
                  jobId={jobId}
                  duration={result.source.duration_seconds}
                  currentTime={currentTime}
                  onTimeUpdate={setCurrentTime}
                />
              )}

              {/* Event Inspector */}
              <EventInspector events={result.events} />

              {/* JSON Inspector */}
              <JsonInspector result={result} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
