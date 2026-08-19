'use client';

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Play, Pause, SkipBack } from 'lucide-react';
import { getClickTrackUrl, getOriginalAudioUrl } from '@/lib/api';
import { HapticController } from '@/lib/haptic-controller';

interface PlaybackControlsProps {
  jobId: string;
  duration: number;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  hapticController?: HapticController | null;
}

type TrackMode = 'original' | 'beats' | 'multi';

export default function PlaybackControls({
  jobId,
  duration,
  currentTime,
  onTimeUpdate,
  hapticController,
}: PlaybackControlsProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [mode, setMode] = useState<TrackMode>('beats');
  const initializedRef = useRef(false);

  const audioSrc = useMemo(() => {
    if (mode === 'original') return getOriginalAudioUrl(jobId);
    return getClickTrackUrl(jobId, mode === 'multi');
  }, [jobId, mode]);

  // Set audio source on mount or mode change
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;
    if (!initializedRef.current) {
      audio.src = audioSrc;
      initializedRef.current = true;
    }
  }, [audioSrc]);

  // Time updates
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handler = () => onTimeUpdate(audio.currentTime);
    audio.addEventListener('timeupdate', handler);
    return () => audio.removeEventListener('timeupdate', handler);
  }, [onTimeUpdate]);

  // Audio event bridge to haptic controller
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !hapticController) return;

    const handlePlay = () => {
      setPlaying(true);
      hapticController.play(audio.currentTime, () => audio.currentTime);
    };

    const handlePause = () => {
      setPlaying(false);
      hapticController.pause();
    };

    const handleEnded = () => {
      setPlaying(false);
      hapticController.stop();
    };

    const handleSeeking = () => {
      hapticController.pause();
    };

    const handleSeeked = () => {
      if (!audio.paused) {
        hapticController.seek(audio.currentTime);
        hapticController.play(audio.currentTime, () => audio.currentTime);
      } else {
        hapticController.seek(audio.currentTime);
      }
    };

    const handleWaiting = () => {
      hapticController.pause();
    };

    const handleStalled = () => {
      hapticController.pause();
    };

    const handleError = () => {
      setPlaying(false);
      hapticController.stop();
    };

    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('seeking', handleSeeking);
    audio.addEventListener('seeked', handleSeeked);
    audio.addEventListener('waiting', handleWaiting);
    audio.addEventListener('stalled', handleStalled);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('seeking', handleSeeking);
      audio.removeEventListener('seeked', handleSeeked);
      audio.removeEventListener('waiting', handleWaiting);
      audio.removeEventListener('stalled', handleStalled);
      audio.removeEventListener('error', handleError);
    };
  }, [hapticController]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;

    if (audio.paused) {
      audio.play().catch(() => {
        setPlaying(false);
      });
    } else {
      audio.pause();
    }
  }, [audioSrc]);

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    onTimeUpdate(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  }, [onTimeUpdate]);

  const handleRestart = useCallback(() => {
    onTimeUpdate(0);
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
    }
  }, [onTimeUpdate]);

  const handleModeChange = useCallback((newMode: TrackMode) => {
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      audio.pause();
    }
    setMode(newMode);
    initializedRef.current = false;
  }, []);

  const formatTime = (t: number) => {
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    const ms = Math.floor((t % 1) * 100);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
  };

  const modes: { label: string; value: TrackMode }[] = [
    { label: 'Original', value: 'original' },
    { label: 'Beat', value: 'beats' },
    { label: 'Beat + Bass', value: 'multi' },
  ];

  return (
    <div className="panel px-4 py-3">
      <audio ref={audioRef} preload="auto" />
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          Diagnostic Playback
        </span>
        <div className="flex items-center gap-px" style={{ background: 'var(--border)' }}>
          {modes.map((m) => (
            <button
              key={m.value}
              onClick={() => handleModeChange(m.value)}
              className="px-2 py-1 text-xs"
              style={{
                background: mode === m.value ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                color: mode === m.value ? 'var(--text-primary)' : 'var(--text-muted)',
                fontFamily: 'var(--font-geist-mono)',
              }}
              aria-pressed={mode === m.value}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
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
