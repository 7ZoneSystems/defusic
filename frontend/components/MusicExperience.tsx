'use client';

import { useState, useCallback } from 'react';
import { HapticConfig, HapticEvent } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';
import { useTheme } from '@/lib/theme';
import HapticPowerVisualizer from '@/components/HapticPowerVisualizer';
import HapticResponseVisualizer from '@/components/HapticResponseVisualizer';
import RotaryKnob from '@/components/RotaryKnob';
import MusicAudioPlayer from '@/components/MusicAudioPlayer';
import HapticSettingsDialog from '@/components/HapticSettingsDialog';
import ThemeSwitcher from '@/components/ThemeSwitcher';

interface MusicExperienceProps {
  jobId: string;
  duration: number;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  onReset: () => void;
  hapticController: HapticController | null;
  realHardware: boolean;
  lastEvent: HapticEvent | null;
  hapticConfig: HapticConfig;
  onHapticConfigChange: (config: HapticConfig) => void;
  audioSrc?: string;
  saveState?: 'idle' | 'saving' | 'saved';
  onSave?: () => void;
}

export default function MusicExperience({
  jobId,
  duration,
  currentTime,
  onTimeUpdate,
  onReset,
  hapticController,
  realHardware,
  lastEvent,
  hapticConfig,
  onHapticConfigChange,
  audioSrc,
  saveState = 'idle',
  onSave,
}: MusicExperienceProps) {
  const [volume, setVolume] = useState(0.7);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { resolved } = useTheme();

  const handleMasterChange = useCallback((value: number) => {
    onHapticConfigChange({ ...hapticConfig, master_intensity: value });
  }, [hapticConfig, onHapticConfigChange]);

  return (
    <div
      className="fixed inset-0 flex flex-col z-40"
      style={{ background: 'var(--bg-primary)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-3 shrink-0"
        style={{
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/favicon.png" alt="" className="h-5 w-auto" />
          <span
            className="font-semibold tracking-widest text-xs uppercase"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
          >
            HEARBEAT
          </span>
          <span
            className="text-xs"
            style={{ color: 'var(--text-muted)' }}
          >
            Music
          </span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeSwitcher />
          <button
            onClick={onReset}
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

      {/* Main area: left visualizer | center | right visualizer */}
      <div className="flex-1 flex min-h-0">
        {/* Left visualizer — Power */}
        <div
          className="shrink-0 flex flex-col"
          style={{
            width: 'clamp(48px, 8vw, 80px)',
            borderRight: '1px solid var(--border-subtle)',
          }}
        >
          <HapticPowerVisualizer
            lastEvent={lastEvent}
            masterIntensity={hapticConfig.master_intensity}
          />
        </div>

        {/* Center — Knob + Controls */}
        <div
          className="flex-1 flex flex-col items-center justify-center min-w-0 min-h-0 gap-4 px-4 relative"
        >
          {/* Background icon */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `url(${resolved === 'light' ? '/icon_light.png' : '/icon_dark.png'})`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'center',
              backgroundSize: 'clamp(160px, 30vw, 280px) auto',
              backgroundPositionY: '42%',
              opacity: 0.08,
              pointerEvents: 'none',
            }}
          />

          {/* Haptic knob */}
          <RotaryKnob
            value={hapticConfig.master_intensity * 100}
            onChange={(pct) => handleMasterChange(pct / 100)}
          />

          {/* Player controls — volume | play | haptics */}
          <MusicAudioPlayer
            jobId={jobId}
            duration={duration}
            currentTime={currentTime}
            onTimeUpdate={onTimeUpdate}
            hapticController={hapticController}
            volume={volume}
            onVolumeChange={setVolume}
            onHapticSettingsClick={() => setSettingsOpen(true)}
            hapticEnabled={hapticConfig.master_intensity > 0}
            audioSrc={audioSrc}
            saveState={saveState}
            onSave={onSave}
          />
        </div>

        {/* Right visualizer — Response */}
        <div
          className="shrink-0 flex flex-col"
          style={{
            width: 'clamp(48px, 8vw, 80px)',
            borderLeft: '1px solid var(--border-subtle)',
          }}
        >
          <HapticResponseVisualizer lastEvent={lastEvent} />
        </div>
      </div>

      {/* Haptic settings popup */}
      <HapticSettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        controller={hapticController}
        realHardware={realHardware}
        lastEvent={lastEvent}
        config={hapticConfig}
        onConfigChange={onHapticConfigChange}
      />
    </div>
  );
}
