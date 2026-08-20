'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { AlertTriangle, FileAudio } from 'lucide-react';
import Header from '@/components/Header';
import TrackUpload from '@/components/TrackUpload';
import ModeSelector from '@/components/ModeSelector';
import MetricsStrip from '@/components/MetricsStrip';
import DrumMetricsStrip from '@/components/DrumMetricsStrip';
import Timeline from '@/components/Timeline';
import EventInspector from '@/components/EventInspector';
import DrumEventInspector from '@/components/DrumEventInspector';
import PlaybackControls from '@/components/PlaybackControls';
import DiagnosticPlayer from '@/components/DiagnosticPlayer';
import DualWaveform from '@/components/DualWaveform';
import DrumPatternView from '@/components/DrumPatternView';
import AnalysisProgress from '@/components/AnalysisProgress';
import HapticPanel from '@/components/HapticPanel';
import { analyzeFile, checkHealth, getHapticTimeline, getJsonDownloadUrl, getWaveformData } from '@/lib/api';
import { AnalysisResult, AnalysisMode, AppState, DiagnosticLayer, WaveformData } from '@/lib/types';
import { DRUM_LAYERS, MUSIC_LAYERS } from '@/lib/types';
import { HapticConfig, HapticEvent, HapticTimeline, DEFAULT_HAPTIC_CONFIG } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';
import { createHapticDriver } from '@/lib/haptic-driver';
import { persistFile, restoreFile, clearPersistedFile, getPersistedMeta } from '@/lib/file-persist';
import { useTheme } from '@/lib/theme';

/** Metadata about a selected file that survives in-memory (lightweight). */
interface SelectedFileMeta {
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

export default function Home() {
  const [state, setState] = useState<AppState>('idle');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [jobId, setJobId] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedMeta, setSelectedMeta] = useState<SelectedFileMeta | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [mode, setMode] = useState<AnalysisMode>('music');
  const [currentTime, setCurrentTime] = useState(0);
  const [engineStatus, setEngineStatus] = useState<'online' | 'offline' | 'analyzing'>('online');
  const { resolved } = useTheme();

  const [layers, setLayers] = useState<DiagnosticLayer[]>(
    mode === 'drumming' ? [...DRUM_LAYERS] : [...MUSIC_LAYERS]
  );
  const [originalVolume, setOriginalVolume] = useState(0.5);
  const [diagnosticVolume, setDiagnosticVolume] = useState(0.7);
  const [originalWaveform, setOriginalWaveform] = useState<WaveformData | null>(null);
  const [diagnosticWaveform, setDiagnosticWaveform] = useState<number[] | null>(null);

  // Haptic state
  const [hapticConfig, setHapticConfig] = useState<HapticConfig>(DEFAULT_HAPTIC_CONFIG);
  const [hapticTimeline, setHapticTimeline] = useState<HapticTimeline | null>(null);
  const [hapticLastEvent, setHapticLastEvent] = useState<HapticEvent | null>(null);
  const [hapticController, setHapticController] = useState<HapticController | null>(null);
  const [realHardware, setRealHardware] = useState(false);
  const hapticInitRef = useRef(false);

  // Initialize haptic driver once
  useEffect(() => {
    if (hapticInitRef.current) return;
    hapticInitRef.current = true;
    const driver = createHapticDriver();
    setRealHardware(driver.isReal);
    const ctrl = new HapticController(driver, {
      onEvent: (evt) => setHapticLastEvent(evt),
    });
    setHapticController(ctrl);
    return () => ctrl.destroy();
  }, []);

  // Restore file from IndexedDB on mount (after a potential reload).
  // Always finishes quickly — never blocks the UI.
  useEffect(() => {
    let active = true;

    async function tryRestore() {
      try {
        // Race each DB call against a short timeout so we never hang
        const meta = await Promise.race([
          getPersistedMeta(),
          new Promise<null>((r) => setTimeout(r, 500)),
        ]);

        if (!active || !meta) {
          if (active) setRestoring(false);
          return;
        }

        const file = await Promise.race([
          restoreFile(),
          new Promise<File | null>((r) => setTimeout(r, 500)),
        ]);

        if (!active) return;

        if (file) {
          setSelectedFile(file);
          setSelectedMeta({
            name: file.name,
            size: file.size,
            type: file.type,
            lastModified: file.lastModified,
          });
          setState('file_selected');
        } else {
          setSelectedMeta({
            name: meta.name,
            size: meta.size,
            type: meta.type,
            lastModified: meta.lastModified,
          });
          setError('File selection was interrupted. Please select the track again.');
          setState('error');
        }
      } catch {
        // IndexedDB unavailable or errored — proceed without restore
      }
      if (active) setRestoring(false);
    }

    tryRestore();
    return () => { active = false; };
  }, []);

