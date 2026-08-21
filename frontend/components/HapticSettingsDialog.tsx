'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { X, Vibrate, VibrateOff, Play, ChevronDown, ChevronUp } from 'lucide-react';
import { HapticConfig, HapticEvent } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';

interface HapticSettingsDialogProps {
  open: boolean;
  onClose: () => void;
  controller: HapticController | null;
  realHardware: boolean;
  lastEvent: HapticEvent | null;
  config: HapticConfig;
  onConfigChange: (config: HapticConfig) => void;
}

type HapticCategoryId = 'beat' | 'subbass' | 'hihat' | 'bass' | 'kick' | 'snare';

interface HapticCategory {
  id: HapticCategoryId;
  label: string;
  color: string;
}

const HAPTIC_CATEGORIES: HapticCategory[] = [
  { id: 'beat', label: 'Beat', color: 'var(--event-beat)' },
  { id: 'subbass', label: 'Sub-bass', color: 'var(--event-subbass-activity)' },
  { id: 'hihat', label: 'Hi-hat', color: 'var(--event-hihat)' },
  { id: 'bass', label: 'Bass', color: 'var(--event-bass)' },
  { id: 'kick', label: 'Kick', color: 'var(--event-kick)' },
  { id: 'snare', label: 'Snare', color: 'var(--event-snare)' },
];

