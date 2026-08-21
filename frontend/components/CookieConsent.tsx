'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { X } from 'lucide-react';

const CONSENT_COOKIE_NAME = 'hearbeat_cookie_consent';
const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;

function getConsentFromCookie(): 'accepted' | 'declined' | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${CONSENT_COOKIE_NAME}=([^;]+)`));
  if (match) {
    const val = match[1];
    if (val === 'accepted' || val === 'declined') return val;
  }
  return null;
}

function writeConsentCookie(value: 'accepted' | 'declined') {
  if (typeof document === 'undefined') return;
  const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
  const secureFlag = isHttps ? '; Secure' : '';
  document.cookie = `${CONSENT_COOKIE_NAME}=${value}; Path=/; SameSite=Lax; Max-Age=${ONE_YEAR_SECONDS}${secureFlag}`;
}

export default function CookieConsent() {
  const [consent, setConsent] = useState<'accepted' | 'declined' | 'unknown'>('unknown');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    Promise.resolve().then(() => {
      setMounted(true);
      const stored = getConsentFromCookie();
      if (stored) {
        setConsent(stored);
      }
    });
  }, []);

  const handleAccept = useCallback(() => {
    writeConsentCookie('accepted');
    setConsent('accepted');
  }, []);

  const handleDecline = useCallback(() => {
    writeConsentCookie('declined');
    setConsent('declined');
  }, []);

  const handleDismiss = useCallback(() => {
    // Dismissing sets declined preference to avoid silently implying acceptance
    writeConsentCookie('declined');
    setConsent('declined');
  }, []);

  // Do not render during SSR or if consent has already been recorded
  if (!mounted || consent !== 'unknown') {
    return null;
  }

  return (
    <div
      className="fixed z-50 pointer-events-auto bottom-4 inset-x-4 sm:inset-x-auto sm:right-5 sm:bottom-5 max-w-sm w-auto sm:w-[360px]"
      role="dialog"
      aria-modal="false"
      aria-label="Cookie consent notice"
    >
      <div
        className="p-4 sm:p-5 flex flex-col items-center text-center gap-3 rounded-lg border shadow-2xl transition-all relative"
        style={{
          background: 'var(--bg-surface)',
          borderColor: 'var(--border)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.35)',
        }}
      >
        {/* Close Button top-right */}
        <button
          onClick={handleDismiss}
          className="absolute top-2.5 right-2.5 p-1 rounded-sm text-text-muted hover:text-text-primary transition-colors"
          aria-label="Close cookie notice"
        >
          <X size={15} />
        </button>

        {/* Centered Cookie Illustration */}
        <div className="flex items-center justify-center pt-1">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/cookie.png"
            alt="HearBeat Cookies"
            className="h-14 sm:h-16 w-auto object-contain select-none"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
        </div>

        {/* Title */}
        <h2
          className="text-2xl sm:text-3xl leading-none -mt-1"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-caveat)',
            fontWeight: 600,
            letterSpacing: '0.01em',
          }}
        >
          Cookies
        </h2>

        {/* Explanation Copy */}
        <p
          className="text-xs leading-relaxed max-w-[300px]"
          style={{ color: 'var(--text-secondary)' }}
        >
          HearBeat uses essential first-party cookies to keep you signed in and remember your preferences.
        </p>

        {/* Legal Links */}
        <div
          className="flex items-center justify-center gap-3 text-[11px]"
          style={{ color: 'var(--text-muted)' }}
        >
          <Link
            href="/privacy"
            className="underline hover:opacity-100 transition-opacity"
            style={{ color: 'var(--text-muted)' }}
          >
            Privacy Policy
          </Link>
          <span>·</span>
          <Link
            href="/terms"
            className="underline hover:opacity-100 transition-opacity"
            style={{ color: 'var(--text-muted)' }}
          >
            Terms of Service
          </Link>
        </div>

        {/* Action Buttons: Decline | Accept */}
        <div className="flex items-center gap-2 w-full mt-0.5">
          <button
            onClick={handleDecline}
            className="flex-1 px-3 py-1.5 text-xs rounded-sm border transition-colors hover:bg-accent/10 font-medium"
            style={{
              color: 'var(--text-muted)',
              borderColor: 'var(--border)',
              background: 'transparent',
              fontFamily: 'var(--font-geist-mono)',
            }}
            aria-label="Decline cookies"
          >
            Decline
          </button>
          <button
            onClick={handleAccept}
            className="flex-1 px-3 py-1.5 text-xs rounded-sm transition-opacity hover:opacity-90 font-medium"
            style={{
              color: 'var(--bg-primary)',
              background: 'var(--accent)',
              border: '1px solid var(--accent)',
              fontFamily: 'var(--font-geist-mono)',
            }}
            aria-label="Accept cookies"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
