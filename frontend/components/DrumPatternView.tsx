'use client';

import { useMemo } from 'react';
import { DrumEventDetail, RhythmInfo } from '@/lib/types';

interface DrumPatternViewProps {
  drumEvents: DrumEventDetail[];
  rhythm: RhythmInfo;
}

const DRUM_ROWS = [
  { type: 'kick', label: 'KICK', color: 'var(--event-kick)' },
  { type: 'snare', label: 'SNARE', color: 'var(--event-snare)' },
  { type: 'hihat', label: 'HI-HAT', color: 'var(--event-hihat)' },
  { type: 'drum_onset', label: 'DRUM', color: 'var(--event-drum-onset)' },
];

const SUBDIVISIONS = 16;

export default function DrumPatternView({ drumEvents, rhythm }: DrumPatternViewProps) {
  const patternData = useMemo(() => {
    if (drumEvents.length === 0 || rhythm.beats.length < 2) return null;

    const beats = rhythm.beats;
    const beatDuration = beats.length > 1 ? beats[1] - beats[0] : 0.5;
    const subDuration = beatDuration / 4; // 16th note subdivisions

    // Build grid: each row is a drum type, each column is a subdivision
    const grid: Record<string, Set<number>> = {};
    for (const row of DRUM_ROWS) {
      grid[row.type] = new Set();
    }

    // Map events to grid positions
    for (const event of drumEvents) {
      if (!grid[event.type]) continue;

      // Find which beat this event is near
      let beatIdx = 0;
      for (let i = 0; i < beats.length; i++) {
        if (Math.abs(event.nearest_beat - beats[i]) < beatDuration * 0.1) {
          beatIdx = i;
          break;
        }
      }

      // Calculate subdivision within beat
      const beatStart = beats[beatIdx] || 0;
      const offset = event.time - beatStart;
      const subIdx = Math.round(offset / subDuration);
      const gridPos = beatIdx * 4 + subIdx;

      if (gridPos >= 0 && gridPos < SUBDIVISIONS * Math.ceil(beats.length / 4)) {
        grid[event.type].add(gridPos);
      }
    }

    return grid;
  }, [drumEvents, rhythm]);

  if (!patternData) {
    return (
      <div className="panel px-4 py-3">
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          Drum Pattern
        </span>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          Insufficient data for pattern view
        </p>
      </div>
    );
  }

  const totalCols = Math.min(SUBDIVISIONS * 4, 64);

  return (
    <div className="panel flex flex-col">
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          Drum Pattern
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          1 e &amp; a 2 e &amp; a 3 e &amp; a 4 e &amp; a
        </span>
      </div>
      <div className="overflow-auto px-3 py-2">
        <table className="w-full" style={{ fontFamily: 'var(--font-geist-mono)' }}>
          <thead>
            <tr>
              <th className="text-left text-xs pr-3" style={{ color: 'var(--text-muted)', width: '60px' }}></th>
              {Array.from({ length: totalCols }, (_, i) => {
                const isBeat = i % 4 === 0;
                return (
                  <th
                    key={i}
                    className="text-center text-xs"
                    style={{
                      color: isBeat ? 'var(--text-secondary)' : 'var(--text-muted)',
                      width: '16px',
                      minWidth: '16px',
                      fontWeight: isBeat ? 'bold' : 'normal',
                    }}
                  >
                    {isBeat ? (i / 4 + 1).toString() : ''}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {DRUM_ROWS.map((row) => (
              <tr key={row.type}>
                <td
                  className="text-xs pr-3 py-0.5"
                  style={{ color: row.color }}
                >
                  {row.label}
                </td>
                {Array.from({ length: totalCols }, (_, i) => {
                  const hasHit = patternData[row.type]?.has(i);
                  return (
                    <td
                      key={i}
                      className="text-center py-0.5"
                      style={{
                        background: i % 4 === 0 ? 'var(--bg-surface)' : 'transparent',
                      }}
                    >
                      {hasHit && (
                        <div
                          className="inline-block w-2.5 h-2.5"
                          style={{
                            background: row.color,
                            borderRadius: '1px',
                          }}
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
