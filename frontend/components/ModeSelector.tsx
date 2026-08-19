'use client';

import { Music, Drum } from 'lucide-react';
import { AnalysisMode } from '@/lib/types';

interface ModeSelectorProps {
  selected: AnalysisMode;
  onSelect: (mode: AnalysisMode) => void;
  disabled?: boolean;
}

const MODES: { value: AnalysisMode; label: string; description: string; icon: React.ReactNode }[] = [
  {
    value: 'music',
    label: 'Music Enjoyment',
    description: 'Beat and bass analysis for musical structure',
    icon: <Music size={16} strokeWidth={1.5} />,
  },
  {
    value: 'drumming',
    label: 'Drumming',
    description: 'Drum-focused analysis with diagnostic playback',
    icon: <Drum size={16} strokeWidth={1.5} />,
  },
];

export default function ModeSelector({ selected, onSelect, disabled }: ModeSelectorProps) {
  return (
    <div className="flex flex-col gap-2">
      <span
        className="text-xs uppercase tracking-wider"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
      >
        Analysis Mode
      </span>
      <div className="flex gap-2">
        {MODES.map((mode) => (
          <button
            key={mode.value}
            onClick={() => onSelect(mode.value)}
            disabled={disabled}
            className="flex-1 flex items-center gap-3 px-4 py-3 text-left transition-colors disabled:opacity-50"
            style={{
              background: selected === mode.value ? 'var(--accent-dim)' : 'var(--bg-panel)',
              color: selected === mode.value ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: `1px solid ${selected === mode.value ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            <span style={{ color: selected === mode.value ? 'var(--accent)' : 'var(--text-muted)' }}>
              {mode.icon}
            </span>
            <div>
              <div className="text-xs font-medium">{mode.label}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {mode.description}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