  // Sync haptic enabled state with config
  useEffect(() => {
    if (hapticController) {
      hapticController.setEnabled(hapticConfig.master_intensity > 0);
    }
  }, [hapticConfig.master_intensity, hapticController]);

  // Sync haptic timeline when it changes (load only, do NOT auto-start)
  useEffect(() => {
    if (hapticController && hapticTimeline) {
      hapticController.load(hapticTimeline);
    }
  }, [hapticTimeline, hapticController]);

  // Haptic seek is handled by audio player components via hapticController.seek()

  // Load haptic timeline when analysis completes
  useEffect(() => {
    if (state !== 'complete' || !jobId) return;

    getWaveformData(jobId, 2000)
      .then(setOriginalWaveform)
      .catch(() => setOriginalWaveform(null));

    getHapticTimeline(jobId)
      .then(setHapticTimeline)
      .catch(() => setHapticTimeline(null));
  }, [state, jobId]);

  // Reload haptic timeline when config changes
  useEffect(() => {
    if (state !== 'complete' || !jobId) return;

    const timer = setTimeout(() => {
      getHapticTimeline(jobId, {
        preset: 'custom',
        master_intensity: hapticConfig.master_intensity,
        beat_intensity: hapticConfig.beat.intensity,
        beat_duration_ms: hapticConfig.beat.duration_ms,
        hihat_intensity: hapticConfig.hihat.intensity,
        hihat_duration_ms: hapticConfig.hihat.duration_ms,
        kick_intensity: hapticConfig.kick.intensity,
        kick_duration_ms: hapticConfig.kick.duration_ms,
        snare_intensity: hapticConfig.snare.intensity,
        snare_duration_ms: hapticConfig.snare.duration_ms,
        bass_intensity: hapticConfig.bass.intensity,
        bass_duration_ms: hapticConfig.bass.duration_ms,
        subbass_intensity: hapticConfig.subbass.intensity,
        subbass_duration_ms: hapticConfig.subbass.duration_ms,
        anticipation_enabled: hapticConfig.anticipation_enabled,
        adaptive_enabled: hapticConfig.adaptive_enabled,
        adaptive_gain_strength: hapticConfig.adaptive_gain_strength,
      })
        .then(setHapticTimeline)
        .catch(() => {});
    }, 300);

    return () => clearTimeout(timer);
  }, [hapticConfig, state, jobId]);

  const handleFileSelected = useCallback(async (file: File) => {
    // Persist to IndexedDB in the background — do NOT await, it may hang
    persistFile(file).catch(() => {});

    setSelectedFile(file);
    setSelectedMeta({
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
    });
    setState('file_selected');
    setError('');

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
      const job = await analyzeFile(selectedFile, mode);
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
  }, [selectedFile, mode]);

  const handleReset = useCallback(() => {
    setState('idle');
    setResult(null);
    setJobId('');
    setError('');
    setSelectedFile(null);
    setSelectedMeta(null);
    setCurrentTime(0);
    setOriginalWaveform(null);
    setDiagnosticWaveform(null);
    setHapticTimeline(null);
    hapticController?.stop();
    clearPersistedFile().catch(() => {});
  }, [hapticController]);

  const handleLayerToggle = useCallback((layerId: string) => {
    setLayers((prev) =>
      prev.map((l) => (l.id === layerId ? { ...l, enabled: !l.enabled } : l))
    );
  }, []);

  const isDrumming = result?.mode === 'drumming';

  // Determine what file info to display (prefer live File, fall back to persisted meta)
  const displayMeta = selectedFile
    ? { name: selectedFile.name, size: selectedFile.size }
    : selectedMeta
      ? { name: selectedMeta.name, size: selectedMeta.size }
      : null;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      <Header status={engineStatus} mode={result?.mode ?? null} />

