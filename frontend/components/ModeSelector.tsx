'use client';

import { AnalysisMode } from '@/lib/types';
import { useTheme } from '@/lib/theme';

interface ModeSelectorProps {
  selected: AnalysisMode;
  onSelect: (mode: AnalysisMode) => void;
  disabled?: boolean;
}

export default function ModeSelector({ selected, onSelect, disabled }: ModeSelectorProps) {
  const { resolved } = useTheme();

  const modes: { value: AnalysisMode; label: string; img: string }[] = [
    {
      value: 'music',
      label: 'Enjoy Music',
      img: resolved === 'light' ? '/Enjoy_music_light.png' : '/Enjoy_music_dark.png',
    },
    {
      value: 'drumming',
      label: "Let's Drum",
      img: resolved === 'light' ? '/drumming_light.png' : '/drumming_dark.png',
    },
  ];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col sm:flex-row gap-3">
        {modes.map((m) => (
          <button
            key={m.value}
            onClick={() => onSelect(m.value)}
            disabled={disabled}
            aria-label={m.label}
            className="flex-1 flex items-center justify-center p-3 transition-colors disabled:opacity-50 cursor-pointer"
            style={{
              background: selected === m.value ? 'var(--accent-dim)' : 'transparent',
              border: `1px solid ${selected === m.value ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: '2px',
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={m.img}
              alt={m.label}
              className="h-auto w-[clamp(120px,30vw,180px)] sm:w-[clamp(100px,18vw,160px)]"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
