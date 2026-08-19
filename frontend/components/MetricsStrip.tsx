'use client';

import { Music, Waves, Drum, Target } from 'lucide-react';
import { AnalysisResult } from '@/lib/types';

interface MetricsStripProps {
  result: AnalysisResult;
}

interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  icon: React.ReactNode;
}

function MetricCard({ label, value, detail, icon }: MetricCardProps) {
  return (
    <div className="panel-elevated px-4 py-3 flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
        >
          {label}
        </span>
      </div>
      <span
        className="text-2xl font-semibold truncate"
        style={{ color: 'var(--accent)', fontFamily: 'var(--font-geist-mono)' }}
      >
        {value}
      </span>
      {detail && (
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {detail}
        </span>
      )}
    </div>
  );
}

export default function MetricsStrip({ result }: MetricsStripProps) {
  const bassEvents = result.events.filter((e) => e.type !== 'beat');
  const onBeatCount = result.events.filter(
    (e) => e.type === 'bass_beat' || e.type === 'bass_accent'
  ).length;
  const onBeatPct = bassEvents.length > 0
    ? ((onBeatCount / bassEvents.length) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-px" style={{ background: 'var(--border)' }}>
      <MetricCard
        label="BPM"
        value={result.rhythm.bpm.toFixed(2)}
        detail={`Confidence: ${(result.rhythm.confidence * 100).toFixed(0)}%`}
        icon={<Music size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Beats"
        value={String(result.rhythm.beat_count)}
        detail={`${result.source.duration_seconds.toFixed(1)}s duration`}
        icon={<Waves size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Bass Events"
        value={String(bassEvents.length)}
        detail={`${result.bass_events_raw.length} raw detections`}
        icon={<Drum size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="On-Beat"
        value={`${onBeatPct}%`}
        detail={`${onBeatCount} of ${bassEvents.length} events`}
        icon={<Target size={14} strokeWidth={1.5} />}
      />
    </div>
  );
}