export default function HapticSettingsDialog({
  open,
  onClose,
  controller,
  realHardware,
  lastEvent,
  config,
  onConfigChange,
}: HapticSettingsDialogProps) {
  const [selectedType, setSelectedType] = useState<HapticCategoryId>('bass');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [testPulseActive, setTestPulseActive] = useState(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  const updateConfig = useCallback(
    (patch: Partial<HapticConfig>) => {
      onConfigChange({ ...config, ...patch });
    },
    [config, onConfigChange]
  );

  const updateEventConfig = useCallback(
    (key: HapticCategoryId, field: 'intensity' | 'duration_ms', value: number) => {
      const current = config[key] as { intensity: number; duration_ms: number };
      updateConfig({ [key]: { ...current, [field]: value } });
    },
    [config, updateConfig]
  );

  const currentCategory = useMemo(
    () => HAPTIC_CATEGORIES.find((c) => c.id === selectedType) || HAPTIC_CATEGORIES[3],
    [selectedType]
  );

  const currentSettings = useMemo(() => {
    const raw = config[selectedType] as { intensity: number; duration_ms: number } | undefined;
    return raw || { intensity: 0.7, duration_ms: 180 };
  }, [config, selectedType]);

  const isLiveEvent = Boolean(
    lastEvent && (lastEvent.type === selectedType || lastEvent.type.startsWith(selectedType))
  );

  const isPulsing = testPulseActive || isLiveEvent;

  const handleTestPulse = useCallback(() => {
    if (!controller) return;
    setTestPulseActive(true);
    controller.testPulse(currentSettings.intensity * config.master_intensity, currentSettings.duration_ms);
    setTimeout(() => setTestPulseActive(false), Math.max(currentSettings.duration_ms, 200));
  }, [controller, currentSettings, config.master_intensity]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0, 0, 0, 0.65)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Haptic settings"
    >
      <div
        className="relative w-full max-w-md overflow-hidden flex flex-col"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            {realHardware ? (
              <Vibrate size={14} style={{ color: 'var(--success)' }} />
            ) : (
              <VibrateOff size={14} style={{ color: 'var(--text-muted)' }} />
            )}
            <span
              className="text-xs uppercase tracking-wider font-semibold"
              style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
            >
              Haptic Controls
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => updateConfig({ master_intensity: config.master_intensity > 0 ? 0 : 1 })}
              className="px-2 py-0.5 text-xs flex items-center gap-1 rounded-sm transition-colors"
              style={{
                color: config.master_intensity > 0 ? 'var(--success)' : 'var(--danger)',
                border: '1px solid var(--border)',
                background: config.master_intensity > 0 ? 'var(--status-success-surface, rgba(74,206,122,0.1))' : 'var(--bg-elevated)',
                fontFamily: 'var(--font-geist-mono)',
              }}
              aria-label={config.master_intensity > 0 ? 'Disable haptics' : 'Enable haptics'}
            >
              {config.master_intensity > 0 ? <Vibrate size={11} /> : <VibrateOff size={11} />}
              <span>{config.master_intensity > 0 ? 'ON' : 'OFF'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1 text-xs rounded-sm transition-opacity hover:opacity-80"
              style={{
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
              }}
              aria-label="Close dialog"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Top Category Selector: Beat | Sub-bass | Hi-hat | Bass | Kick | Snare */}
        <div
          className="flex items-center gap-1 px-3 py-2.5 overflow-x-auto whitespace-nowrap scrollbar-none"
          style={{
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-elevated)',
          }}
          role="tablist"
          aria-label="Haptic Event Categories"
        >
          {HAPTIC_CATEGORIES.map((cat) => {
            const isSelected = selectedType === cat.id;
            return (
              <button
                key={cat.id}
                role="tab"
                aria-selected={isSelected}
                onClick={() => setSelectedType(cat.id)}
                className="px-2.5 py-1 text-xs rounded-sm shrink-0 transition-all font-medium"
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  color: isSelected ? 'var(--text-primary)' : 'var(--text-muted)',
                  background: isSelected
                    ? 'color-mix(in srgb, var(--bg-surface) 90%, var(--text-primary))'
                    : 'transparent',
                  border: isSelected
                    ? `1px solid ${cat.color}`
                    : '1px solid transparent',
                  boxShadow: isSelected ? `0 0 8px ${cat.color}25` : 'none',
                }}
              >
                <span className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle" style={{ background: cat.color }} />
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Body: Single Active Category Controls */}
        <div className="p-4 flex flex-col gap-5">
          {/* Strength Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="haptic-strength"
                className="text-xs uppercase tracking-wider font-medium"
                style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-geist-mono)' }}
              >
                Strength
              </label>
              <span
                className="text-sm font-semibold tabular-nums"
                style={{ color: currentCategory.color, fontFamily: 'var(--font-geist-mono)' }}
              >
                {Math.round(currentSettings.intensity * 100)}%
              </span>
            </div>
            <input
              id="haptic-strength"
              type="range"
              min={0}
              max={100}
              value={Math.round(currentSettings.intensity * 100)}
              onChange={(e) => updateEventConfig(selectedType, 'intensity', parseInt(e.target.value, 10) / 100)}
              className="w-full h-1.5 cursor-pointer accent-gold"
              style={{ accentColor: currentCategory.color }}
              aria-label={`${currentCategory.label} strength`}
            />
          </div>

          {/* Latency Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="haptic-latency"
                className="text-xs uppercase tracking-wider font-medium"
                style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-geist-mono)' }}
              >
                Latency
              </label>
              <span
                className="text-sm font-semibold tabular-nums"
                style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
              >
                {currentSettings.duration_ms}ms
              </span>
            </div>
            <input
              id="haptic-latency"
              type="range"
              min={5}
              max={250}
              value={currentSettings.duration_ms}
              onChange={(e) => updateEventConfig(selectedType, 'duration_ms', parseInt(e.target.value, 10))}
              className="w-full h-1.5 cursor-pointer"
              style={{ accentColor: currentCategory.color }}
              aria-label={`${currentCategory.label} latency duration`}
            />
          </div>

          {/* Live Preview / Test Button Row */}
          <div
            className="flex items-center justify-between p-2.5 rounded-sm border"
            style={{
              background: 'var(--bg-elevated)',
              borderColor: 'var(--border)',
            }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-2.5 h-2.5 rounded-full transition-transform duration-150"
                style={{
                  background: currentCategory.color,
                  transform: isPulsing ? 'scale(1.4)' : 'scale(1)',
                  boxShadow: isPulsing ? `0 0 10px ${currentCategory.color}` : 'none',
                }}
              />
              <div className="flex flex-col">
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                  {currentCategory.label} Preview
                </span>
                <span className="text-[11px]" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
                  {Math.round(currentSettings.intensity * 100)}% · {currentSettings.duration_ms}ms
                </span>
              </div>
            </div>

            <button
              onClick={handleTestPulse}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-sm transition-opacity hover:opacity-90 font-medium"
              style={{
                color: 'var(--text-primary)',
                border: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                fontFamily: 'var(--font-geist-mono)',
              }}
              aria-label={`Test ${currentCategory.label} haptic pulse`}
            >
              <Play size={11} className="fill-current" />
              <span>Test Pulse</span>
            </button>
          </div>

          {/* Collapsible Advanced Settings (Adaptive & Anticipation) */}
          <div className="border-t pt-3" style={{ borderColor: 'var(--border-subtle)' }}>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full text-xs transition-colors hover:text-text-primary py-1"
              style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
              aria-expanded={showAdvanced}
            >
              <span>Advanced Dynamics</span>
              {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>

            {showAdvanced && (
              <div className="flex flex-col gap-3 mt-2.5 pt-2">
                {/* Adaptive toggle & gain */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      Adaptive Loudness Scaling
                    </span>
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      Scale haptic energy to song dynamics
                    </span>
                  </div>
                  <button
                    onClick={() => updateConfig({ adaptive_enabled: !config.adaptive_enabled })}
                    className="px-2.5 py-0.5 text-xs rounded-sm border"
                    style={{
                      color: config.adaptive_enabled ? 'var(--accent)' : 'var(--text-muted)',
                      borderColor: config.adaptive_enabled ? 'var(--accent)' : 'var(--border)',
                      background: config.adaptive_enabled ? 'var(--accent-surface)' : 'transparent',
                      fontFamily: 'var(--font-geist-mono)',
                    }}
                  >
                    {config.adaptive_enabled ? 'ON' : 'OFF'}
                  </button>
                </div>

                {config.adaptive_enabled && (
                  <div className="flex flex-col gap-1 pl-2">
                    <div className="flex items-center justify-between text-[11px]" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
                      <span>Gain Strength</span>
                      <span>{(config.adaptive_gain_strength * 100).toFixed(0)}%</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={200}
                      value={Math.round(config.adaptive_gain_strength * 100)}
                      onChange={(e) => updateConfig({ adaptive_gain_strength: parseInt(e.target.value, 10) / 100 })}
                      className="w-full h-1"
                      style={{ accentColor: 'var(--accent)' }}
                      aria-label="Adaptive gain strength"
                    />
                  </div>
                )}

                {/* Anticipation toggle */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      Beat Anticipation
                    </span>
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      Pre-cue upcoming downbeats
                    </span>
                  </div>
                  <button
                    onClick={() => updateConfig({ anticipation_enabled: !config.anticipation_enabled })}
                    className="px-2.5 py-0.5 text-xs rounded-sm border"
                    style={{
                      color: config.anticipation_enabled ? 'var(--accent)' : 'var(--text-muted)',
                      borderColor: config.anticipation_enabled ? 'var(--accent)' : 'var(--border)',
                      background: config.anticipation_enabled ? 'var(--accent-surface)' : 'transparent',
                      fontFamily: 'var(--font-geist-mono)',
                    }}
                  >
                    {config.anticipation_enabled ? 'ON' : 'OFF'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
