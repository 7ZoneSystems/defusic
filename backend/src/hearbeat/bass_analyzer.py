"""Bass analysis using filter-bank energy and onset detection.

Replaces the previous Demucs-based bass stem approach with a direct
filter-bank pipeline operating on the original audio. Detects:

- bass transients: onset/attack events in the bass signal
- bass_activity: sustained low-frequency energy regions
- subbass events: separate analysis for 20-60 Hz
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from hearbeat.config import (
    BASS_ACTIVITY_MIN_DURATION,
    BASS_ACTIVITY_THRESHOLD,
    BASS_LOW_HZ,
    BASS_HIGH_HZ,
    BASS_MIN_EVENT_GAP,
    BASS_ONSET_DELTA,
    FILTER_ORDER,
    HOP_LENGTH,
    LOWMID_HIGH_HZ,
    LOWMID_LOW_HZ,
    SUBBASS_HIGH_HZ,
    SUBBASS_LOW_HZ,
)
from hearbeat.filter_bank import FilterBank

logger = logging.getLogger(__name__)


class BassAnalysisError(Exception):
    """Raised when bass analysis fails."""


class BassAnalyzer:
    """Filter-bank based bass analyzer.

    Operates directly on the original audio (no Demucs required).
    Detects bass transients via onset strength and bass activity
    via energy envelope thresholding.
    """

    def __init__(self, sr: int = 44100) -> None:
        self.sr = sr
        self._filter_bank: FilterBank | None = None

    def _get_filter_bank(self) -> FilterBank:
        if self._filter_bank is None:
            self._filter_bank = FilterBank(
                sr=self.sr,
                bands={
                    "subbass": (SUBBASS_LOW_HZ, SUBBASS_HIGH_HZ),
                    "bass": (BASS_LOW_HZ, BASS_HIGH_HZ),
                    "lowmid": (LOWMID_LOW_HZ, LOWMID_HIGH_HZ),
                },
                order=FILTER_ORDER,
            )
        return self._filter_bank

    def analyze(self, wav_path: Path) -> dict:
        """Full bass analysis from a WAV file.

        Loads audio, applies filter bank, detects events.

        Returns:
            dict with bass features, events, and filtered signals.
        """
        import soundfile as sf

        audio, file_sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample if needed (the pipeline normalizes to 44100)
        if file_sr != self.sr:
            try:
                import librosa
                audio = librosa.resample(
                    audio, orig_sr=file_sr, target_sr=self.sr
                ).astype(np.float32)
            except ImportError:
                logger.warning(
                    "Cannot resample from %d to %d — using raw audio", file_sr, self.sr
                )

        return self.analyze_audio(audio)

    def analyze_audio(self, audio: np.ndarray) -> dict:
        """Analyze a raw audio array for bass events.

        Args:
            audio: Mono float32 audio at self.sr sample rate.

        Returns:
            dict with features, events, filtered signals, warnings.
        """
        if len(audio) == 0:
            return self._empty_result("Audio is empty")

        fb = self._get_filter_bank()
        hop = HOP_LENGTH

        # Filter into bands
        subbass_filtered = fb.filter_band(audio, "subbass", causal=False)
        bass_filtered = fb.filter_band(audio, "bass", causal=False)
        lowmid_filtered = fb.filter_band(audio, "lowmid", causal=False)

        # Combined bass signal (subbass + bass + lowmid)
        bass_combined = subbass_filtered + bass_filtered + lowmid_filtered

        # Energy envelopes
        subbass_energy = fb.band_energy_envelope(audio, "subbass", hop_length=hop)
        bass_energy = fb.band_energy_envelope(audio, "bass", hop_length=hop)
        lowmid_energy = fb.band_energy_envelope(audio, "lowmid", hop_length=hop)

        # RMS of combined bass
        bass_rms = _frame_rms(bass_combined, 2048, hop)

        # Onset strength on the bass-filtered signal
        onset_env = _onset_strength(bass_combined, self.sr, hop)

        # Track-level normalization
        peak_rms = float(bass_rms.max()) if len(bass_rms) > 0 else 1.0
        if peak_rms < 1e-10:
            peak_rms = 1.0

        features = {
            "subbass_energy": subbass_energy,
            "bass_energy": bass_energy,
            "lowmid_energy": lowmid_energy,
            "bass_rms": bass_rms,
            "onset_strength": onset_env,
            "hop_length": hop,
            "duration": len(audio) / self.sr,
            "peak_rms": peak_rms,
        }

        # Detect events
        transient_events = self._detect_bass_transients(
            bass_combined, bass_rms, onset_env, hop, peak_rms
        )
        activity_events = self._detect_bass_activity(
            subbass_energy, bass_energy, lowmid_energy, hop, peak_rms
        )

        # Merge: remove activity events that overlap with transients
        merged = self._merge_events(transient_events, activity_events)

        logger.info(
            "Bass analysis: %d transients + %d activity = %d total",
            len(transient_events), len(activity_events), len(merged),
        )

        return {
            "features": features,
            "events": merged,
            "filtered": {
                "subbass": subbass_filtered,
                "bass": bass_filtered,
                "lowmid": lowmid_filtered,
                "combined": bass_combined,
            },
            "warnings": [],
        }

    def _detect_bass_transients(
        self,
        bass_combined: np.ndarray,
        bass_rms: np.ndarray,
        onset_env: np.ndarray,
        hop_length: int,
        peak_rms: float,
    ) -> list[dict]:
        """Detect bass transients using onset strength + RMS."""
        if len(bass_rms) == 0 or len(onset_env) == 0:
            return []

        min_len = min(len(bass_rms), len(onset_env))
        rms_norm = _normalize(bass_rms[:min_len])
        onset_norm = _normalize(onset_env[:min_len])

        combined = 0.5 * rms_norm + 0.5 * onset_norm

        # Adaptive threshold: mean + 1.5 * std
        mean_val = np.mean(combined)
        std_val = np.std(combined)
        threshold = mean_val + 1.5 * std_val

        events: list[dict] = []
        frame_times = np.arange(min_len) * hop_length / self.sr
        min_gap_frames = int(BASS_MIN_EVENT_GAP * self.sr / hop_length)

        in_event = False
        event_start_idx = 0
        last_event_frame = -min_gap_frames

        for i in range(min_len):
            if combined[i] >= threshold and not in_event:
                in_event = True
                event_start_idx = i
            elif (combined[i] < threshold or i == min_len - 1) and in_event:
                in_event = False
                event_end_idx = i if combined[i] < threshold else i + 1

                region = combined[event_start_idx:event_end_idx]
                peak_local_idx = int(np.argmax(region))
                peak_idx = event_start_idx + peak_local_idx

                # Enforce minimum gap
                if peak_idx - last_event_frame < min_gap_frames:
                    continue

                event_duration = float(
                    (event_end_idx - event_start_idx) * hop_length / self.sr
                )
                if event_duration < 0.02:
                    continue

                # Gate: skip events with negligible energy
                raw_rms_val = float(bass_rms[peak_idx])
                if raw_rms_val < 1e-6:
                    continue

                normalized_energy = raw_rms_val / peak_rms if peak_rms > 0 else 0.0

                events.append({
                    "time": float(frame_times[peak_idx]),
                    "strength": float(np.clip(rms_norm[peak_idx], 0.0, 1.0)),
                    "raw_rms": float(bass_rms[peak_idx]),
                    "normalized_energy": normalized_energy,
                    "duration": event_duration,
                    "onset_strength": float(onset_norm[peak_idx]),
                    "frame_index": int(peak_idx),
                    "event_kind": "transient",
                })
                last_event_frame = peak_idx

        return events

    def _detect_bass_activity(
        self,
        subbass_energy: np.ndarray,
        bass_energy: np.ndarray,
        lowmid_energy: np.ndarray,
        hop_length: int,
        peak_rms: float,
    ) -> list[dict]:
        """Detect sustained bass activity from energy envelopes.

        Merges adjacent active frames into coherent activity intervals.
        """
        min_len = min(len(subbass_energy), len(bass_energy), len(lowmid_energy))
        if min_len == 0:
            return []

        # Use the maximum energy across the three bands
        energy = np.maximum(
            np.maximum(subbass_energy[:min_len], bass_energy[:min_len]),
            lowmid_energy[:min_len],
        )

        # Normalize relative to track peak
        if peak_rms > 1e-10:
            energy_relative = energy / peak_rms
        else:
            energy_relative = _normalize(energy)

        threshold = BASS_ACTIVITY_THRESHOLD
        min_duration_frames = int(BASS_ACTIVITY_MIN_DURATION * self.sr / hop_length)

        frame_times = np.arange(min_len) * hop_length / self.sr
        events: list[dict] = []

        in_event = False
        event_start_idx = 0

        for i in range(min_len):
            if energy_relative[i] >= threshold and not in_event:
                in_event = True
                event_start_idx = i
            elif (energy_relative[i] < threshold or i == min_len - 1) and in_event:
                in_event = False
                event_end_idx = i if energy_relative[i] < threshold else i + 1

                event_duration_frames = event_end_idx - event_start_idx
                if event_duration_frames < min_duration_frames:
                    continue

                event_duration = float(event_duration_frames * hop_length / self.sr)
                mid_idx = (event_start_idx + event_end_idx) // 2
                mid_time = float(frame_times[mid_idx])

                region_energy = energy[event_start_idx:event_end_idx]
                avg_energy = float(np.mean(region_energy))
                normalized_energy = avg_energy / peak_rms if peak_rms > 0 else 0.0

                peak_local = int(np.argmax(energy_relative[event_start_idx:event_end_idx]))
                peak_idx = event_start_idx + peak_local

                # Compute per-band energy for diagnostics
                sub_avg = float(np.mean(subbass_energy[event_start_idx:event_end_idx]))
                bass_avg = float(np.mean(bass_energy[event_start_idx:event_end_idx]))
                lowmid_avg = float(np.mean(lowmid_energy[event_start_idx:event_end_idx]))

                events.append({
                    "time": mid_time,
                    "strength": float(np.clip(float(energy_relative[peak_idx]), 0.0, 1.0)),
                    "raw_rms": float(region_energy.mean()),
                    "normalized_energy": float(np.clip(normalized_energy, 0.0, 1.0)),
                    "duration": event_duration,
                    "onset_strength": 0.0,
                    "frame_index": int(peak_idx),
                    "event_kind": "activity",
                    "start_time": float(frame_times[event_start_idx]),
                    "end_time": float(frame_times[min(event_end_idx, min_len - 1)]),
                    "subbass_energy": sub_avg,
                    "bass_energy": bass_avg,
                    "lowmid_energy": lowmid_avg,
                })

        return events

    def _merge_events(
        self, transients: list[dict], activity: list[dict]
    ) -> list[dict]:
        """Merge transient and activity events.

        Activity events that overlap with transients are removed.
        """
        if not activity:
            return transients
        if not transients:
            return activity

        transient_times: set[int] = set()
        for t in transients:
            frame = t.get("frame_index", 0)
            for offset in range(-3, 4):
                transient_times.add(frame + offset)

        merged = list(transients)
        for act in activity:
            peak_frame = act.get("frame_index", 0)
            if peak_frame in transient_times:
                continue
            merged.append(act)

        merged.sort(key=lambda e: e["time"])
        return merged

    def _empty_result(self, warning: str) -> dict:
        return {
            "features": {},
            "events": [],
            "filtered": {},
            "warnings": [warning],
        }


def _frame_rms(
    signal: np.ndarray, frame_length: int, hop_length: int
) -> np.ndarray:
    """Compute RMS energy per frame."""
    n_frames = 1 + (len(signal) - frame_length) // hop_length
    if n_frames <= 0:
        return np.array([np.sqrt(np.mean(signal**2))], dtype=np.float64)

    frames = np.lib.stride_tricks.as_strided(
        signal,
        shape=(n_frames, frame_length),
        strides=(signal.strides[0] * hop_length, signal.strides[0]),
    )
    rms = np.sqrt(np.mean(frames**2, axis=1))
    return rms.astype(np.float64)


def _onset_strength(
    signal: np.ndarray, sr: int, hop_length: int
) -> np.ndarray:
    """Compute onset strength envelope using spectral flux."""
    try:
        import librosa

        onset_env = librosa.onset.onset_strength(
            y=signal.astype(np.float32),
            sr=sr,
            hop_length=hop_length,
        )
        return onset_env.astype(np.float64)
    except ImportError:
        return _spectral_flux_fallback(signal, sr, hop_length)


def _spectral_flux_fallback(
    signal: np.ndarray, sr: int, hop_length: int
) -> np.ndarray:
    """Fallback onset detection using scipy FFT."""
    from scipy.signal import stft

    _, _, Zxx = stft(signal, fs=sr, nperseg=2048, noverlap=2048 - hop_length)
    magnitude = np.abs(Zxx)
    diff = np.diff(magnitude, axis=1)
    flux = np.maximum(0, diff).sum(axis=0)
    return flux.astype(np.float64)


def _normalize(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to 0-1."""
    if len(arr) == 0:
        return arr
    min_val = float(arr.min())
    max_val = float(arr.max())
    if max_val - min_val < 1e-10:
        return np.zeros_like(arr)
    return ((arr - min_val) / (max_val - min_val)).astype(np.float64)
