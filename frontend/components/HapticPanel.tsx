'use client';

import { useState, useCallback } from 'react';
import { Vibrate, VibrateOff, Play, Square } from 'lucide-react';
import { HapticConfig, HapticEvent } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';
import { DEFAULT_HAPTIC_CONFIG } from '@/lib/haptic-types';

interface HapticPanelProps {
  controller: HapticController | null;
  realHardware: boolean;
  lastEvent: HapticEvent | null;
  config: HapticConfig;
  onConfigChange: (config: HapticConfig) => void;
}

interface SliderRowProps {
  label: string;
  intensity: number;
  duration_ms: number;
  onIntensityChange: (v: number) => void;
  onDurationChange: (v: number) => void;
}

function SliderRow({ label, intensity, duration_ms, onIntensityChange, onDurationChange }: SliderRowProps) {
  return (
    <div className="flex items-center gap-3 py-1.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <span className="text-xs w-20 shrink-0" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-geist-mono)' }}>
        {label}
      </span>
      <div className="flex items-center gap-2 flex-1">
        <span className="text-xs w-8 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
          {(intensity * 100).toFixed(0)}%
        </span>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(intensity * 100)}
          onChange={(e) => onIntensityChange(parseInt(e.target.value) / 100)}
          className="flex-1"
          aria-label={`${label} intensity`}
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs w-10 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
          {duration_ms}ms
        </span>
        <input
          type="range"
          min={5}
          max={200}
          value={duration_ms}
          onChange={(e) => onDurationChange(parseInt(e.target.value))}
          className="w-16"
          aria-label={`${label} duration`}
        />
      </div>
    </div>
  );
}

function PulseBar({ intensity, color }: { intensity: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-3 rounded-sm overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
        <div
          className="h-full transition-all duration-150"
          style={{ width: `${intensity * 100}%`, background: color }}
        />
      </div>
    </div>
  );
}

const EVENT_COLORS: Record<string, string> = {
  beat: 'var(--beat-color)',
  hihat: 'var(--hihat-color)',
  kick: 'var(--kick-color)',
  snare: 'var(--snare-color)',
  bass: 'var(--bass-beat-color)',
  subbass: '#6A8ECE',
};

