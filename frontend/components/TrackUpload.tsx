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
      // Reset the input so re-selecting the same file triggers onChange
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
      className="panel-elevated flex flex-col items-center justify-center gap-4 p-8"
      style={{
        borderStyle: 'dashed',
        borderColor: 'var(--border)',
        borderRadius: '2px',
      }}
    >
      {/*
        Standard HTML file input.
        Kept visible but positioned to overlap the drop zone.
        Using opacity:0 + absolute positioning so Android browsers
        can reliably open the native file picker on tap.
        No pointer-events:none, no disabled overlays, no form submission.
      */}
      <div className="relative w-full">
        <input
          ref={inputRef}
          type="file"
          accept="audio/*,video/mp4"
          onChange={handleChange}
          disabled={disabled}
          aria-label="Upload audio file"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            opacity: 0,
            cursor: disabled ? 'not-allowed' : 'pointer',
            zIndex: 10,
          }}
        />
        <div
          className="flex flex-col items-center justify-center gap-4 p-4 pointer-events-none"
          aria-hidden="true"
        >
          <FileAudio size={32} style={{ color: 'var(--text-muted)' }} strokeWidth={1} />
          <div className="text-center">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Drop an MP3 or MP4
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              or choose a file
            </p>
          </div>
          <div
            className="flex items-center gap-2 px-3 py-1.5 text-xs uppercase tracking-wider"
            style={{
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            <Upload size={12} />
            Choose file
          </div>
        </div>
      </div>
    </div>
  );
}
