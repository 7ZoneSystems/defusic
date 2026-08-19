'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Pause, SkipBack, Volume2 } from 'lucide-react';
import { getOriginalAudioUrl, getDiagnosticAudioUrl } from '@/lib/api';
import { DiagnosticLayer, AnalysisMode } from '@/lib/types';

interface DiagnosticPlayerProps {
  jobId: string;
  duration: number;
  mode: AnalysisMode;
  layers: DiagnosticLayer[];
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  onLayerToggle: (layerId: string) => void;
  originalVolume: number;
  diagnosticVolume: number;
  onOriginalVolumeChange: (v: number) => void;
  onDiagnosticVolumeChange: (v: number) => void;
}

export default function DiagnosticPlayer({
  jobId,
  duration,
  layers,
  currentTime,
  onTimeUpdate,
  onLayerToggle,
  originalVolume,
  diagnosticVolume,
  onOriginalVolumeChange,
  onDiagnosticVolumeChange,
}: DiagnosticPlayerProps) {
  const originalRef = useRef<HTMLAudioElement>(null);
  const diagnosticRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [syncSource, setSyncSource] = useState<'original' | 'diagnostic' | null>(null);

  const activeLayers = layers.filter((l) => l.enabled).map((l) => l.id);
  const diagnosticUrl = getDiagnosticAudioUrl(jobId, activeLayers);
  const originalUrl = getOriginalAudioUrl(jobId);

  // Sync volumes
  useEffect(() => {
    if (originalRef.current) originalRef.current.volume = originalVolume;
  }, [originalVolume]);

  useEffect(() => {
    if (diagnosticRef.current) diagnosticRef.current.volume = diagnosticVolume;
  }, [diagnosticVolume]);

  // Sync time updates from both elements
  const handleOriginalTimeUpdate = useCallback(() => {
    const audio = originalRef.current;
    if (!audio) return;
    onTimeUpdate(audio.currentTime);

    // Sync diagnostic to original
    if (diagnosticRef.current && syncSource !== 'diagnostic') {
      const diag = diagnosticRef.current;
      if (Math.abs(diag.currentTime - audio.currentTime) > 0.1) {
        diag.currentTime = audio.currentTime;
      }
    }
  }, [onTimeUpdate, syncSource]);

  const handleDiagnosticTimeUpdate = useCallback(() => {
    const audio = diagnosticRef.current;
    if (!audio) return;
    onTimeUpdate(audio.currentTime);

    // Sync original to diagnostic
    if (originalRef.current && syncSource !== 'original') {
      const orig = originalRef.current;
      if (Math.abs(orig.currentTime - audio.currentTime) > 0.1) {
        orig.currentTime = audio.currentTime;
      }
    }
  }, [onTimeUpdate, syncSource]);

  useEffect(() => {
    const orig = originalRef.current;
    const diag = diagnosticRef.current;
    if (!orig || !diag) return;

    orig.addEventListener('timeupdate', handleOriginalTimeUpdate);
    diag.addEventListener('timeupdate', handleDiagnosticTimeUpdate);

    return () => {
      orig.removeEventListener('timeupdate', handleOriginalTimeUpdate);
      diag.removeEventListener('timeupdate', handleDiagnosticTimeUpdate);
    };
  }, [handleOriginalTimeUpdate, handleDiagnosticTimeUpdate]);

  const togglePlay = () => {
    const orig = originalRef.current;
    const diag = diagnosticRef.current;
    if (!orig || !diag) return;

    if (playing) {
      orig.pause();
      diag.pause();
    } else {
      setSyncSource('original');
      orig.play().catch(() => {});
      diag.play().catch(() => {});
    }
    setPlaying(!playing);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    onTimeUpdate(time);
    if (originalRef.current) originalRef.current.currentTime = time;
    if (diagnosticRef.current) diagnosticRef.current.currentTime = time;
  };

  const handleRestart = () => {
    onTimeUpdate(0);
    if (originalRef.current) originalRef.current.currentTime = 0;
    if (diagnosticRef.current) diagnosticRef.current.currentTime = 0;
  };

  const formatTime = (t: number) => {
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    const ms = Math.floor((t % 1) * 100);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
  };

  return (
    <div className="panel px-4 py-3">
      <audio ref={originalRef} preload="auto" src={originalUrl} crossOrigin="anonymous" />
      <audio ref={diagnosticRef} preload="auto" src={diagnosticUrl} crossOrigin="anonymous" />

      {/* Layer selection */}
      <div className="flex items-center justify-between mb-3">
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          Layers
        </span>
        <div className="flex items-center gap-1">
          {layers.map((layer) => (
            <button
              key={layer.id}
              onClick={() => onLayerToggle(layer.id)}
              className="px-2 py-1 text-xs"
              style={{
                background: layer.enabled ? `${layer.color}20` : 'var(--bg-panel)',
                color: layer.enabled ? layer.color : 'var(--text-muted)',
                border: `1px solid ${layer.enabled ? layer.color : 'var(--border)'}`,
                borderRadius: '2px',
                fontFamily: 'var(--font-geist-mono)',
              }}
              aria-pressed={layer.enabled}
            >
              {layer.label}
            </button>
          ))}
        </div>
      </div>

      {/* Volume controls */}
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div className="flex items-center gap-2">
          <Volume2 size={12} style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs w-14" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
            Original
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={originalVolume}
            onChange={(e) => onOriginalVolumeChange(parseFloat(e.target.value))}
            className="flex-1"
            aria-label="Original volume"
          />
          <span className="text-xs w-8 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
            {Math.round(originalVolume * 100)}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Volume2 size={12} style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs w-14" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
            Generated
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={diagnosticVolume}
            onChange={(e) => onDiagnosticVolumeChange(parseFloat(e.target.value))}
            className="flex-1"
            aria-label="Diagnostic volume"
          />
          <span className="text-xs w-8 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
            {Math.round(diagnosticVolume * 100)}%
          </span>
        </div>
      </div>

      {/* Transport controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleRestart}
          className="p-1.5"
          style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '2px' }}
          aria-label="Restart"
        >
          <SkipBack size={14} />
        </button>
        <button
          onClick={togglePlay}
          className="p-1.5"
          style={{
            color: 'var(--text-primary)',
            background: 'var(--accent-dim)',
            borderRadius: '2px',
          }}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}
        </button>
        <input
          type="range"
          min={0}
          max={duration}
          step={0.01}
          value={currentTime}
          onChange={handleSeek}
          className="flex-1"
          aria-label="Seek"
        />
        <span
          className="text-xs w-20 text-right"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          {formatTime(currentTime)}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>/</span>
        <span
          className="text-xs w-20"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          {formatTime(duration)}
        </span>
      </div>
    </div>
  );
}
