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

function formatTime(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
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
      audio.play().catch(() => {});
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

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 shrink-0"
      style={{
        background: 'var(--bg-surface)',
        borderTop: '1px solid var(--border)',
      }}
    >
      <audio ref={audioRef} preload="auto" />

      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        className="p-2 flex items-center justify-center"
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
        className="text-xs w-20 text-right shrink-0"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
      >
        {formatTime(currentTime)}
      </span>

      {/* Progress */}
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

      {/* Duration */}
      <span
        className="text-xs w-20 shrink-0"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
      >
        {formatTime(duration)}
      </span>

      {/* Volume */}
      <div className="flex items-center gap-1.5 shrink-0">
        <Volume2 size={14} style={{ color: 'var(--text-muted)' }} />
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
          className="w-20"
          aria-label="Song volume"
        />
      </div>

      {/* Haptic settings button */}
      <button
        onClick={onHapticSettingsClick}
        className="p-1.5 flex items-center justify-center"
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
