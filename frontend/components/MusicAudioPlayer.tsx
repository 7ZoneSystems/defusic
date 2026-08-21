'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { Vibrate, Volume2, Save, Check, Loader2, SkipBack, SkipForward, ChevronUp } from 'lucide-react';
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
  onPrevious?: () => void;
  onNext?: () => void;
  hasPrevious?: boolean;
  hasNext?: boolean;
  onOpenQueue?: () => void;
  queueLength?: number;
  onEnded?: () => void;
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
  onPrevious,
  onNext,
  hasPrevious = false,
  hasNext = false,
  onOpenQueue,
  queueLength = 0,
  onEnded,
}: MusicAudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [pulse, setPulse] = useState(false);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const onEndedRef = useRef(onEnded);
  const playerTouchStartY = useRef<number | null>(null);
  const { resolved } = useTheme();

  useEffect(() => { onTimeUpdateRef.current = onTimeUpdate; });
  useEffect(() => { onEndedRef.current = onEnded; });

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
      if (onEndedRef.current) {
        onEndedRef.current();
      }
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

  const handleTouchStart = (e: React.TouchEvent) => {
    playerTouchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (playerTouchStartY.current === null) return;
    const deltaY = e.changedTouches[0].clientY - playerTouchStartY.current;
    playerTouchStartY.current = null;
    if (deltaY < -45 && onOpenQueue) {
      onOpenQueue();
    }
  };

  return (
    <div
      className="flex flex-col items-center gap-2.5 w-full select-none"
      style={{ maxWidth: 'min(480px, 94vw)' }}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <audio ref={audioRef} preload="auto" />

      {/* Time + Progress */}
      <div className="flex items-center gap-2.5 w-full">
        <span
          className="text-xs text-right shrink-0 tabular-nums"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '34px' }}
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
          className="flex-1 min-w-0 cursor-pointer"
          style={{ height: 4, accentColor: 'var(--gold)' }}
          aria-label="Seek"
        />

        <span
          className="text-xs shrink-0 tabular-nums"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', width: '34px' }}
        >
          {formatTime(duration)}
        </span>
      </div>

      {/* Controls row: Volume | Previous - Play - Next | Save | Haptics */}
      <div className="flex items-center justify-between w-full px-0.5 relative">
        {/* Left: Volume slider */}
        <div className="flex items-center gap-1 shrink-0">
          <Volume2 size={13} style={{ color: 'var(--text-muted)' }} />
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
            className="w-12 sm:w-16 md:w-20 cursor-pointer"
            style={{ height: 3, accentColor: 'var(--gold)' }}
            aria-label="Song volume"
          />
        </div>

        {/* Center: Previous / Play-Pause / Next */}
        <div className="flex items-center gap-0.5 sm:gap-1.5 shrink-0">
          {/* Previous Button */}
          {onPrevious && (
            <button
              onClick={onPrevious}
              disabled={!hasPrevious}
              className="p-1.5 sm:p-2 rounded-full transition-all flex items-center justify-center hover:bg-accent/10 disabled:opacity-25 disabled:cursor-not-allowed"
              style={{
                color: hasPrevious ? 'var(--text-primary)' : 'var(--text-muted)',
              }}
              aria-label="Previous song"
              title="Previous song"
            >
              <SkipBack size={17} />
            </button>
          )}

          {/* Main Play/Pause Button */}
          <button
            onClick={togglePlay}
            className="flex items-center justify-center"
            style={{
              width: 76,
              height: 76,
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
                width: 52,
                height: 52,
                objectFit: 'contain',
                transition: 'opacity 150ms ease',
              }}
            />
          </button>

          {/* Next Button */}
          {onNext && (
            <button
              onClick={onNext}
              disabled={!hasNext}
              className="p-1.5 sm:p-2 rounded-full transition-all flex items-center justify-center hover:bg-accent/10 disabled:opacity-25 disabled:cursor-not-allowed"
              style={{
                color: hasNext ? 'var(--text-primary)' : 'var(--text-muted)',
              }}
              aria-label="Next song"
              title="Next song"
            >
              <SkipForward size={17} />
            </button>
          )}
        </div>

        {/* Right: Save & Haptic buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Save Button */}
          {onSave && (
            <button
              onClick={onSave}
              disabled={saveState === 'saving'}
              className="p-1.5 sm:p-2 flex items-center justify-center shrink-0"
              style={{
                color: saveState === 'saved'
                  ? 'var(--success)'
                  : saveState === 'saving'
                    ? 'var(--accent)'
                    : 'var(--text-muted)',
                border: saveState === 'saved'
                  ? '1px solid var(--success)'
                  : saveState === 'saving'
                    ? '1px solid var(--accent)'
                    : '1px solid var(--border)',
                background: saveState === 'saved'
                  ? 'color-mix(in srgb, var(--success) 12%, transparent)'
                  : saveState === 'saving'
                    ? 'color-mix(in srgb, var(--accent) 12%, transparent)'
                    : 'transparent',
                borderRadius: '2px',
                cursor: saveState === 'saving' ? 'not-allowed' : 'pointer',
                transition: 'border-color 180ms ease, color 180ms ease, background-color 180ms ease',
              }}
              aria-label={
                saveState === 'saved'
                  ? 'Saved'
                  : saveState === 'saving'
                    ? 'Saving song...'
                    : 'Save song'
              }
              title={
                saveState === 'saved'
                  ? 'Saved to library'
                  : saveState === 'saving'
                    ? 'Saving to library...'
                    : 'Save to library'
              }
            >
              {saveState === 'saving' ? (
                <Loader2 size={15} className="animate-spin" />
              ) : saveState === 'saved' ? (
                <Check size={15} />
              ) : (
                <Save size={15} />
              )}
            </button>
          )}

          {/* Haptic settings */}
          <button
            onClick={onHapticSettingsClick}
            className="p-1.5 sm:p-2 flex items-center justify-center shrink-0"
            style={{
              color: hapticEnabled ? 'var(--success)' : 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              transition: 'border-color 180ms ease',
            }}
            aria-label="Haptic settings"
            title="Haptic settings"
          >
            <Vibrate size={15} />
          </button>
        </div>
      </div>

      {/* Swipe-up / Queue trigger pill */}
      {onOpenQueue && (
        <button
          onClick={onOpenQueue}
          className="flex items-center gap-1.5 px-3.5 py-1 text-[11px] rounded-full transition-all hover:bg-accent/15 mt-1 border select-none hover:border-accent/40"
          style={{
            color: 'var(--text-muted)',
            borderColor: 'var(--border)',
            background: 'var(--bg-elevated)',
            fontFamily: 'var(--font-geist-mono)',
          }}
          aria-label="Open saved songs"
        >
          <ChevronUp size={12} />
          <span>Saved Songs {queueLength > 0 ? `(${queueLength})` : ''}</span>
        </button>
      )}
    </div>
  );
}
