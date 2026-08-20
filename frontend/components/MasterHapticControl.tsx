'use client';

import { useCallback, useRef } from 'react';

interface MasterHapticControlProps {
  value: number;
  onChange: (value: number) => void;
}

export default function MasterHapticControl({ value, onChange }: MasterHapticControlProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const updateFromPointer = useCallback((clientY: number) => {
    const track = trackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const ratio = 1 - (clientY - rect.top) / rect.height;
    const clamped = Math.max(0, Math.min(1, ratio));
    onChange(clamped);
  }, [onChange]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    updateFromPointer(e.clientY);
  }, [updateFromPointer]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!draggingRef.current) return;
    updateFromPointer(e.clientY);
  }, [updateFromPointer]);

  const handlePointerUp = useCallback(() => {
    draggingRef.current = false;
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 0.1 : 0.02;
    if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
      e.preventDefault();
      onChange(Math.min(1, value + step));
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
      e.preventDefault();
      onChange(Math.max(0, value - step));
    }
  }, [value, onChange]);

  const displayValue = Math.round(value * 100);
  const fillHeight = value * 100;

  return (
    <div className="flex flex-col items-center gap-2 select-none">
      <span
        className="text-xs uppercase tracking-wider"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', fontSize: '9px' }}
      >
        HAPTIC
      </span>

      <div
        className="relative flex flex-col items-center"
        style={{ height: 'clamp(180px, 35vh, 320px)' }}
      >
        {/* Track background */}
        <div
          ref={trackRef}
          className="relative w-10 rounded-sm cursor-pointer"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            height: '100%',
          }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          role="slider"
          tabIndex={0}
          aria-label="Master haptic intensity"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={displayValue}
          onKeyDown={handleKeyDown}
        >
          {/* Fill */}
          <div
            className="absolute bottom-0 left-0 right-0 transition-none"
            style={{
              height: `${fillHeight}%`,
              background: value > 0.5
                ? 'var(--accent)'
                : value > 0
                  ? 'var(--accent-dim)'
                  : 'transparent',
              opacity: 0.4 + value * 0.6,
            }}
          />

          {/* Thumb indicator */}
          <div
            className="absolute left-0 right-0 h-0.5"
            style={{
              bottom: `${fillHeight}%`,
              background: 'var(--accent)',
              transform: 'translateY(50%)',
            }}
          />

          {/* Tick marks */}
          {[0, 25, 50, 75, 100].map((pct) => (
            <div
              key={pct}
              className="absolute left-full ml-1.5 flex items-center"
              style={{ bottom: `${pct}%`, transform: 'translateY(50%)' }}
            >
              <div
                className="w-1.5 h-px"
                style={{ background: 'var(--border)' }}
              />
              <span
                className="ml-1"
                style={{
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '8px',
                }}
              >
                {pct}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Value display */}
      <span
        className="text-lg tabular-nums"
        style={{
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-geist-mono)',
          fontWeight: 600,
        }}
      >
        {displayValue}%
      </span>
    </div>
  );
}
