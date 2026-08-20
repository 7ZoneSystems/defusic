'use client';

import { useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import { HapticConfig, HapticEvent } from '@/lib/haptic-types';
import { HapticController } from '@/lib/haptic-controller';
import HapticPanel from '@/components/HapticPanel';

interface HapticSettingsDialogProps {
  open: boolean;
  onClose: () => void;
  controller: HapticController | null;
  realHardware: boolean;
  lastEvent: HapticEvent | null;
  config: HapticConfig;
  onConfigChange: (config: HapticConfig) => void;
}

export default function HapticSettingsDialog({
  open,
  onClose,
  controller,
  realHardware,
  lastEvent,
  config,
  onConfigChange,
}: HapticSettingsDialogProps) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0, 0, 0, 0.6)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Haptic settings"
    >
      <div
        className="relative w-full max-w-md max-h-[90vh] overflow-y-auto mx-4"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: '2px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 p-1 z-10"
          style={{
            color: 'var(--text-muted)',
            border: '1px solid var(--border)',
            borderRadius: '2px',
          }}
          aria-label="Close"
        >
          <X size={14} />
        </button>

        <HapticPanel
          controller={controller}
          realHardware={realHardware}
          lastEvent={lastEvent}
          config={config}
          onConfigChange={onConfigChange}
        />
      </div>
    </div>
  );
}
