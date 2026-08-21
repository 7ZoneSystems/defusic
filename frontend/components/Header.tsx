'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { AnalysisMode } from '@/lib/types';
import ThemeSwitcher from './ThemeSwitcher';
import UserMenu from './UserMenu';
import { ArrowLeft } from 'lucide-react';

interface HeaderProps {
  status?: 'online' | 'offline' | 'analyzing';
  mode?: AnalysisMode | null;
  backHref?: string;
  backLabel?: string;
  children?: ReactNode;
}

export default function Header({
  status = 'online',
  mode,
  backHref,
  backLabel = 'Main',
  children,
}: HeaderProps) {
  return (
    <header
      className="glass-panel flex items-center justify-between px-6 py-3 shrink-0"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-3">
        <Link
          href="/"
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/favicon.png" alt="" className="h-5 w-auto" />
          <span
            className="font-semibold tracking-widest text-xs uppercase"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-geist-mono)' }}
          >
            HEARBEAT
          </span>
        </Link>
        {backHref && (
          <Link
            href={backHref}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-sm transition-colors hover:bg-accent/20"
            style={{
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            <ArrowLeft size={12} />
            <span>{backLabel}</span>
          </Link>
        )}
      </div>
      <div className="flex items-center gap-3">
        {children}
        {mode && (
          <span
            className="text-xs uppercase tracking-wider px-2 py-0.5"
            style={{
              color: mode === 'drumming' ? 'var(--event-hihat)' : 'var(--accent)',
              fontFamily: 'var(--font-geist-mono)',
              border: `1px solid ${mode === 'drumming' ? 'var(--event-hihat)' : 'var(--accent)'}`,
              borderRadius: '2px',
            }}
          >
            {mode === 'drumming' ? 'DRUMMING' : 'MUSIC'}
          </span>
        )}
        <ThemeSwitcher />
        <UserMenu />
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
