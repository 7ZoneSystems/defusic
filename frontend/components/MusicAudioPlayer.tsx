'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { Vibrate, Volume2, Save } from 'lucide-react';
import { getOriginalAudioUrl } from '@/lib/api';
import { HapticController } from '@/lib/haptic-controller';
import { useTheme } from '@/lib/theme';

interface MusicAudioPlayerProps {
  jobId: string;
  duration: number;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  hapticController?: HapticController | null;
  volume: number;
  onVolumeChange: (v: number) => void;
  onHapticSettingsClick: () => void;
  hapticEnabled: boolean;
  audioSrc?: string;
  saveState?: 'idle' | 'saving' | 'saved';
  onSave?: () => void;
}

function formatTime(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function MusicAudioPlayer({
  jobId,
  duration,
  currentTime,
  onTimeUpdate,
  hapticController,
  volume,
  onVolumeChange,
  onHapticSettingsClick,
  hapticEnabled,
  audioSrc: audioSrcProp,
  saveState = 'idle',
  onSave,
}: MusicAudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [pulse, setPulse] = useState(false);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const { resolved } = useTheme();
  useEffect(() => { onTimeUpdateRef.current = onTimeUpdate; });

  const audioSrc = audioSrcProp || getOriginalAudioUrl(jobId);

  const playImg = resolved === 'light' ? '/play_light.png' : '/play_dark.png';
  const pauseImg = resolved === 'light' ? '/pause_light.png' : '/pause_dark.png';

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !audioSrc) return;
    if (audio.src !== audioSrc && !audio.src.endsWith(audioSrc)) {
      audio.src = audioSrc;
      audio.volume = volume;
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
      setPulse(true);
      setTimeout(() => setPulse(false), 200);
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
    <div className="flex flex-col items-center gap-3 w-full" style={{ maxWidth: 'min(480px, 80vw)' }}>
      <audio ref={audioRef} preload="auto" />

      {/* Time + Progress */}
      <div className="flex items-center gap-3 w-full">
        <span
          className="text-xs text-right shrink-0 tabular-nums"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '36px' }}
        >
          {formatTime(currentTime)}
        </span>

        <input
          type="range"
          min={0}
          max={duration}
          step={0.01}
          value={currentTime}
          onChange={handleSeek}
          className="flex-1 min-w-0"
          style={{ height: 4, accentColor: 'var(--gold)' }}
          aria-label="Seek"
        />

        <span
          className="text-xs shrink-0 tabular-nums"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '36px' }}
        >
          {formatTime(duration)}
        </span>
      </div>

      {/* Controls row: volume | play | haptics */}
      <div className="flex items-center justify-center w-full relative">
        {/* Volume — left */}
        <div className="flex items-center gap-1.5 shrink-0 absolute" style={{ left: '16px' }}>
          <Volume2 size={14} style={{ color: 'var(--text-muted)' }} />
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
            className="w-20"
            style={{ height: 3, accentColor: 'var(--gold)' }}
            aria-label="Song volume"
          />
        </div>

        {/* Play/Pause — large centered */}
        <button
          onClick={togglePlay}
          className="flex items-center justify-center"
          style={{
            width: 100,
            height: 100,
            background: 'none',
            border: 'none',
            borderRadius: '2px',
            transition: 'transform 180ms ease',
            transform: pulse ? 'scale(1.06)' : 'scale(1)',
            padding: 0,
          }}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={playing ? pauseImg : playImg}
            alt=""
            style={{
              width: 64,
              height: 64,
              objectFit: 'contain',
              transition: 'opacity 150ms ease',
            }}
          />
        </button>

        {/* Save — right of center */}
        {onSave && (
          <button
            onClick={onSave}
            disabled={saveState === 'saving'}
            className="p-2 flex items-center justify-center shrink-0 absolute"
            style={{
              right: '56px',
              color: saveState === 'saved' ? 'var(--success)' : 'var(--text-muted)',
              border: saveState === 'saved' ? '1px solid var(--success)' : '1px solid var(--border)',
              background: saveState === 'saved' ? 'color-mix(in srgb, var(--success) 12%, transparent)' : 'transparent',
              borderRadius: '2px',
              transition: 'border-color 180ms ease, color 180ms ease, background-color 180ms ease',
            }}
            aria-label={saveState === 'saved' ? 'Saved' : 'Save song'}
            title={saveState === 'saved' ? 'Saved to library' : 'Save to library'}
          >
            <Save size={16} />
          </button>
        )}

        {/* Haptic settings — right */}
        <button
          onClick={onHapticSettingsClick}
          className="p-2 flex items-center justify-center shrink-0 absolute"
          style={{
            right: '16px',
            color: hapticEnabled ? 'var(--success)' : 'var(--text-muted)',
            border: '1px solid var(--border)',
            borderRadius: '2px',
            transition: 'border-color 180ms ease',
          }}
          aria-label="Haptic settings"
        >
          <Vibrate size={16} />
        </button>
      </div>
    </div>
  );
}
