'use client';

import { useRef, useCallback, useEffect } from 'react';

interface RotaryKnobProps {
  value: number;
  onChange: (value: number) => void;
}

const KNOB_FULL_RANGE_DEGREES = 320;

export default function RotaryKnob({ value, onChange }: RotaryKnobProps) {
  const knobRef = useRef<HTMLDivElement>(null);
  const activePointerRef = useRef<number | null>(null);
  const prevAngleRef = useRef(0);
  const accumulatedRef = useRef(0);
  const initialValueRef = useRef(0);

  const getAngle = useCallback((clientX: number, clientY: number) => {
    const knob = knobRef.current;
    if (!knob) return 0;
    const rect = knob.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    return Math.atan2(clientY - cy, clientX - cx);
  }, []);

  const clampValue = useCallback((v: number) => Math.max(0, Math.min(100, Math.round(v))), []);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const knob = knobRef.current;
    if (!knob) return;

    knob.setPointerCapture(e.pointerId);
    activePointerRef.current = e.pointerId;
    prevAngleRef.current = getAngle(e.clientX, e.clientY);
    accumulatedRef.current = 0;
    initialValueRef.current = value;
  }, [value, getAngle]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (activePointerRef.current !== e.pointerId) return;

    const currentAngle = getAngle(e.clientX, e.clientY);
    const prevAngle = prevAngleRef.current;

    let delta = currentAngle - prevAngle;
    if (delta > Math.PI) delta -= 2 * Math.PI;
    if (delta < -Math.PI) delta += 2 * Math.PI;

    prevAngleRef.current = currentAngle;
    accumulatedRef.current += delta;

    const degreesForFullRange = KNOB_FULL_RANGE_DEGREES;
    const valueDelta = (accumulatedRef.current / (degreesForFullRange * Math.PI / 180)) * 100;
    const newValue = clampValue(initialValueRef.current + valueDelta);
    onChange(newValue);
  }, [getAngle, clampValue, onChange]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    const knob = knobRef.current;
    if (knob && activePointerRef.current !== null) {
      try { knob.releasePointerCapture(e.pointerId); } catch {}
    }
    activePointerRef.current = null;
  }, []);

  const handlePointerCancel = useCallback((e: React.PointerEvent) => {
    const knob = knobRef.current;
    if (knob && activePointerRef.current !== null) {
      try { knob.releasePointerCapture(e.pointerId); } catch {}
    }
    activePointerRef.current = null;
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 2;
    let newValue = value;
    switch (e.key) {
      case 'ArrowUp':
      case 'ArrowRight':
        e.preventDefault();
        newValue = clampValue(value + step);
        break;
      case 'ArrowDown':
      case 'ArrowLeft':
        e.preventDefault();
        newValue = clampValue(value - step);
        break;
      case 'Home':
        e.preventDefault();
        newValue = 0;
        break;
      case 'End':
        e.preventDefault();
        newValue = 100;
        break;
      default:
        return;
    }
    onChange(newValue);
  }, [value, clampValue, onChange]);

  useEffect(() => {
    const knob = knobRef.current;
    if (!knob) return;
    const preventScroll = (e: TouchEvent) => e.preventDefault();
    knob.addEventListener('touchstart', preventScroll, { passive: false });
    knob.addEventListener('touchmove', preventScroll, { passive: false });
    return () => {
      knob.removeEventListener('touchstart', preventScroll);
      knob.removeEventListener('touchmove', preventScroll);
    };
  }, []);

  const pct = Math.round(value);
  const visStartAngle = -225;
  const visEndAngle = 45;
  const visRange = visEndAngle - visStartAngle;
  const sweepAngle = visStartAngle + (value / 100) * visRange;
  const rad = (deg: number) => (deg * Math.PI) / 180;

  const r = 42;
  const cx = 50;
  const cy = 50;
  const arcStartX = cx + r * Math.cos(rad(visStartAngle));
  const arcStartY = cy + r * Math.sin(rad(visStartAngle));
  const arcEndX = cx + r * Math.cos(rad(sweepAngle));
  const arcEndY = cy + r * Math.sin(rad(sweepAngle));
  const largeArc = (sweepAngle - visStartAngle) > 180 ? 1 : 0;

  const indicatorR = 36;
  const indicatorAngle = rad(sweepAngle);
  const indicatorX = cx + indicatorR * Math.cos(indicatorAngle);
  const indicatorY = cy + indicatorR * Math.sin(indicatorAngle);

  const tickMarks = [0, 25, 50, 75, 100].map((pctVal) => {
    const tickAngle = rad(visStartAngle + (pctVal / 100) * visRange);
    const innerR = 38;
    const outerR = 44;
    return {
      x1: cx + innerR * Math.cos(tickAngle),
      y1: cy + innerR * Math.sin(tickAngle),
      x2: cx + outerR * Math.cos(tickAngle),
      y2: cy + outerR * Math.sin(tickAngle),
    };
  });

  return (
    <div className="flex flex-col items-center gap-3 select-none">
      <span
        className="text-xs uppercase tracking-wider"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', fontSize: '9px' }}
      >
        HAPTIC
      </span>

      <div
        ref={knobRef}
        className="relative cursor-grab active:cursor-grabbing"
        style={{ touchAction: 'none', width: 'clamp(140px, 30vw, 200px)', height: 'clamp(140px, 30vw, 200px)' }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
        role="slider"
        tabIndex={0}
        aria-label="Master haptic intensity"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        onKeyDown={handleKeyDown}
      >
        <svg viewBox="0 0 100 100" className="w-full h-full">
          {/* Background ring */}
          <circle
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke="var(--border)"
            strokeWidth="3"
            strokeLinecap="round"
          />

          {/* Active arc */}
          {value > 0 && (
            <path
              d={`M ${arcStartX} ${arcStartY} A ${r} ${r} 0 ${largeArc} 1 ${arcEndX} ${arcEndY}`}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="4"
              strokeLinecap="round"
            />
          )}

          {/* Tick marks */}
          {tickMarks.map((tick, i) => (
            <line
              key={i}
              x1={tick.x1} y1={tick.y1}
              x2={tick.x2} y2={tick.y2}
              stroke="var(--border-strong)"
              strokeWidth="1"
            />
          ))}

          {/* Rotation indicator dot */}
          <circle
            cx={indicatorX} cy={indicatorY} r="3"
            fill="var(--accent)"
          />

          {/* Center dot */}
          <circle
            cx={cx} cy={cy} r="4"
            fill="var(--bg-elevated)"
            stroke="var(--border)"
            strokeWidth="1"
          />
        </svg>

        {/* Value text */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ pointerEvents: 'none' }}
        >
          <span
            className="text-xl tabular-nums font-semibold"
            style={{
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            {pct}%
          </span>
        </div>
      </div>
    </div>
  );
}
