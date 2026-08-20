'use client';

import { useState, useCallback } from 'react';
import { HapticConfig, HapticEvent } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';
import HapticPowerVisualizer from '@/components/HapticPowerVisualizer';
import HapticResponseVisualizer from '@/components/HapticResponseVisualizer';
import RotaryKnob from '@/components/RotaryKnob';
import MusicPlayerBar from '@/components/MusicPlayerBar';
import HapticSettingsDialog from '@/components/HapticSettingsDialog';

interface MusicExperienceProps {
  jobId: string;
  filename: string;
  duration: number;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  onReset: () => void;
  hapticController: HapticController | null;
  realHardware: boolean;
  lastEvent: HapticEvent | null;
  hapticConfig: HapticConfig;
  onHapticConfigChange: (config: HapticConfig) => void;
}

export default function MusicExperience({
  jobId,
  filename,
  duration,
  currentTime,
  onTimeUpdate,
  onReset,
  hapticController,
  realHardware,
  lastEvent,
  hapticConfig,
  onHapticConfigChange,
}: MusicExperienceProps) {
  const [volume, setVolume] = useState(0.7);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleMasterChange = useCallback((value: number) => {
    onHapticConfigChange({ ...hapticConfig, master_intensity: value });
  }, [hapticConfig, onHapticConfigChange]);

  return (
    <div
      className="fixed inset-0 flex flex-col z-40"
      style={{ background: 'var(--bg-primary)' }}
    >
      {/* Track info bar */}
      <div
        className="flex items-center justify-between px-4 py-2 shrink-0"
        style={{
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
          {filename}
        </span>
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

        {/* Center — Master control */}
        <div className="flex-1 flex items-center justify-center min-w-0 min-h-0">
          <RotaryKnob
            value={hapticConfig.master_intensity * 100}
            onChange={(pct) => handleMasterChange(pct / 100)}
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

      {/* Bottom — Player bar */}
      <MusicPlayerBar
        jobId={jobId}
        duration={duration}
        currentTime={currentTime}
        onTimeUpdate={onTimeUpdate}
        hapticController={hapticController}
        volume={volume}
        onVolumeChange={setVolume}
        onHapticSettingsClick={() => setSettingsOpen(true)}
        hapticEnabled={hapticConfig.master_intensity > 0}
      />

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
