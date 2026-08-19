"""Bass analysis using multi-expert onset fusion and hysteresis energy detection.

Architecture:
    original audio
        -> filter bank (subbass, bass, lowmid)
        -> combined bass signal
        -> multi-expert onset fusion (bass transients)
        -> hysteresis energy envelope (bass activity)
        -> sub-bass monitoring
        -> event merge + deduplication

No Demucs required. Designed for future Android real-time streaming.

References:
- Essentia onset detection: https://essentia.upf.edu/tutorial_rhythm_onsetdetection.html
- Score-level fusion: https://www.researchgate.net/publication/220722982
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from hearbeat.config import (
    BASS_ACTIVITY_MIN_DURATION,
    BASS_ACTIVITY_THRESHOLD,
    BASS_HIGH_HZ,
    BASS_LOW_HZ,
    BASS_MIN_EVENT_GAP,
    FILTER_ORDER,
    HOP_LENGTH,
    LOWMID_HIGH_HZ,
    LOWMID_LOW_HZ,
    STFT_N_FFT,
    SUBBASS_HIGH_HZ,
    SUBBASS_LOW_HZ,
)
from hearbeat.experts import compute_all_experts
from hearbeat.filter_bank import FilterBank
from hearbeat.onset_fusion import (
    FusionConfig,
    OnsetCandidate,
    multi_expert_fusion,
)

logger = logging.getLogger(__name__)


class BassAnalysisError(Exception):
    """Raised when bass analysis fails."""


class BassAnalyzer:
    """Multi-expert bass analyzer.

    Operates directly on the original audio (no Demucs required).
    Uses multi-expert onset fusion for transients and hysteresis
    energy envelope for sustained activity.
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
        """Full bass analysis from a WAV file."""
        import soundfile as sf

        audio, file_sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

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
        """Analyze raw audio for bass events.

        Args:
            audio: Mono float32 audio at self.sr.

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

        # Combined bass signal
        bass_combined = subbass_filtered + bass_filtered + lowmid_filtered

        # Energy envelopes
        subbass_energy = fb.band_energy_envelope(audio, "subbass", hop_length=hop)
        bass_energy = fb.band_energy_envelope(audio, "bass", hop_length=hop)
        lowmid_energy = fb.band_energy_envelope(audio, "lowmid", hop_length=hop)

        # RMS of combined bass
        bass_rms = _frame_rms(bass_combined, STFT_N_FFT, hop)

        # Track-level normalization
        peak_rms = float(bass_rms.max()) if len(bass_rms) > 0 else 1.0
        if peak_rms < 1e-10:
            peak_rms = 1.0

        features = {
            "subbass_energy": subbass_energy,
            "bass_energy": bass_energy,
            "lowmid_energy": lowmid_energy,
            "bass_rms": bass_rms,
            "hop_length": hop,
            "duration": len(audio) / self.sr,
            "peak_rms": peak_rms,
        }

        # === Multi-expert transient detection ===
        transient_events = self._detect_bass_transients(
            bass_combined, bass_rms, hop, peak_rms
        )

        # === Hysteresis activity detection ===
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
        hop_length: int,
        peak_rms: float,
    ) -> list[dict]:
        """Detect bass transients using multi-expert onset fusion.

        Runs HFC, complex, flux, and RMS-difference experts on the
        bass-filtered signal, then fuses their peaks.
        """
        if len(bass_combined) == 0:
            return []

        # Compute onset experts on the bass signal
        experts = compute_all_experts(
            bass_combined, sr=self.sr, n_fft=STFT_N_FFT,
            hop_length=hop_length,
            experts=["hfc", "complex", "flux", "rms_diff"],
        )

        # Fusion config tuned for bass: raise min_fused_score to filter
        # small fluctuations in continuous signals
        config = FusionConfig(
            cluster_tolerance_ms=25.0,
            minimum_event_gap_ms=BASS_MIN_EVENT_GAP * 1000,
            expert_weights={
                "hfc": 0.15,
                "complex": 0.35,
                "flux": 0.30,
                "rms_diff": 0.20,
            },
            min_fused_score=0.12,
        )

        candidates = multi_expert_fusion(experts, config=config, delta=0.15)

        # Convert candidates to event dicts
        events: list[dict] = []
        n_rms = len(bass_rms)

        for cand in candidates:
            # Map time to frame index
            frame_idx = int(cand.time * self.sr / hop_length)
            if frame_idx >= n_rms:
                continue

            raw_rms_val = float(bass_rms[frame_idx])
            if raw_rms_val < 1e-6:
                continue

            normalized_energy = raw_rms_val / peak_rms if peak_rms > 0 else 0.0

            events.append({
                "time": cand.time,
                "strength": float(np.clip(cand.fused_score, 0.0, 1.0)),
                "raw_rms": raw_rms_val,
                "normalized_energy": normalized_energy,
                "duration": 0.05,
                "onset_strength": cand.fused_score,
                "frame_index": frame_idx,
                "event_kind": "transient",
                "expert_scores": cand.expert_scores,
                "fused_score": cand.fused_score,
                "n_experts_agreeing": cand.n_experts_agreeing,
            })

        return events

    def _detect_bass_activity(
        self,
        subbass_energy: np.ndarray,
        bass_energy: np.ndarray,
        lowmid_energy: np.ndarray,
        hop_length: int,
        peak_rms: float,
    ) -> list[dict]:
        """Detect sustained bass activity using hysteresis energy envelope.

        Uses separate activation and deactivation thresholds to prevent
        ON/OFF/OFF flapping around a single threshold during sustained notes.
        """
        min_len = min(len(subbass_energy), len(bass_energy), len(lowmid_energy))
        if min_len == 0:
            return []

        # Combined energy: max across bands
        energy = np.maximum(
            np.maximum(subbass_energy[:min_len], bass_energy[:min_len]),
            lowmid_energy[:min_len],
        )

        # Normalize relative to track peak
        if peak_rms > 1e-10:
            energy_relative = energy / peak_rms
        else:
            energy_relative = _normalize(energy)

        # Hysteresis thresholds
        activation_threshold = BASS_ACTIVITY_THRESHOLD
        deactivation_threshold = activation_threshold * 0.6  # 60% of activation

        min_duration_frames = int(BASS_ACTIVITY_MIN_DURATION * self.sr / hop_length)
        frame_times = np.arange(min_len) * hop_length / self.sr

        events: list[dict] = []
        in_event = False
        event_start_idx = 0

        for i in range(min_len):
            if not in_event and energy_relative[i] >= activation_threshold:
                in_event = True
                event_start_idx = i
            elif in_event and energy_relative[i] < deactivation_threshold:
                in_event = False
                event_end_idx = i

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

                # Per-band diagnostics
                sub_avg = float(np.mean(subbass_energy[event_start_idx:event_end_idx]))
                bass_avg = float(np.mean(bass_energy[event_start_idx:event_end_idx]))
                lowmid_avg = float(np.mean(lowmid_energy[event_start_idx:event_end_idx]))

                # Classify: subbass_activity if sub-band dominates, else bass_activity
                is_subbass_dominant = sub_avg > bass_avg and sub_avg > lowmid_avg
                event_type = "subbass_activity" if is_subbass_dominant else "bass_activity"

                events.append({
                    "time": mid_time,
                    "strength": float(np.clip(float(energy_relative[peak_idx]), 0.0, 1.0)),
                    "raw_rms": float(region_energy.mean()),
                    "normalized_energy": float(np.clip(normalized_energy, 0.0, 1.0)),
                    "duration": event_duration,
                    "onset_strength": 0.0,
                    "frame_index": int(peak_idx),
                    "event_kind": "activity",
                    "event_type": event_type,
                    "start_time": float(frame_times[event_start_idx]),
                    "end_time": float(frame_times[min(event_end_idx, min_len - 1)]),
                    "subbass_energy": sub_avg,
                    "bass_energy": bass_avg,
                    "lowmid_energy": lowmid_avg,
                })

        # Handle event still active at end of audio
        if in_event:
            event_end_idx = min_len
            event_duration_frames = event_end_idx - event_start_idx
            if event_duration_frames >= min_duration_frames:
                event_duration = float(event_duration_frames * hop_length / self.sr)
                mid_idx = (event_start_idx + event_end_idx) // 2
                mid_time = float(frame_times[mid_idx])

                region_energy = energy[event_start_idx:event_end_idx]
                avg_energy = float(np.mean(region_energy))
                normalized_energy = avg_energy / peak_rms if peak_rms > 0 else 0.0

                peak_local = int(np.argmax(energy_relative[event_start_idx:event_end_idx]))
                peak_idx = event_start_idx + peak_local

                sub_avg = float(np.mean(subbass_energy[event_start_idx:event_end_idx]))
                bass_avg = float(np.mean(bass_energy[event_start_idx:event_end_idx]))
                lowmid_avg = float(np.mean(lowmid_energy[event_start_idx:event_end_idx]))

                is_subbass_dominant = sub_avg > bass_avg and sub_avg > lowmid_avg
                event_type = "subbass_activity" if is_subbass_dominant else "bass_activity"

                events.append({
                    "time": mid_time,
                    "strength": float(np.clip(float(energy_relative[peak_idx]), 0.0, 1.0)),
                    "raw_rms": float(region_energy.mean()),
                    "normalized_energy": float(np.clip(normalized_energy, 0.0, 1.0)),
                    "duration": event_duration,
                    "onset_strength": 0.0,
                    "frame_index": int(peak_idx),
                    "event_kind": "activity",
                    "event_type": event_type,
                    "start_time": float(frame_times[event_start_idx]),
                    "end_time": float(frame_times[min(event_end_idx - 1, min_len - 1)]),
                    "subbass_energy": sub_avg,
                    "bass_energy": bass_avg,
                    "lowmid_energy": lowmid_avg,
                })

        return events

    def _merge_events(
        self, transients: list[dict], activity: list[dict]
    ) -> list[dict]:
        """Merge transient and activity events.

        Long activity events (>0.5s) always survive — they represent sustained
        notes even if transients occur within them. Short activity events whose
        peak_frame is within 3 frames of a transient are dropped.
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
            duration = act.get("duration", 0.0)
            if duration > 0.5:
                merged.append(act)
            elif peak_frame in transient_times:
                continue
            else:
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


def _normalize(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to 0-1."""
    if len(arr) == 0:
        return arr
    min_val = float(arr.min())
    max_val = float(arr.max())
    if max_val - min_val < 1e-10:
        return np.zeros_like(arr)
    return ((arr - min_val) / (max_val - min_val)).astype(np.float64)
