'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { Play, Pause, Vibrate, Volume2 } from 'lucide-react';
import { getOriginalAudioUrl } from '@/lib/api';
import { HapticController } from '@/lib/haptic-controller';

interface MusicPlayerBarProps {
  jobId: string;
  duration: number;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  hapticController?: HapticController | null;
  volume: number;
  onVolumeChange: (v: number) => void;
  onHapticSettingsClick: () => void;
  hapticEnabled: boolean;
}

function formatTime(t: number, compact: boolean) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  if (compact) return `${m}:${String(s).padStart(2, '0')}`;
  const ms = Math.floor((t % 1) * 100);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

export default function MusicPlayerBar({
  jobId,
  duration,
  currentTime,
  onTimeUpdate,
  hapticController,
  volume,
  onVolumeChange,
  onHapticSettingsClick,
  hapticEnabled,
}: MusicPlayerBarProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const initializedRef = useRef(false);
  const [playing, setPlaying] = useState(false);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => { onTimeUpdateRef.current = onTimeUpdate; });

  const audioSrc = getOriginalAudioUrl(jobId);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;
    if (!initializedRef.current) {
      audio.src = audioSrc;
      audio.volume = volume;
      initializedRef.current = true;
    }
  }, [audioSrc, volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.volume = volume;
  }, [volume]);

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
    const handleSeeking = () => hapticController.pause();
    const handleSeeked = () => {
      if (!audio.paused) {
        hapticController.seek(audio.currentTime);
        hapticController.play(audio.currentTime, () => audio.currentTime);
      } else {
        hapticController.seek(audio.currentTime);
      }
    };
    const handleWaiting = () => hapticController.pause();
    const handleStalled = () => hapticController.pause();
    const handleError = () => {
      setPlaying(false);
      hapticController.stop();
    };
    const handleTimeUpdate = () => onTimeUpdateRef.current(audio.currentTime);

    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('seeking', handleSeeking);
    audio.addEventListener('seeked', handleSeeked);
    audio.addEventListener('waiting', handleWaiting);
    audio.addEventListener('stalled', handleStalled);
    audio.addEventListener('error', handleError);
    audio.addEventListener('timeupdate', handleTimeUpdate);

    return () => {
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('seeking', handleSeeking);
      audio.removeEventListener('seeked', handleSeeked);
      audio.removeEventListener('waiting', handleWaiting);
      audio.removeEventListener('stalled', handleStalled);
      audio.removeEventListener('error', handleError);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [hapticController]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;
    if (audio.paused) {
      audio.play().catch(() => {});
    } else {
      audio.pause();
    }
  }, [audioSrc]);

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    onTimeUpdateRef.current(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  }, []);

  return (
    <div
      className="flex items-center gap-2 px-3 py-2.5 shrink-0"
      style={{
        background: 'var(--bg-surface)',
        borderTop: '1px solid var(--border)',
        boxSizing: 'border-box',
        width: '100%',
        maxWidth: '100vw',
        overflowX: 'hidden',
      }}
    >
      <audio ref={audioRef} preload="auto" />

      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        className="shrink-0 p-2 flex items-center justify-center"
        style={{
          color: 'var(--text-primary)',
          background: 'var(--accent-dim)',
          borderRadius: '2px',
          border: '1px solid var(--accent)',
        }}
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? <Pause size={16} /> : <Play size={16} />}
      </button>

      {/* Current time */}
      <span
        className="text-xs text-right shrink-0 hidden sm:inline"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '64px' }}
      >
        {formatTime(currentTime, false)}
      </span>
      <span
        className="text-xs text-right shrink-0 sm:hidden"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '36px' }}
      >
        {formatTime(currentTime, true)}
      </span>

      {/* Progress — the only flexible element */}
      <input
        type="range"
        min={0}
        max={duration}
        step={0.01}
        value={currentTime}
        onChange={handleSeek}
        className="flex-1 min-w-0"
        style={{ width: 0 }}
        aria-label="Seek"
      />

      {/* Duration */}
      <span
        className="text-xs shrink-0 hidden sm:inline"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '64px' }}
      >
        {formatTime(duration, false)}
      </span>
      <span
        className="text-xs shrink-0 sm:hidden"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '36px' }}
      >
        {formatTime(duration, true)}
      </span>

      {/* Volume */}
      <div className="flex items-center gap-1 shrink-0">
        <Volume2 size={12} style={{ color: 'var(--text-muted)' }} />
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
          className="w-16 sm:w-20"
          aria-label="Song volume"
        />
      </div>

      {/* Haptic settings button */}
      <button
        onClick={onHapticSettingsClick}
        className="shrink-0 p-1.5 flex items-center justify-center"
        style={{
          color: hapticEnabled ? 'var(--success)' : 'var(--text-muted)',
          border: '1px solid var(--border)',
          borderRadius: '2px',
        }}
        aria-label="Haptic settings"
      >
        <Vibrate size={14} />
      </button>
    </div>
  );
}