      <main className="flex-1 flex flex-col">
        {/* Restore banner (shown briefly if IndexedDB had data) */}
        {state === 'idle' && restoring && selectedMeta && (
          <div className="px-4 py-2" style={{ background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
              Restoring previous session...
            </p>
          </div>
        )}

        {/* Upload Section — always visible in idle state */}
        {state === 'idle' && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg">
              <div className="mb-6 text-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={resolved === 'light' ? '/icon_light.png' : '/icon_dark.png'}
                  alt="HearBeat"
                  className="mx-auto mb-4 h-auto w-[clamp(112px,40vw,200px)] sm:w-[clamp(140px,35vw,260px)] md:w-[clamp(160px,28vw,300px)]"
                />
                <h1
                  className="text-lg font-semibold tracking-wider uppercase mb-2"
                  style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
                >
                  Analyze Track
                </h1>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Upload an audio or video file for analysis
                </p>
              </div>
              <TrackUpload onFileSelected={handleFileSelected} />
            </div>
          </div>
        )}

        {/* File Selected (live File object or restored metadata) */}
        {state === 'file_selected' && displayMeta && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-lg panel-elevated p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <FileAudio size={20} style={{ color: 'var(--accent)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                    {displayMeta.name}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {(displayMeta.size / (1024 * 1024)).toFixed(1)} MB
                  </p>
                </div>
              </div>

              {/* If no live File object, show re-select prompt */}
              {!selectedFile && (
                <div className="panel p-3" style={{ borderColor: 'var(--warning)' }}>
                  <p className="text-xs" style={{ color: 'var(--warning)' }}>
                    File data was lost. Please re-select the track to continue.
                  </p>
                </div>
              )}

              <ModeSelector
                selected={mode}
                onSelect={(m) => {
                  setMode(m);
                  setLayers(m === 'drumming' ? [...DRUM_LAYERS] : [...MUSIC_LAYERS]);
                }}
              />

              <div className="flex gap-2">
                <button
                  onClick={handleAnalyze}
                  disabled={!selectedFile}
                  className="flex-1 px-4 py-2 text-xs uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
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

              {!selectedFile && (
                <TrackUpload onFileSelected={handleFileSelected} />
              )}
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
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setError('');
                    setState('idle');
                  }}
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
                <span
                  className="text-xs px-1.5 py-0.5"
                  style={{
                    color: isDrumming ? 'var(--event-hihat)' : 'var(--accent)',
                    border: `1px solid ${isDrumming ? 'var(--event-hihat)' : 'var(--accent)'}`,
                    borderRadius: '2px',
                    fontFamily: 'var(--font-geist-mono)',
                  }}
                >
                  {isDrumming ? 'DRUMMING' : 'MUSIC'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {hapticTimeline && (
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {hapticTimeline.events.length} haptic events
                  </span>
                )}
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
            {isDrumming ? (
              <DrumMetricsStrip result={result} />
            ) : (
              <MetricsStrip result={result} />
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div
                className="px-4 py-2 flex items-start gap-2"
                style={{ background: 'color-mix(in srgb, var(--warning) 8%, transparent)', borderBottom: '1px solid var(--border)' }}
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
              {/* Dual waveform for drumming mode */}
              {isDrumming && jobId && (
                <DualWaveform
                  originalData={originalWaveform}
                  diagnosticData={diagnosticWaveform}
                  duration={result.source.duration_seconds}
                  currentTime={currentTime}
                  onSeek={setCurrentTime}
                  originalVolume={originalVolume}
                  diagnosticVolume={diagnosticVolume}
                />
              )}

              {/* Timeline */}
              <Timeline result={result} currentTime={currentTime} onSeek={setCurrentTime} />

              {/* Playback */}
              {jobId && isDrumming && (
                <DiagnosticPlayer
                  jobId={jobId}
                  duration={result.source.duration_seconds}
                  mode={result.mode}
                  layers={layers}
                  currentTime={currentTime}
                  onTimeUpdate={setCurrentTime}
                  onLayerToggle={handleLayerToggle}
                  originalVolume={originalVolume}
                  diagnosticVolume={diagnosticVolume}
                  onOriginalVolumeChange={setOriginalVolume}
                  onDiagnosticVolumeChange={setDiagnosticVolume}
                  hapticController={hapticController}
                />
              )}

              {jobId && !isDrumming && (
                <PlaybackControls
                  jobId={jobId}
                  duration={result.source.duration_seconds}
                  currentTime={currentTime}
                  onTimeUpdate={setCurrentTime}
                  hapticController={hapticController}
                />
              )}

              {/* Haptic Panel */}
              <HapticPanel
                controller={hapticController}
                realHardware={realHardware}
                lastEvent={hapticLastEvent}
                config={hapticConfig}
                onConfigChange={setHapticConfig}
              />

              {/* Drum pattern view (drumming mode) */}
              {isDrumming && result.drum_events_raw.length > 0 && (
                <DrumPatternView
                  drumEvents={result.drum_events_raw}
                  rhythm={result.rhythm}
                />
              )}

              {/* Event Inspector */}
              {isDrumming ? (
                <DrumEventInspector events={result.drum_events_raw} />
              ) : (
                <EventInspector events={result.events} />
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
