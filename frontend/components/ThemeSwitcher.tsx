'use client';

import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme, ThemePreference } from '@/lib/theme';

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
  { value: 'system', label: 'System theme', icon: Monitor },
];

export default function ThemeSwitcher() {
  const { preference, setPreference } = useTheme();

  return (
    <div className="flex items-center" role="radiogroup" aria-label="Theme selection">
      {OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const active = preference === opt.value;
        return (
          <button
            key={opt.value}
            role="radio"
            aria-checked={active}
            aria-label={opt.label}
            onClick={() => setPreference(opt.value)}
            className="p-1.5"
            style={{
              color: active ? 'var(--accent)' : 'var(--text-muted)',
              background: active ? 'var(--accent-surface)' : 'transparent',
              borderRadius: '2px',
            }}
          >
            <Icon size={14} strokeWidth={1.5} />
          </button>
        );
      })}
    </div>
  );
}
