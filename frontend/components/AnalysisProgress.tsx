'use client';

import { Loader } from 'lucide-react';

interface AnalysisProgressProps {
  stage?: string;
}

const STAGES = ['AUDIO', 'RHYTHM', 'BASS', 'EVENTS'];

export default function AnalysisProgress({ stage }: AnalysisProgressProps) {
  return (
    <div className="panel-elevated p-6 flex flex-col items-center gap-4">
      <Loader size={24} style={{ color: 'var(--accent)' }} className="animate-spin-slow" />
      <div className="flex items-center gap-2">
        {STAGES.map((s, i) => {
          const isActive = stage?.toUpperCase().includes(s.toLowerCase()) || (!stage && i === 0);
          return (
            <div key={s} className="flex items-center gap-2">
              {i > 0 && <div className="w-4 h-px" style={{ background: 'var(--border)' }} />}
              <div className="flex items-center gap-1.5">
                <div
                  className="w-1.5 h-1.5"
                  style={{
                    background: isActive ? 'var(--accent)' : 'var(--border)',
                    borderRadius: '1px',
                  }}
                />
                <span
                  className="text-xs uppercase tracking-wider"
                  style={{
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                    fontFamily: 'var(--font-geist-mono)',
                  }}
                >
                  {s}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Analyzing track...
      </p>
    </div>
  );
}
