/**
 * HapticController — audio-synchronized haptic event scheduler.
 *
 * The HTMLAudioElement is the authoritative clock.
 * This controller reads audio.currentTime and schedules haptic events
 * in a rolling window ahead of the current playback position.
 *
 * Key design:
 * - No independent playback timer (no performance.now() clock)
 * - Session token prevents stale callbacks after pause/seek/stop
 * - Hard-stop on all audio state changes
 * - Rolling 200ms scheduling window
 */

import { HapticEvent, HapticTimeline } from './haptic-types';
import { HapticDriver } from './haptic-driver';

const SCHEDULE_AHEAD_MS = 200;
const TICK_INTERVAL_MS = 50;
const DRIFT_THRESHOLD_MS = 50;
const LARGE_DRIFT_MS = 100;

export type HapticPlaybackState = 'idle' | 'loaded' | 'playing' | 'paused';

export interface HapticControllerCallbacks {
  onEvent?: (event: HapticEvent) => void;
  onStateChange?: (state: HapticPlaybackState) => void;
}

export class HapticController {
  private driver: HapticDriver;
  private timeline: HapticTimeline | null = null;
  private enabled = false;
  private playing = false;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private eventIndex = 0;
  private callbacks: HapticControllerCallbacks;
  private sessionId = 0;
  private lastEventTime = -1;
  private getAudioTime: (() => number) | null = null;

  constructor(driver: HapticDriver, callbacks: HapticControllerCallbacks = {}) {
    this.driver = driver;
    this.callbacks = callbacks;
  }

  /** Load a haptic timeline. Does NOT start playback. */
  load(timeline: HapticTimeline): void {
    this.hardStop();
    this.timeline = timeline;
    this.eventIndex = 0;
    this.callbacks.onStateChange?.('loaded');
  }

  /** Enable/disable haptic output. */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.hardStop();
    }
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Start haptic scheduling. Must only be called after audio is confirmed playing.
   * @param audioCurrentTimeS - The audio element's current time in seconds
   * @param getAudioTime - Callback that returns current audio time (used by tick loop)
   */
  play(audioCurrentTimeS: number, getAudioTime?: () => number): void {
    if (!this.enabled || !this.timeline) return;
    if (this.playing) return;

    this.sessionId++;
    this.playing = true;
    this.getAudioTime = getAudioTime ?? null;
    this.eventIndex = this.findEventIndex(audioCurrentTimeS * 1000);
    this.lastEventTime = audioCurrentTimeS;
    this.startTicking();
    this.callbacks.onStateChange?.('playing');
  }

  /** Hard stop: cancel all pending callbacks, clear vibration, invalidate session. */
  pause(): void {
    if (!this.playing) return;
    this.hardStop();
    this.callbacks.onStateChange?.('paused');
  }

  /** Stop and reset everything. */
  stop(): void {
    this.hardStop();
    this.eventIndex = 0;
    this.lastEventTime = -1;
    this.getAudioTime = null;
    this.callbacks.onStateChange?.('idle');
  }

  /**
   * Seek to a new position. Must be called with the audio element's currentTime.
   * If audio is playing, reschedules from the new position.
   * If audio is paused, just repositions the cursor.
   */
  seek(audioCurrentTimeS: number): void {
    this.driver.cancel();
    this.eventIndex = this.findEventIndex(audioCurrentTimeS * 1000);
    this.lastEventTime = audioCurrentTimeS;
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

  /** Get current session ID (for debugging). */
  getSessionId(): number {
    return this.sessionId;
  }

  /** Get the last scheduled event time (for debugging). */
  getLastEventTime(): number {
    return this.lastEventTime;
  }

  /** Cleanup. */
  destroy(): void {
    this.hardStop();
    this.timeline = null;
  }

  // --- Private ---

  private hardStop(): void {
    this.playing = false;
    this.sessionId++;
    this.stopTicking();
    this.driver.cancel();
  }

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
    if (!this.playing || !this.timeline || !this.getAudioTime) return;

    const currentSession = this.sessionId;
    const audioTimeS = this.getAudioTime();
    const audioTimeMs = audioTimeS * 1000;

    // Drift correction: if audio has jumped (seek, stall recovery), resync
    const expectedTimeMs = this.lastEventTime * 1000;
    const driftMs = Math.abs(audioTimeMs - expectedTimeMs);

    if (driftMs > LARGE_DRIFT_MS) {
      // Large drift: discard stale events, resync cursor
      this.eventIndex = this.findEventIndex(audioTimeMs);
    } else if (driftMs > DRIFT_THRESHOLD_MS) {
      // Moderate drift: resync event index
      this.eventIndex = this.findEventIndex(audioTimeMs);
    }

    this.lastEventTime = audioTimeS;

    // Schedule events in the look-ahead window
    const scheduleEnd = audioTimeMs + SCHEDULE_AHEAD_MS;
    const events = this.timeline.events;

    while (this.eventIndex < events.length) {
      const event = events[this.eventIndex];
      const eventTimeMs = event.time * 1000;

      if (eventTimeMs > scheduleEnd) break;

      // Only fire events that are in the near future or very slightly in the past
      if (eventTimeMs >= audioTimeMs - 10) {
        const delayMs = Math.max(0, eventTimeMs - audioTimeMs);
        this.scheduleEvent(event, delayMs, currentSession);
      }

      this.eventIndex++;
    }

    // Check if we've reached the end of the timeline
    if (this.eventIndex >= events.length && audioTimeMs > (this.timeline.duration_seconds * 1000)) {
      this.stop();
    }
  }

  private scheduleEvent(event: HapticEvent, delayMs: number, session: number): void {
    if (!this.enabled) return;

    const execute = () => {
      // Validate session before executing
      if (session !== this.sessionId) return;
      if (!this.enabled || !this.playing) return;
      this.driver.vibrate(event.intensity, event.duration_ms);
      this.callbacks.onEvent?.(event);
      this.lastEventTime = event.time;
    };

    if (delayMs <= 0) {
      execute();
    } else {
      setTimeout(execute, delayMs);
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
