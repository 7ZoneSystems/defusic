'use client';

import { useState, useMemo } from 'react';
import { Filter } from 'lucide-react';
import { DrumEventDetail } from '@/lib/types';

interface DrumEventInspectorProps {
  events: DrumEventDetail[];
}

const FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Kick', value: 'kick' },
  { label: 'Snare', value: 'snare' },
  { label: 'Hi-hat', value: 'hihat' },
  { label: 'Drum', value: 'drum_onset' },
];

const TYPE_COLORS: Record<string, string> = {
  kick: 'var(--event-kick)',
  snare: 'var(--event-snare)',
  hihat: 'var(--event-hihat)',
  drum_onset: 'var(--event-drum-onset)',
  cymbal: 'var(--event-hihat)',
  percussion: 'var(--event-drum-onset)',
};

export default function DrumEventInspector({ events }: DrumEventInspectorProps) {
  const [filter, setFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const perPage = 50;

  const filtered = useMemo(
    () => (filter === 'all' ? events : events.filter((e) => e.type === filter)),
    [events, filter]
  );

  const totalPages = Math.ceil(filtered.length / perPage);
  const visible = filtered.slice(page * perPage, (page + 1) * perPage);

  return (
    <div className="panel flex flex-col">
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <Filter size={12} style={{ color: 'var(--text-muted)' }} />
          <span
            className="text-xs uppercase tracking-wider"
            style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
          >
            Drum Events
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            ({filtered.length})
          </span>
        </div>
        <div className="flex items-center gap-px" style={{ background: 'var(--border)' }}>
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setFilter(f.value); setPage(0); }}
              className="px-2 py-1 text-xs"
              style={{
                background: filter === f.value ? 'var(--bg-elevated)' : 'var(--bg-surface)',
                color: filter === f.value ? 'var(--text-primary)' : 'var(--text-muted)',
                fontFamily: 'var(--font-geist-mono)',
              }}
              aria-pressed={filter === f.value}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-auto" style={{ maxHeight: '320px' }}>
        <table className="w-full text-xs" style={{ fontFamily: 'var(--font-geist-mono)' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['TIME', 'TYPE', 'STRENGTH', 'CONFIDENCE', 'NEAREST BEAT', 'DELTA', 'POSITION'].map((h) => (
                <th
                  key={h}
                  className="px-3 py-1.5 text-left font-medium"
                  style={{ color: 'var(--text-muted)', background: 'var(--bg-surface)' }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((event, i) => (
              <tr
                key={`${event.time}-${event.type}-${i}`}
                style={{ borderBottom: '1px solid var(--border-subtle)' }}
              >
                <td className="px-3 py-1.5" style={{ color: 'var(--text-primary)' }}>
                  {event.time.toFixed(3)}
                </td>
                <td className="px-3 py-1.5">
                  <span
                    className="inline-block px-1.5 py-0.5"
                    style={{
                      color: TYPE_COLORS[event.type] || 'var(--text-muted)',
                      background: `${TYPE_COLORS[event.type] || 'var(--text-muted)'}15`,
                      borderRadius: '2px',
                    }}
                  >
                    {event.type}
                  </span>
                </td>
                <td className="px-3 py-1.5" style={{ color: 'var(--text-secondary)' }}>
                  {event.strength.toFixed(3)}
                </td>
                <td className="px-3 py-1.5" style={{ color: 'var(--text-secondary)' }}>
                  {event.confidence.toFixed(3)}
                </td>
                <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>
                  {event.nearest_beat.toFixed(3)}
                </td>
                <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>
                  {event.beat_delta_seconds >= 0 ? '+' : ''}{event.beat_delta_seconds.toFixed(4)}
                </td>
                <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>
                  {event.beat_position.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div
          className="flex items-center justify-between px-3 py-1.5"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-0.5 text-xs disabled:opacity-30"
              style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '2px' }}
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-0.5 text-xs disabled:opacity-30"
              style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '2px' }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
