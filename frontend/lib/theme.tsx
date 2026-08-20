'use client';

import { createContext, useContext, useEffect, useCallback, useSyncExternalStore, ReactNode } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';
type ResolvedTheme = 'light' | 'dark';

interface ThemeContextValue {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'hearbeat-theme';

// ---------------------------------------------------------------------------
// External store for theme preference (SSR-safe via useSyncExternalStore)
// ---------------------------------------------------------------------------

let prefListeners: Array<() => void> = [];

function emitPrefChange() {
  for (const l of prefListeners) l();
}

function getPrefSnapshot(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  } catch { /* ignore */ }
  return 'system';
}

function getPrefServerSnapshot(): ThemePreference {
  return 'system';
}

function subscribePref(callback: () => void) {
  prefListeners.push(callback);
  return () => { prefListeners = prefListeners.filter((l) => l !== callback); };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(resolved: ResolvedTheme) {
  document.documentElement.setAttribute('data-theme', resolved);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ThemeProvider({ children }: { children: ReactNode }) {
  const preference = useSyncExternalStore(subscribePref, getPrefSnapshot, getPrefServerSnapshot);

  // Derive resolved theme (no useState, no cascading renders)
  const resolved: ResolvedTheme = preference === 'system' ? resolveSystemTheme() : preference;

  // Sync resolved theme to DOM whenever it changes
  useEffect(() => {
    applyTheme(resolved);
  }, [resolved]);

  // Listen for real-time system color-scheme changes when preference is 'system'
  useEffect(() => {
    if (preference !== 'system') return;
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const handler = (e: MediaQueryListEvent) => {
      applyTheme(e.matches ? 'light' : 'dark');
    };
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [preference]);

  const setPreference = useCallback((p: ThemePreference) => {
    try {
      localStorage.setItem(STORAGE_KEY, p);
    } catch { /* ignore */ }
    applyTheme(p === 'system' ? resolveSystemTheme() : p);
    emitPrefChange();
  }, []);

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // During SSR or outside provider, return safe defaults
    return {
      preference: 'system',
      resolved: 'dark',
      setPreference: () => {},
    };
  }
  return ctx;
}
