'use client';

import { useRef } from 'react';
import { Upload, FileAudio } from 'lucide-react';

interface TrackUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function TrackUpload({ onFileSelected, disabled }: TrackUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) onFileSelected(file);
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="panel-elevated flex flex-col items-center justify-center gap-4 p-8 cursor-pointer transition-colors"
      style={{
        borderStyle: 'dashed',
        borderColor: 'var(--border)',
        borderRadius: '2px',
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
      aria-label="Upload audio file"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mp3,.mp4,.wav,.flac,.ogg,.aac,.m4a,.wma,.webm"
        onChange={handleChange}
        className="hidden"
        disabled={disabled}
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
  );
}