export default function HapticPanel({
  controller,
  realHardware,
  lastEvent,
  config,
  onConfigChange,
}: HapticPanelProps) {
  const [testRunning, setTestRunning] = useState(false);

  const updateConfig = useCallback(
    (patch: Partial<HapticConfig>) => {
      onConfigChange({ ...config, ...patch });
    },
    [config, onConfigChange]
  );

  const updateEventConfig = useCallback(
    (key: keyof HapticConfig, field: 'intensity' | 'duration_ms', value: number) => {
      const current = config[key] as { intensity: number; duration_ms: number };
      updateConfig({ [key]: { ...current, [field]: value } });
    },
    [config, updateConfig]
  );

  const handleTestPulse = useCallback(
    (type: string) => {
      if (!controller) return;
      const cfg = config[type as keyof HapticConfig] as { intensity: number; duration_ms: number } | undefined;
      if (cfg && typeof cfg === 'object' && 'intensity' in cfg) {
        controller.testPulse(cfg.intensity * config.master_intensity, cfg.duration_ms);
      }
    },
    [controller, config]
  );

  const handleTestSequence = useCallback(async () => {
    if (!controller || testRunning) return;
    setTestRunning(true);

    const types = ['beat', 'hihat', 'kick', 'bass', 'subbass'];
    for (const type of types) {
      handleTestPulse(type);
      await new Promise((r) => setTimeout(r, 500));
    }

    setTestRunning(false);
  }, [controller, testRunning, handleTestPulse]);

  return (
    <div className="panel flex flex-col">
      <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          {realHardware ? (
            <Vibrate size={12} style={{ color: 'var(--success)' }} />
          ) : (
            <VibrateOff size={12} style={{ color: 'var(--text-muted)' }} />
          )}
          <span
            className="text-xs uppercase tracking-wider"
            style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
          >
            Haptics
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-xs px-2 py-0.5"
            style={{
              color: realHardware ? 'var(--success)' : 'var(--text-muted)',
              background: realHardware ? 'rgba(74, 206, 122, 0.1)' : 'var(--bg-elevated)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            {realHardware ? 'HAPTICS AVAILABLE' : 'PREVIEW MODE'}
          </span>
          <button
            onClick={() => updateConfig({ master_intensity: config.master_intensity > 0 ? 0 : 1 })}
            className="px-2 py-1 text-xs flex items-center gap-1"
            style={{
              color: config.master_intensity > 0 ? 'var(--success)' : 'var(--danger)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
            aria-label={config.master_intensity > 0 ? 'Disable haptics' : 'Enable haptics'}
          >
            {config.master_intensity > 0 ? <Vibrate size={10} /> : <VibrateOff size={10} />}
            {config.master_intensity > 0 ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      <div className="px-3 py-2">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Master</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(config.master_intensity * 100)}
            onChange={(e) => updateConfig({ master_intensity: parseInt(e.target.value) / 100 })}
            className="flex-1"
            aria-label="Master haptic intensity"
          />
          <span className="text-xs w-10 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
            {(config.master_intensity * 100).toFixed(0)}%
          </span>
        </div>

        <SliderRow
          label="Beat"
          intensity={config.beat.intensity}
          duration_ms={config.beat.duration_ms}
          onIntensityChange={(v) => updateEventConfig('beat', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('beat', 'duration_ms', v)}
        />
        <SliderRow
          label="Hi-hat"
          intensity={config.hihat.intensity}
          duration_ms={config.hihat.duration_ms}
          onIntensityChange={(v) => updateEventConfig('hihat', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('hihat', 'duration_ms', v)}
        />
        <SliderRow
          label="Kick"
          intensity={config.kick.intensity}
          duration_ms={config.kick.duration_ms}
          onIntensityChange={(v) => updateEventConfig('kick', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('kick', 'duration_ms', v)}
        />
        <SliderRow
          label="Snare"
          intensity={config.snare.intensity}
          duration_ms={config.snare.duration_ms}
          onIntensityChange={(v) => updateEventConfig('snare', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('snare', 'duration_ms', v)}
        />
        <SliderRow
          label="Bass"
          intensity={config.bass.intensity}
          duration_ms={config.bass.duration_ms}
          onIntensityChange={(v) => updateEventConfig('bass', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('bass', 'duration_ms', v)}
        />
        <SliderRow
          label="Sub-bass"
          intensity={config.subbass.intensity}
          duration_ms={config.subbass.duration_ms}
          onIntensityChange={(v) => updateEventConfig('subbass', 'intensity', v)}
          onDurationChange={(v) => updateEventConfig('subbass', 'duration_ms', v)}
        />

        <div className="flex items-center gap-3 py-2 mt-1" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Anticipation</span>
          <button
            onClick={() => updateConfig({ anticipation_enabled: !config.anticipation_enabled })}
            className="px-2 py-0.5 text-xs"
            style={{
              color: config.anticipation_enabled ? 'var(--accent)' : 'var(--text-muted)',
              background: config.anticipation_enabled ? 'var(--accent-glow)' : 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            {config.anticipation_enabled ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Test Panel */}
      <div className="px-3 py-2" style={{ borderTop: '1px solid var(--border)' }}>
        <span className="text-xs uppercase tracking-wider block mb-2" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
          Test Panel
        </span>

        {lastEvent && (
          <div className="mb-2 px-2 py-1.5" style={{ background: 'var(--bg-primary)', borderRadius: '2px' }}>
            <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
              Last: {lastEvent.type} ({(lastEvent.intensity * 100).toFixed(0)}% / {lastEvent.duration_ms}ms)
            </span>
          </div>
        )}

        {/* Visual pulse preview for desktop */}
        {!realHardware && (
          <div className="mb-3 px-2 py-2" style={{ background: 'var(--bg-primary)', borderRadius: '2px' }}>
            <span className="text-xs block mb-1.5" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
              Haptic Preview
            </span>
            {['beat', 'hihat', 'kick', 'bass', 'subbass'].map((type) => {
              const cfg = config[type as keyof HapticConfig] as { intensity: number; duration_ms: number };
              return (
                <div key={type} className="flex items-center gap-2 py-0.5">
                  <span className="text-xs w-14" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-geist-mono)' }}>
                    {type}
                  </span>
                  <PulseBar intensity={cfg.intensity} color={EVENT_COLORS[type] || 'var(--accent)'} />
                  <span className="text-xs w-10 text-right" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
                    {cfg.duration_ms}ms
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          {['beat', 'hihat', 'kick', 'bass', 'subbass'].map((type) => (
            <button
              key={type}
              onClick={() => handleTestPulse(type)}
              className="px-2 py-1 text-xs"
              style={{
                color: 'var(--text-secondary)',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: '2px',
                fontFamily: 'var(--font-geist-mono)',
              }}
              disabled={!controller}
            >
              {type}
            </button>
          ))}
          <button
            onClick={handleTestSequence}
            disabled={!controller || testRunning}
            className="px-2 py-1 text-xs flex items-center gap-1"
            style={{
              color: testRunning ? 'var(--accent)' : 'var(--text-secondary)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            {testRunning ? <Square size={10} /> : <Play size={10} />}
            Sequence
          </button>
        </div>
      </div>
    </div>
  );
}
