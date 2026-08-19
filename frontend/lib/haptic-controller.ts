/**
 * HapticController — manages haptic event scheduling, playback sync, and device control.
 *
 * Consumes a HapticTimeline from the backend and schedules events
 * synchronized with audio playback.
 */

import { HapticEvent, HapticTimeline } from './haptic-types';
import { HapticDriver } from './haptic-driver';

const SCHEDULE_AHEAD_MS = 200;
const TICK_INTERVAL_MS = 50;

export interface HapticControllerCallbacks {
  onEvent?: (event: HapticEvent) => void;
  onStateChange?: (state: 'idle' | 'playing' | 'paused') => void;
}

export class HapticController {
  private driver: HapticDriver;
  private timeline: HapticTimeline | null = null;
  private enabled = false;
  private playing = false;
  private startTime = 0;
  private pauseOffset = 0;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private scheduledUpTo = 0;
  private eventIndex = 0;
  private callbacks: HapticControllerCallbacks;

  constructor(driver: HapticDriver, callbacks: HapticControllerCallbacks = {}) {
    this.driver = driver;
    this.callbacks = callbacks;
  }

  /** Load a haptic timeline. */
  load(timeline: HapticTimeline): void {
    this.stop();
    this.timeline = timeline;
    this.eventIndex = 0;
    this.scheduledUpTo = 0;
  }

  /** Enable/disable haptic output. */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.driver.cancel();
      this.stopTicking();
    }
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  /** Start playback from current position. */
  play(): void {
    if (!this.enabled || !this.timeline) return;
    if (this.playing) return;

    this.playing = true;
    this.startTime = performance.now() - this.pauseOffset;
    this.scheduledUpTo = this.pauseOffset;
    this.startTicking();
    this.callbacks.onStateChange?.('playing');
  }

  /** Pause playback. */
  pause(): void {
    if (!this.playing) return;

    this.playing = false;
    this.pauseOffset = performance.now() - this.startTime;
    this.stopTicking();
    this.driver.cancel();
    this.callbacks.onStateChange?.('paused');
  }

  /** Stop playback and reset. */
  stop(): void {
    this.playing = false;
    this.pauseOffset = 0;
    this.startTime = 0;
    this.eventIndex = 0;
    this.scheduledUpTo = 0;
    this.stopTicking();
    this.driver.cancel();
    this.callbacks.onStateChange?.('idle');
  }

  /** Seek to a specific time in seconds. */
  seek(timeSeconds: number): void {
    const timeMs = timeSeconds * 1000;

    // Cancel any pending vibrations
    this.driver.cancel();

    // Reset event index to find the first event at or after this time
    this.pauseOffset = timeMs;
    this.scheduledUpTo = timeMs;

    // Binary search for the correct event index
    if (this.timeline) {
      this.eventIndex = this.findEventIndex(timeMs);
    }

    if (this.playing) {
      this.startTime = performance.now() - timeMs;
    }
  }

  /** Get current playback position in seconds. */
  getCurrentTime(): number {
    if (!this.playing) return this.pauseOffset / 1000;
    return (performance.now() - this.startTime) / 1000;
  }

  /** Get timeline duration in seconds. */
  getDuration(): number {
    return this.timeline?.duration_seconds ?? 0;
  }

  /** Get number of events in timeline. */
  getEventCount(): number {
    return this.timeline?.events.length ?? 0;
  }

  /** Check if real haptic hardware is available. */
  isRealHardware(): boolean {
    return this.driver.isReal;
  }

  /** Fire a test haptic pulse (not from timeline). */
  testPulse(intensity: number, duration_ms: number): void {
    if (!this.enabled) return;
    this.driver.vibrate(intensity, duration_ms);
  }

  /** Cleanup. */
  destroy(): void {
    this.stop();
    this.timeline = null;
  }

  // --- Private scheduling ---

  private startTicking(): void {
    this.stopTicking();
    this.tickTimer = setInterval(() => this.tick(), TICK_INTERVAL_MS);
  }

  private stopTicking(): void {
    if (this.tickTimer !== null) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
  }

  private tick(): void {
    if (!this.playing || !this.timeline) return;

    const nowMs = performance.now() - this.startTime;
    const scheduleEnd = nowMs + SCHEDULE_AHEAD_MS;

    const events = this.timeline.events;
    while (this.eventIndex < events.length) {
      const event = events[this.eventIndex];
      const eventTimeMs = event.time * 1000;

      if (eventTimeMs > scheduleEnd) break;

      if (eventTimeMs >= nowMs - 10) {
        // Event is in the near future (within tick resolution)
        const delayMs = Math.max(0, eventTimeMs - nowMs);
        this.scheduleEvent(event, delayMs);
      }

      this.eventIndex++;
    }

    this.scheduledUpTo = scheduleEnd;

    // Check if we've reached the end of the timeline
    if (this.eventIndex >= events.length && nowMs > (this.timeline.duration_seconds * 1000)) {
      this.stop();
    }
  }

  private scheduleEvent(event: HapticEvent, delayMs: number): void {
    if (!this.enabled) return;

    if (delayMs <= 0) {
      this.driver.vibrate(event.intensity, event.duration_ms);
      this.callbacks.onEvent?.(event);
    } else {
      setTimeout(() => {
        if (this.enabled && this.playing) {
          this.driver.vibrate(event.intensity, event.duration_ms);
          this.callbacks.onEvent?.(event);
        }
      }, delayMs);
    }
  }

  private findEventIndex(timeMs: number): number {
    if (!this.timeline) return 0;

    const events = this.timeline.events;
    let lo = 0;
    let hi = events.length;

    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (events[mid].time * 1000 < timeMs) {
        lo = mid + 1;
      } else {
        hi = mid;
      }
    }

    return lo;
  }
}
