'use client';

import { useRef, useCallback } from 'react';
import { useTheme } from '@/lib/theme';

interface TrackUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function TrackUpload({ onFileSelected, disabled }: TrackUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { resolved } = useTheme();

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

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  return (
    <div
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      className="flex flex-col items-center justify-center gap-3 cursor-pointer"
      style={{
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : undefined,
      }}
    >
      <input
        ref={inputRef}
        id="file-upload-input"
        type="file"
        accept="audio/*,video/mp4"
        onChange={handleChange}
        disabled={disabled}
        aria-label="Upload audio file"
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }}
      />

      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={resolved === 'light' ? '/choose_files_light.png' : '/choose_files_dark.png'}
        alt="Choose music files"
        className="w-[clamp(200px,55vw,340px)] md:w-[clamp(140px,18vw,200px)] h-auto"
      />

      <p
        className="text-sm text-center"
        style={{
          color: 'var(--text-muted)',
          fontStyle: 'italic',
          fontFamily: 'Georgia, "Times New Roman", serif',
        }}
      >
        May I have your music files?
      </p>
    </div>
  );
}
