'use client';

import { useEffect, useCallback, useRef } from 'react';
import { ChevronDown, HardDrive, Music, Loader2, Sparkles } from 'lucide-react';
import { LibrarySong } from '@/lib/api';

interface SavedSongsSheetProps {
  open: boolean;
  onClose: () => void;
  queue: LibrarySong[];
  currentSongId: number | null;
  onSelectSong: (songId: number) => void;
  loading?: boolean;
}

function formatDuration(sec: number | null) {
  if (!sec) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function SavedSongsSheet({
  open,
  onClose,
  queue,
  currentSongId,
  onSelectSong,
  loading = false,
}: SavedSongsSheetProps) {
  const touchStartY = useRef<number | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartY.current === null) return;
    const deltaY = e.changedTouches[0].clientY - touchStartY.current;
    touchStartY.current = null;
    // Swipe down on sheet closes it
    if (deltaY > 40) {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end select-none"
      style={{
        background: 'rgba(0, 0, 0, 0.55)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Saved Songs"
    >
      <style>{`
        @keyframes sheetSlideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        .sheet-animated {
          animation: sheetSlideUp 260ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>

      <div
        className="w-full max-w-lg mx-auto flex flex-col max-h-[70vh] sm:max-h-[55vh] overflow-hidden sheet-animated"
        style={{
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border)',
          borderLeft: '1px solid var(--border)',
          borderRight: '1px solid var(--border)',
          borderTopLeftRadius: '14px',
          borderTopRightRadius: '14px',
          boxShadow: '0 -8px 32px rgba(0,0,0,0.4)',
        }}
        onClick={(e) => e.stopPropagation()}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* Drag Handle & Header */}
        <div
          className="flex flex-col items-center pt-2.5 pb-2 px-5 cursor-pointer select-none shrink-0"
          style={{ borderBottom: '1px solid var(--border-subtle)' }}
          onClick={onClose}
        >
          {/* Handle bar */}
          <div
            className="w-10 h-1 rounded-full mb-1 opacity-60 hover:opacity-100 transition-opacity"
            style={{ background: 'var(--text-muted)' }}
          />
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2.5">
              <span
                className="leading-none text-2xl"
                style={{
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-caveat)',
                  fontWeight: 600,
                  letterSpacing: '0.02em',
                }}
              >
                Saved Songs
              </span>
              {queue.length > 0 && (
                <span
                  className="text-[11px] px-2 py-0.5 rounded-full"
                  style={{
                    color: 'var(--text-muted)',
                    background: 'var(--bg-elevated)',
                    fontFamily: 'var(--font-geist-mono)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  {queue.length}
                </span>
              )}
            </div>

            <button
              onClick={onClose}
              className="p-1 rounded-sm text-text-muted hover:text-text-primary transition-colors"
              aria-label="Close saved songs"
            >
              <ChevronDown size={18} />
            </button>
          </div>
        </div>

        {/* Song List Content */}
        <div className="flex-1 overflow-y-auto p-2.5 space-y-1 scrollbar-thin">
          {loading && queue.length === 0 ? (
            <div className="flex items-center justify-center py-12 gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
              <Loader2 size={16} className="animate-spin" />
              <span>Loading saved songs...</span>
            </div>
          ) : queue.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <Sparkles size={20} className="mb-2 opacity-40" style={{ color: 'var(--gold)' }} />
              <p
                className="text-2xl"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-caveat)',
                  fontWeight: 600,
                }}
              >
                Nothing saved
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-sans)' }}>
                Analyze and save tracks to see them here.
              </p>
            </div>
          ) : (
            queue.map((song, idx) => {
              const isCurrent = song.id === currentSongId;
              return (
                <button
                  key={song.id}
                  onClick={() => {
                    if (song.id !== currentSongId) {
                      onSelectSong(song.id);
                    }
                    onClose();
                  }}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left group"
                  style={{
                    background: isCurrent
                      ? 'color-mix(in srgb, var(--accent-surface) 60%, var(--bg-elevated))'
                      : 'transparent',
                    border: isCurrent ? '1px solid var(--accent)' : '1px solid transparent',
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1 pr-3">
                    {/* Status dot / track number */}
                    <div className="w-4 h-4 flex items-center justify-center shrink-0">
                      {isCurrent ? (
                        <div
                          className="w-2 h-2 rounded-full animate-pulse"
                          style={{ background: 'var(--accent)', boxShadow: '0 0 6px var(--accent)' }}
                        />
                      ) : (
                        <span
                          className="text-[11px] text-text-muted font-mono group-hover:hidden"
                          style={{ fontFamily: 'var(--font-geist-mono)' }}
                        >
                          {idx + 1}
                        </span>
                      )}
                      {!isCurrent && (
                        <Music
                          size={12}
                          className="hidden group-hover:block"
                          style={{ color: 'var(--text-secondary)' }}
                        />
                      )}
                    </div>

                    <span
                      className="text-xs truncate font-medium"
                      style={{
                        color: isCurrent ? 'var(--text-primary)' : 'var(--text-secondary)',
                        fontWeight: isCurrent ? 600 : 400,
                      }}
                    >
                      {song.filename}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {song.duration_seconds ? (
                      <span
                        className="text-[11px] tabular-nums"
                        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
                      >
                        {formatDuration(song.duration_seconds)}
                      </span>
                    ) : null}

                    {song.drive_file_id && (
                      <HardDrive size={11} style={{ color: 'var(--text-muted)' }} />
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
