/**
 * Haptic driver abstraction.
 *
 * Phone vibration motors are not audio-frequency speakers.
 * We translate musical meaning into tactile patterns, not frequencies.
 */

import { HapticDriverResult } from './haptic-types';

export interface HapticDriver {
  /** Check if the driver is available on this device/browser. */
  check(): HapticDriverResult;

  /** Fire a single haptic pulse. */
  vibrate(intensity: number, duration_ms: number): void;

  /** Cancel any in-progress vibration. */
  cancel(): void;

  /** Whether this driver provides real hardware feedback. */
  readonly isReal: boolean;
}

/**
 * Web Vibration API driver.
 *
 * Limitations:
 * - navigator.vibrate() does NOT support amplitude control on most browsers.
 * - We approximate intensity through duration scaling when amplitude is unavailable.
 * - iOS Safari does not support the Vibration API at all.
 */
export class WebVibrationDriver implements HapticDriver {
  readonly isReal = true;

  check(): HapticDriverResult {
    if (typeof navigator === 'undefined' || !navigator.vibrate) {
      return { supported: false, capability: 'none' };
    }
    // The standard Vibration API provides timing only, not amplitude.
    return { supported: true, capability: 'vibrate-only' };
  }

  vibrate(intensity: number, duration_ms: number): void {
    if (!navigator.vibrate) return;

    // Clamp values
    const dur = Math.max(1, Math.round(duration_ms));
    const int = Math.max(0, Math.min(1, intensity));

    // If intensity is very low, skip (avoid meaningless vibration)
    if (int < 0.05) return;

    // The standard API only accepts a duration or pattern.
    // Approximate intensity by scaling duration.
    // Higher intensity = full duration; lower = shorter effective pulse.
    const effectiveDuration = Math.round(dur * (0.3 + 0.7 * int));

    navigator.vibrate(effectiveDuration);
  }

  cancel(): void {
    if (navigator.vibrate) {
      navigator.vibrate(0);
    }
  }
}

/**
 * Mock driver for desktop/development.
 *
 * Does NOT produce any physical vibration.
 * Logs events to console for debugging.
 */
export class MockHapticDriver implements HapticDriver {
  readonly isReal = false;
  lastEvent: { intensity: number; duration_ms: number; timestamp: number } | null = null;

  check(): HapticDriverResult {
    return { supported: true, capability: 'none' };
  }

  vibrate(intensity: number, duration_ms: number): void {
    this.lastEvent = {
      intensity,
      duration_ms,
      timestamp: Date.now(),
    };
  }

  cancel(): void {
    this.lastEvent = null;
  }
}

/**
 * Factory: create the best available driver.
 */
export function createHapticDriver(): HapticDriver {
  const web = new WebVibrationDriver();
  const result = web.check();
  if (result.supported) {
    return web;
  }
  return new MockHapticDriver();
}
