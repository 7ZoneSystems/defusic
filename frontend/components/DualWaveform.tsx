'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { WaveformData } from '@/lib/types';
import { resolveToken, resolveTokenAlpha } from '@/lib/theme-utils';

interface DualWaveformProps {
  originalData: WaveformData | null;
  diagnosticData: number[] | null;
  duration: number;
  currentTime: number;
  onSeek: (time: number) => void;
  originalVolume: number;
  diagnosticVolume: number;
}

export default function DualWaveform({
  originalData,
  diagnosticData,
  duration,
  currentTime,
  onSeek,
  originalVolume,
  diagnosticVolume,
}: DualWaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resolve theme tokens at draw time
    const bgSurface = resolveToken('--bg-surface');
    const bgPrimary = resolveToken('--bg-primary');
    const textMuted = resolveToken('--text-muted');
    const textSecondary = resolveToken('--text-secondary');
    const textPrimary = resolveToken('--text-primary');
    const eventBeat = resolveToken('--event-beat');
    const eventBass = resolveToken('--event-bass');

    const dpr = window.devicePixelRatio || 1;
    const rect = container.getBoundingClientRect();
    const w = rect.width;
    const trackH = 60;
    const gap = 8;
    const totalH = trackH * 2 + gap;

    canvas.width = w * dpr;
    canvas.height = totalH * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${totalH}px`;
    ctx.scale(dpr, dpr);

    // Background
    ctx.fillStyle = bgSurface;
    ctx.fillRect(0, 0, w, totalH);

    // Draw original waveform (top track)
    if (originalData && originalData.waveform.length > 0) {
      drawWaveform(ctx, originalData.waveform, w, trackH, 0, eventBeat, originalVolume);
      // Label
      ctx.fillStyle = textMuted;
      ctx.font = '9px var(--font-geist-mono), monospace';
      ctx.textAlign = 'left';
      ctx.fillText('ORIGINAL', 4, 12);
    }

    // Draw diagnostic waveform (bottom track)
    if (diagnosticData && diagnosticData.length > 0) {
      drawWaveform(ctx, diagnosticData, w, trackH, trackH + gap, eventBass, diagnosticVolume);
      // Label
      ctx.fillStyle = textMuted;
      ctx.font = '9px var(--font-geist-mono), monospace';
      ctx.textAlign = 'left';
      ctx.fillText('GENERATED', 4, trackH + gap + 12);
    }

    // Time ruler
    ctx.fillStyle = bgPrimary;
    ctx.fillRect(0, totalH - 16, w, 16);
    ctx.fillStyle = textMuted;
    ctx.font = '9px var(--font-geist-mono), monospace';
    ctx.textAlign = 'center';
    const numLabels = Math.min(10, Math.max(3, Math.floor(w / 80)));
    for (let i = 0; i <= numLabels; i++) {
      const t = (duration / numLabels) * i;
      const x = (t / duration) * w;
      ctx.fillText(`${t.toFixed(1)}s`, x, totalH - 4);
    }

    // Playhead cursor
    const playX = duration > 0 ? (currentTime / duration) * w : 0;
    ctx.strokeStyle = textPrimary;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(playX, 0);
    ctx.lineTo(playX, totalH - 16);
    ctx.stroke();
    ctx.setLineDash([]);

    // Hover cursor
    if (hoverX !== null) {
      ctx.strokeStyle = resolveTokenAlpha('--text-primary', 0.3);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hoverX, 0);
      ctx.lineTo(hoverX, totalH - 16);
      ctx.stroke();
      // Time tooltip
      const hoverTime = (hoverX / w) * duration;
      ctx.fillStyle = textSecondary;
      ctx.font = '9px var(--font-geist-mono), monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${hoverTime.toFixed(3)}s`, hoverX, totalH - 20);
    }
  }, [originalData, diagnosticData, duration, currentTime, originalVolume, diagnosticVolume, hoverX]);

  useEffect(() => {
    draw();
  }, [draw]);

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = (x / rect.width) * duration;
    if (time >= 0 && time <= duration) onSeek(time);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    setHoverX(e.clientX - rect.left);
  };

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
          Waveform Comparison
        </span>
        <span
          className="text-xs"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          {duration.toFixed(1)}s
        </span>
      </div>
      <div ref={containerRef} className="relative overflow-hidden" style={{ height: '140px' }}>
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-crosshair"
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverX(null)}
        />
      </div>
    </div>
  );
}

function drawWaveform(
  ctx: CanvasRenderingContext2D,
  data: number[],
  width: number,
  height: number,
  yOffset: number,
  color: string,
  volume: number,
) {
  const n = data.length;
  const barWidth = Math.max(1, width / n);
  const midY = yOffset + height / 2;

  ctx.save();
  ctx.globalAlpha = 0.3 + 0.7 * volume;

  for (let i = 0; i < n; i++) {
    const x = (i / n) * width;
    const amplitude = data[i] * volume;
    const barH = amplitude * height;

    ctx.fillStyle = color;
    ctx.fillRect(x, midY - barH / 2, barWidth, barH);
  }

  ctx.restore();
}
