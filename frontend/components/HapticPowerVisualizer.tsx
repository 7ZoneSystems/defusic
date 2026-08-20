'use client';

import { useRef, useEffect } from 'react';
import { HapticEvent } from '@/lib/haptic-types';

interface HapticPowerVisualizerProps {
  lastEvent: HapticEvent | null;
  masterIntensity: number;
}

const BAR_COUNT = 24;
const DECAY_RATE = 0.92;
const ATTACK_RATE = 0.35;

export default function HapticPowerVisualizer({ lastEvent, masterIntensity }: HapticPowerVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const barsRef = useRef<number[]>(new Array(BAR_COUNT).fill(0));
  const targetRef = useRef<number[]>(new Array(BAR_COUNT).fill(0));
  const rafRef = useRef<number>(0);
  const lastEventRef = useRef<HapticEvent | null>(null);
  const masterRef = useRef(masterIntensity);

  useEffect(() => {
    masterRef.current = masterIntensity;
  }, [masterIntensity]);

  useEffect(() => {
    if (lastEvent && lastEvent !== lastEventRef.current) {
      lastEventRef.current = lastEvent;
      const power = lastEvent.intensity * masterRef.current;
      const fillCount = Math.max(1, Math.round(power * BAR_COUNT));
      const newTargets = new Array(BAR_COUNT).fill(0);
      for (let i = 0; i < fillCount; i++) {
        newTargets[i] = 1.0 - (i / BAR_COUNT) * 0.3;
      }
      targetRef.current = newTargets;
    }
  }, [lastEvent]);

  useEffect(() => {
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
      }

      ctx.clearRect(0, 0, w, h);

      const bars = barsRef.current;
      const targets = targetRef.current;
      const barH = Math.max(1, (h - (BAR_COUNT - 1) * 2) / BAR_COUNT);
      const barW = w * 0.6;
      const offsetX = (w - barW) / 2;

      const cs = getComputedStyle(canvas);
      const accent = cs.getPropertyValue('--accent').trim() || '#4A9ECE';
      const muted = cs.getPropertyValue('--text-muted').trim() || '#6E7681';

      for (let i = 0; i < BAR_COUNT; i++) {
        const target = targets[i];
        const current = bars[i];

        if (target > current) {
          bars[i] = current + (target - current) * ATTACK_RATE;
        } else {
          bars[i] = current * DECAY_RATE;
        }

        if (bars[i] < 0.01) {
          bars[i] = 0;
          targets[i] = 0;
        }

        const y = h - (i + 1) * (barH + 2);
        const alpha = 0.15 + bars[i] * 0.85;

        ctx.fillStyle = bars[i] > 0.05 ? accent : muted;
        ctx.globalAlpha = alpha;
        ctx.fillRect(offsetX, y, barW * Math.max(0.15, bars[i]), barH);
      }

      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div className="flex flex-col items-center gap-1" style={{ height: '100%', minHeight: 0 }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block' }}
      />
      <span
        className="text-xs shrink-0"
        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)', fontSize: '9px' }}
      >
        POWER
      </span>
    </div>
  );
}
