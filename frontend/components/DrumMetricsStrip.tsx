'use client';

import { Music, Drum, Target, Percent } from 'lucide-react';
import { AnalysisResult } from '@/lib/types';

interface DrumMetricsStripProps {
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

export default function DrumMetricsStrip({ result }: DrumMetricsStripProps) {
  const drumEvents = result.events.filter(
    (e) => e.type !== 'beat' && e.type !== 'bass'
  );
  const kicks = drumEvents.filter((e) => e.type === 'kick').length;
  const snares = drumEvents.filter((e) => e.type === 'snare').length;
  const hats = drumEvents.filter((e) => e.type === 'hihat').length;
  const generic = drumEvents.filter((e) => e.type === 'drum_onset').length;

  const classifiedCount = kicks + snares + hats;
  const classifiedPct = drumEvents.length > 0
    ? ((classifiedCount / drumEvents.length) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-px" style={{ background: 'var(--border)' }}>
      <MetricCard
        label="BPM"
        value={result.rhythm.bpm.toFixed(2)}
        detail={`Confidence: ${(result.rhythm.confidence * 100).toFixed(0)}%`}
        icon={<Music size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Drum Events"
        value={String(drumEvents.length)}
        detail={`${result.rhythm.beat_count} beats`}
        icon={<Drum size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Kicks"
        value={String(kicks)}
        detail={`${snares} snares, ${hats} hats`}
        icon={<Target size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Classified"
        value={`${classifiedPct}%`}
        detail={`${classifiedCount} of ${drumEvents.length}`}
        icon={<Percent size={14} strokeWidth={1.5} />}
      />
      <MetricCard
        label="Generic"
        value={String(generic)}
        detail="drum_onset events"
        icon={<Drum size={14} strokeWidth={1.5} />}
      />
    </div>
  );
}
