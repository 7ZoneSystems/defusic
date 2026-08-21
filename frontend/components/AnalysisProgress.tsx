'use client';

import { useState, useEffect } from 'react';
import { useTheme } from '@/lib/theme';

const MESSAGES = [
  "waiting is so hard ",
  "i am sorry servers are slow nowdays 😢",
  "trying harder",
  "this is just one time then you can save song if you are signed it 😄",
  "doing itttt",
  "almost done",
];

export default function AnalysisProgress() {
  const { resolved } = useTheme();
  const [msgIndex, setMsgIndex] = useState(0);
  const [fade, setFade] = useState(true);

  const imgSrc = resolved === 'light' ? '/loading_light.png' : '/loading_dark.png';

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setMsgIndex((prev) => (prev + 1) % MESSAGES.length);
        setFade(true);
      }, 300);
    }, 3800);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className="flex flex-col items-center justify-center w-full px-4 text-center select-none"
      role="status"
      aria-live="polite"
      aria-label="Processing audio"
    >
      <style>{`
        @keyframes dotSequence {
          0%, 100% {
            opacity: 0.25;
            transform: scale(0.8);
          }
          33% {
            opacity: 1;
            transform: scale(1.25);
          }
          66% {
            opacity: 0.25;
            transform: scale(0.8);
          }
        }
        .loading-dot-1 {
          animation: dotSequence 1.5s ease-in-out infinite;
          animation-delay: 0s;
        }
        .loading-dot-2 {
          animation: dotSequence 1.5s ease-in-out infinite;
          animation-delay: 0.25s;
        }
        .loading-dot-3 {
          animation: dotSequence 1.5s ease-in-out infinite;
          animation-delay: 0.5s;
        }
      `}</style>

      {/* Main loading artwork */}
      <div className="relative flex items-center justify-center w-full max-w-[650px] mb-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgSrc}
          alt="HearBeat processing"
          className="w-full h-auto object-contain"
          style={{
            maxHeight: 'min(420px, 45vh)',
            width: 'clamp(260px, 88vw, 650px)',
          }}
        />
      </div>

      {/* Animated three-dot sequence */}
      <div className="flex items-center justify-center gap-3 mb-3" aria-hidden="true">
        <span
          className="loading-dot-1 inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: 'var(--text-primary)' }}
        />
        <span
          className="loading-dot-2 inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: 'var(--text-primary)' }}
        />
        <span
          className="loading-dot-3 inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: 'var(--text-primary)' }}
        />
      </div>

      {/* Rotating cursive message */}
      <div
        className="flex items-center justify-center min-h-[3.2rem] px-4 max-w-md w-full transition-opacity duration-300"
        style={{ opacity: fade ? 1 : 0 }}
      >
        <p
          className="text-center leading-relaxed tracking-wide"
          style={{
            fontFamily: 'var(--font-caveat)',
            fontSize: 'clamp(1.3rem, 3.8vw, 1.65rem)',
            color: 'var(--text-secondary)',
          }}
        >
          {MESSAGES[msgIndex]}
        </p>
      </div>
    </div>
  );
}
