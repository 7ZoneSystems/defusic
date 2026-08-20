'use client';

import { useRef, useEffect } from 'react';
import { HapticEvent } from '@/lib/haptic-types';

interface HapticResponseVisualizerProps {
  lastEvent: HapticEvent | null;
}

const MAX_DURATION_MS = 250;
const RING_COUNT = 7;
const DECAY_RATE = 0.94;

export default function HapticResponseVisualizer({ lastEvent }: HapticResponseVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ringsRef = useRef<number[]>(new Array(RING_COUNT).fill(0));
  const rafRef = useRef<number>(0);
  const lastEventRef = useRef<HapticEvent | null>(null);

  useEffect(() => {
    if (lastEvent && lastEvent !== lastEventRef.current) {
      lastEventRef.current = lastEvent;
      const normalizedDuration = Math.min(1, lastEvent.duration_ms / MAX_DURATION_MS);
      const rings = ringsRef.current;
      rings.shift();
      rings.push(normalizedDuration);
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

      const rings = ringsRef.current;
      const centerX = w / 2;
      const maxRadius = Math.min(w, h) * 0.4;

      const cs = getComputedStyle(canvas);
      const hihat = cs.getPropertyValue('--event-hihat').trim() || '#4ACE7A';
      const bass = cs.getPropertyValue('--event-bass').trim() || '#CE6A4A';
      const accent = cs.getPropertyValue('--accent').trim() || '#4A9ECE';

      const colors = [hihat, bass, accent, hihat, bass];

      for (let i = 0; i < RING_COUNT; i++) {
        const ring = rings[i];
        rings[i] = ring * DECAY_RATE;
        if (rings[i] < 0.01) rings[i] = 0;

        const radius = maxRadius * (0.15 + i * 0.12);
        const alpha = 0.25 + rings[i] * 0.75;
        const lineWidth = 2 + rings[i] * 5;

        ctx.beginPath();
        ctx.arc(centerX, h / 2, radius, 0, Math.PI * 2);
        ctx.strokeStyle = colors[i];
        ctx.globalAlpha = alpha;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
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
        RESPONSE
      </span>
    </div>
  );
}
