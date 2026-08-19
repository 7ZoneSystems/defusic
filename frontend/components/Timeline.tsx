'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { AnalysisResult } from '@/lib/types';
import { resolveToken, resolveTokenAlpha } from '@/lib/theme-utils';

interface TimelineProps {
  result: AnalysisResult;
  currentTime: number;
  onSeek: (time: number) => void;
}

const LANE_HEIGHT = 28;
const LANES = [
  { key: 'beat', label: 'BEAT', token: '--event-beat' },
  { key: 'bass', label: 'BASS', token: '--text-muted' },
  { key: 'bass_beat', label: 'BASS+BEAT', token: '--event-bass' },
  { key: 'bass_offbeat', label: 'OFFBEAT', token: '--event-bass-offbeat' },
  { key: 'bass_accent', label: 'ACCENT', token: '--event-bass-accent' },
  { key: 'bass_activity', label: 'BASS ACTIVITY', token: '--event-bass-activity' },
];

export default function Timeline({ result, currentTime, onSeek }: TimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [scrollX, setScrollX] = useState(0);

  const duration = result.source.duration_seconds;
  const events = result.events;

  const getEventLane = (type: string) => {
    const idx = LANES.findIndex((l) => l.key === type);
    return idx >= 0 ? idx : -1;
  };

  const timeToX = useCallback(
    (time: number, width: number) => {
      const visibleDuration = duration / zoom;
      const offset = scrollX * (duration - visibleDuration);
      return ((time - offset) / visibleDuration) * width;
    },
    [duration, zoom, scrollX]
  );

  const xToTime = useCallback(
    (x: number, width: number) => {
      const visibleDuration = duration / zoom;
      const offset = scrollX * (duration - visibleDuration);
      return (x / width) * visibleDuration + offset;
    },
    [duration, zoom, scrollX]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resolve theme tokens at draw time
    const bgPrimary = resolveToken('--bg-surface');
    const bgRowEven = resolveToken('--row-even');
    const bgRowOdd = resolveToken('--row-odd');
    const bgElevated = resolveToken('--bg-elevated');
    const border = resolveToken('--border');
    const textMuted = resolveToken('--text-muted');
    const textPrimary = resolveToken('--text-primary');
    const textSecondary = resolveToken('--text-secondary');

    const laneColors = LANES.map((l) => resolveToken(l.token));

    const dpr = window.devicePixelRatio || 1;
    const rect = container.getBoundingClientRect();
    const w = rect.width;
    const headerH = 24;
    const lanesH = LANES.length * LANE_HEIGHT;
    const totalH = headerH + lanesH + 30;

    canvas.width = w * dpr;
    canvas.height = totalH * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${totalH}px`;
    ctx.scale(dpr, dpr);

    ctx.fillStyle = bgPrimary;
    ctx.fillRect(0, 0, w, totalH);

    const visibleDuration = duration / zoom;
    const offset = scrollX * (duration - visibleDuration);

    // Time ruler
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    const tickInterval = visibleDuration > 60 ? 10 : visibleDuration > 20 ? 5 : visibleDuration > 5 ? 1 : 0.5;
    const firstTick = Math.floor(offset / tickInterval) * tickInterval;

    ctx.font = '10px var(--font-geist-mono), monospace';
    ctx.fillStyle = textMuted;
    ctx.textAlign = 'center';

    for (let t = firstTick; t <= offset + visibleDuration; t += tickInterval) {
      const x = timeToX(t, w);
      if (x < 0 || x > w) continue;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, headerH);
      ctx.stroke();
      ctx.fillText(`${t.toFixed(1)}s`, x, 16);
    }

    // Lane backgrounds
    for (let i = 0; i < LANES.length; i++) {
      const y = headerH + i * LANE_HEIGHT;
      ctx.fillStyle = i % 2 === 0 ? bgRowEven : bgRowOdd;
      ctx.fillRect(0, y, w, LANE_HEIGHT);
      // Lane label
      ctx.fillStyle = textMuted;
      ctx.font = '9px var(--font-geist-mono), monospace';
      ctx.textAlign = 'left';
      ctx.fillText(LANES[i].label, 4, y + LANE_HEIGHT / 2 + 3);
    }

    // Events
    for (const event of events) {
      const lane = getEventLane(event.type);
      if (lane < 0) continue;

      const x = timeToX(event.time, w);
      if (x < -2 || x > w + 2) continue;

      const y = headerH + lane * LANE_HEIGHT;
      const barH = 4 + event.strength * (LANE_HEIGHT - 8);

      ctx.globalAlpha = 0.3 + 0.7 * event.strength;
      ctx.fillStyle = laneColors[lane];

      // Draw activity events as wider bars
      if (event.type === 'bass_activity' && event.duration && event.duration > 0) {
        const endX = timeToX(event.time + event.duration, w);
        const barW = Math.max(2, endX - x);
        ctx.fillRect(x, y + (LANE_HEIGHT - barH) / 2, barW, barH);
      } else {
        ctx.fillRect(x - 1, y + (LANE_HEIGHT - barH) / 2, 2, barH);
      }

      ctx.globalAlpha = 1;
    }

    // Playhead
    const playX = timeToX(currentTime, w);
    if (playX >= 0 && playX <= w) {
      ctx.strokeStyle = textPrimary;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(playX, 0);
      ctx.lineTo(playX, totalH);
      ctx.stroke();
      ctx.setLineDash([]);
      // Playhead label
      ctx.fillStyle = textPrimary;
      ctx.font = '9px var(--font-geist-mono), monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${currentTime.toFixed(2)}s`, playX, totalH - 4);
    }

    // Hover cursor
    if (hoverTime !== null) {
      const hx = timeToX(hoverTime, w);
      if (hx >= 0 && hx <= w) {
        ctx.strokeStyle = resolveTokenAlpha('--text-primary', 0.3);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(hx, 0);
        ctx.lineTo(hx, totalH);
        ctx.stroke();

        // Find nearest event for tooltip
        let nearestEvent = null;
        let nearestDist = Infinity;
        for (const event of events) {
          const ex = timeToX(event.time, w);
          const dist = Math.abs(ex - hx);
          if (dist < 10 && dist < nearestDist) {
            nearestDist = dist;
            nearestEvent = event;
          }
        }

        if (nearestEvent) {
          const tooltipX = Math.min(hx + 8, w - 120);
          const tooltipY = headerH + LANES.length * LANE_HEIGHT + 4;
          ctx.fillStyle = bgElevated;
          ctx.fillRect(tooltipX, tooltipY, 116, 40);
          ctx.strokeStyle = border;
          ctx.strokeRect(tooltipX, tooltipY, 116, 40);
          ctx.fillStyle = textPrimary;
          ctx.font = '9px var(--font-geist-mono), monospace';
          ctx.textAlign = 'left';
          ctx.fillText(`${nearestEvent.type}`, tooltipX + 4, tooltipY + 12);
          ctx.fillText(`t=${nearestEvent.time.toFixed(3)}s str=${nearestEvent.strength.toFixed(2)}`, tooltipX + 4, tooltipY + 24);
          if (nearestEvent.beat_delta_seconds != null) {
            ctx.fillText(`delta=${nearestEvent.beat_delta_seconds >= 0 ? '+' : ''}${nearestEvent.beat_delta_seconds.toFixed(4)}s`, tooltipX + 4, tooltipY + 36);
          }
        } else {
          ctx.fillStyle = textSecondary;
          ctx.font = '9px var(--font-geist-mono), monospace';
          ctx.textAlign = 'center';
          ctx.fillText(`${hoverTime.toFixed(3)}s`, hx, headerH + LANES.length * LANE_HEIGHT + 16);
        }
      }
    }
  }, [result, currentTime, hoverTime, zoom, scrollX, timeToX, duration, events]);

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = xToTime(x, rect.width);
    if (time >= 0 && time <= duration) onSeek(time);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setHoverTime(xToTime(x, rect.width));
  };

  const headerH = 24;
  const lanesH = LANES.length * LANE_HEIGHT;
  const totalH = headerH + lanesH + 30;

  return (
    <div className="panel flex flex-col">
      <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          Timeline
        </span>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {LANES.map((lane) => (
              <div key={lane.key} className="flex items-center gap-1">
                <div className="w-2 h-2" style={{ background: `var(${lane.token})`, borderRadius: '1px' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{lane.label}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setZoom((z) => Math.max(1, z / 1.5))}
              className="px-1.5 py-0.5 text-xs"
              style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '2px' }}
              aria-label="Zoom out"
            >
              -
            </button>
            <span className="text-xs w-12 text-center" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
              {zoom.toFixed(1)}x
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(20, z * 1.5))}
              className="px-1.5 py-0.5 text-xs"
              style={{ color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '2px' }}
              aria-label="Zoom in"
            >
              +
            </button>
          </div>
        </div>
      </div>
      <div ref={containerRef} className="relative overflow-hidden" style={{ height: `${totalH}px` }}>
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-crosshair"
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => { setHoverTime(null); }}
        />
      </div>
      <div className="px-3 py-1.5 flex items-center gap-2" style={{ borderTop: '1px solid var(--border)' }}>
        <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}>
          Scroll to zoom
        </span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.001}
          value={scrollX}
          onChange={(e) => setScrollX(parseFloat(e.target.value))}
          className="flex-1"
          aria-label="Timeline scroll"
        />
      </div>
    </div>
  );
}
