'use client';

import { useRef, useCallback } from 'react';
import { Upload, FileAudio } from 'lucide-react';

interface TrackUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function TrackUpload({ onFileSelected, disabled }: TrackUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelected(file);
      e.target.value = '';
    }
  }, [onFileSelected]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files[0];
    if (file) onFileSelected(file);
  }, [onFileSelected]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className="flex flex-col items-center justify-center gap-4 p-8"
      style={{
        border: '1px dashed var(--border)',
        borderRadius: '2px',
        background: 'var(--bg-elevated)',
      }}
    >
      {/* Visually hidden but NOT display:none — .click() works */}
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,video/mp4"
        onChange={handleChange}
        disabled={disabled}
        aria-label="Upload audio file"
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          borderWidth: 0,
        }}
      />

      <FileAudio size={32} style={{ color: 'var(--text-muted)' }} strokeWidth={1} />

      <div className="text-center">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Drop an MP3 or MP4
        </p>
        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          or choose a file
        </p>
      </div>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-1.5 text-xs uppercase tracking-wider"
        style={{
          color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
          borderRadius: '2px',
          fontFamily: 'var(--font-geist-mono)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          background: 'transparent',
        }}
      >
        <Upload size={12} />
        Choose file
      </button>
    </div>
  );
}
