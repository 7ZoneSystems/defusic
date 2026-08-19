'use client';

import { Activity } from 'lucide-react';
import { ReactNode } from 'react';

interface HeaderProps {
  status?: 'online' | 'offline' | 'analyzing';
  children?: ReactNode;
}

export default function Header({ status = 'online', children }: HeaderProps) {
  return (
    <header
      className="glass-panel flex items-center justify-between px-6 py-3"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-3">
        <Activity size={18} style={{ color: 'var(--accent)' }} strokeWidth={1.5} />
        <span
          className="font-semibold tracking-widest text-xs uppercase"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
        >
          HEARBEAT
        </span>
        <span
          className="text-xs hidden sm:inline"
          style={{ color: 'var(--text-muted)' }}
        >
          Music Analysis Engine
        </span>
      </div>
      <div className="flex items-center gap-4">
        {children}
        <span
          className="text-xs uppercase tracking-wider px-2 py-0.5"
          style={{
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-geist-mono)',
            border: '1px solid var(--border)',
            borderRadius: '2px',
          }}
        >
          STAGE 1
        </span>
        <div className="flex items-center gap-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: status === 'online' ? 'var(--success)' : status === 'analyzing' ? 'var(--warning)' : 'var(--danger)',
            }}
          />
          <span
            className="text-xs uppercase"
            style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
          >
            {status === 'analyzing' ? 'PROCESSING' : status === 'online' ? 'ENGINE READY' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  );
}
