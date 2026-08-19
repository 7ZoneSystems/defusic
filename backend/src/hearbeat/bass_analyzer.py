"""Bass analysis using Demucs source separation + signal features."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np

from hearbeat.config import (
    BASS_ACTIVITY_ENERGY_THRESHOLD,
    BASS_ACTIVITY_MIN_DURATION,
    BASS_MAX_HZ,
    DEVICE,
    DEMUCS_MODEL,
    MODELS_DIR,
    SUBBASS_MAX_HZ,
)

logger = logging.getLogger(__name__)


class BassAnalysisError(Exception):
    """Raised when bass analysis fails."""


class BassStemExtractor:
    """Extracts bass stem using Demucs source separation.

    Isolated behind this interface so the model can be replaced later.
    """

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or DEMUCS_MODEL
        self.device = device or DEVICE
        self.models_dir = MODELS_DIR
        self._separate_func = None

    def _ensure_loaded(self) -> None:
        if self._separate_func is not None:
            return
        try:
            from demucs.api import Separator
            from demucs.hf import load_safetensors_model, BagOfModels
            import yaml

            local_model_dir = self.models_dir
            yaml_path = local_model_dir / f"{self.model_name}.yaml"

            if yaml_path.is_file():
                logger.info("Loading Demucs model from local: %s", local_model_dir)
                with open(yaml_path) as f:
                    bag = yaml.safe_load(f)
                models = [
                    load_safetensors_model(local_model_dir / f"{sig}.safetensors")
                    for sig in bag["models"]
                ]
                model = BagOfModels(models, bag.get("weights"), bag.get("segment"))

                self._separator = Separator.__new__(Separator)
                self._separator._name = self.model_name
                self._separator._repo = None
                self._separator._device = self.device
                self._separator._shifts = 1
                self._separator._overlap = 0.25
                self._separator._split = True
                self._separator._segment = None
                self._separator._jobs = 0
                self._separator._progress = False
                self._separator._callback = None
                self._separator._callback_arg = None
                self._separator._model = model
                self._separator._stem_sources = None
                self._separator._samplerate = model.samplerate
                self._separator._audio_channels = model.audio_channels
            else:
                logger.info(
                    "Local model not found at %s, loading from cache/hub: %s",
                    yaml_path, self.model_name,
                )
                self._separator = Separator(
                    model=self.model_name,
                    device=self.device,
                )
            logger.info(
                "Loaded Demucs separator: model=%s, device=%s",
                self.model_name, self.device,
            )
        except ImportError as e:
            raise BassAnalysisError(
                "Demucs is required for bass separation. "
                "Install with: pip install demucs"
            ) from e

    def extract_bass(self, wav_path: Path) -> tuple[np.ndarray, int]:
        """Extract bass stem from a WAV file.

        Returns:
            Tuple of (bass_audio_array, sample_rate)
        """
        self._ensure_loaded()

        logger.info("Running Demucs bass separation on: %s", wav_path)
        _, separated = self._separator.separate_audio_file(str(wav_path))

        if "bass" not in separated:
            raise BassAnalysisError(
                f"Demucs did not produce a bass stem. Available: {list(separated.keys())}"
            )

        bass = separated["bass"].cpu().numpy()

        if bass.ndim > 1 and bass.shape[0] > 1:
            bass = bass.mean(axis=0)
        elif bass.ndim > 1:
            bass = bass[0]

        sr = self._separator.samplerate
        logger.info(
            "Extracted bass stem: %.1fs at %d Hz", len(bass) / sr, sr,
        )
        return bass, sr


class BassAnalyzer:
    """Analyzes bass signal for musical events.

    Detects two types of bass events:
    - bass transient: onset/attack in the bass signal
    - bass_activity: sustained low-frequency energy
    """

    def __init__(self) -> None:
        self.separator = BassStemExtractor()

    def analyze(self, wav_path: Path) -> dict:
        """Full bass analysis: separation + feature extraction.

        Returns:
            dict with bass features and detected bass events.
        """
        bass_audio, sr = self.separator.extract_bass(wav_path)

        if len(bass_audio) == 0:
            return {
                "bass_audio": np.array([], dtype=np.float32),
                "sample_rate": sr,
                "events": [],
                "rms_envelope": np.array([]),
                "onset_envelope": np.array([]),
                "warnings": ["Bass stem is empty"],
            }

        features = self._extract_features(bass_audio, sr)
        transient_events = self._detect_bass_transients(bass_audio, sr, features)
        activity_events = self._detect_bass_activity(bass_audio, sr, features)

        # Merge: remove activity events that overlap with transients
        merged = self._merge_events(transient_events, activity_events)

        logger.info(
            "Bass analysis: %d transients + %d activity = %d total",
            len(transient_events), len(activity_events), len(merged),
        )

        return {
            "bass_audio": bass_audio,
            "sample_rate": sr,
            "features": features,
            "events": merged,
            "warnings": [],
        }

    def _extract_features(self, bass: np.ndarray, sr: int) -> dict:
        """Extract signal-level features from the bass stem."""
        hop_length = 512
        frame_length = 2048

        # RMS energy in frames
        rms = self._frame_rms(bass, frame_length, hop_length)

        # Onset strength (spectral flux-based)
        onset_env = self._onset_strength(bass, sr, hop_length)

        # Low-frequency energy envelope
        low_freq_energy = self._low_frequency_energy(bass, sr, hop_length)

        # Sub-bass energy (below subbass_max_hz)
        subbass_energy = self._band_energy(
            bass, sr, hop_length,
            low_hz=20, high_hz=SUBBASS_MAX_HZ,
        )

        # Bass energy (below bass_max_hz)
        bass_band_energy = self._band_energy(
            bass, sr, hop_length,
            low_hz=20, high_hz=BASS_MAX_HZ,
        )

        # Track-level normalization: get the peak energy for relative scaling
        peak_rms = float(rms.max()) if len(rms) > 0 else 1.0
        if peak_rms < 1e-10:
            peak_rms = 1.0

        return {
            "rms": rms,
            "onset_strength": onset_env,
            "low_freq_energy": low_freq_energy,
            "subbass_energy": subbass_energy,
            "bass_band_energy": bass_band_energy,
            "hop_length": hop_length,
            "frame_length": frame_length,
            "duration": len(bass) / sr,
            "peak_rms": peak_rms,
        }

    def _frame_rms(
        self, signal: np.ndarray, frame_length: int, hop_length: int
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
        self, signal: np.ndarray, sr: int, hop_length: int
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
            return self._spectral_flux_fallback(signal, sr, hop_length)

    def _spectral_flux_fallback(
        self, signal: np.ndarray, sr: int, hop_length: int
    ) -> np.ndarray:
        """Fallback onset detection using scipy FFT."""
        from scipy.signal import stft

        _, _, Zxx = stft(signal, fs=sr, nperseg=2048, noverlap=2048 - hop_length)
        magnitude = np.abs(Zxx)

        diff = np.diff(magnitude, axis=1)
        flux = np.maximum(0, diff).sum(axis=0)
        return flux.astype(np.float64)

    def _low_frequency_energy(
        self, signal: np.ndarray, sr: int, hop_length: int
    ) -> np.ndarray:
        """Compute low-frequency energy envelope via bandpass filtering.

        Uses a bandpass filter targeting the bass/sub-bass range (20-250 Hz),
        then computes RMS of the filtered signal per frame.
        """
        from scipy.signal import butter, filtfilt

        nyq = sr / 2.0
        low = 20.0 / nyq
        high = min(BASS_MAX_HZ / nyq, 0.99)

        if low >= high:
            # Fallback: just use RMS
            return self._frame_rms(signal, 2048, hop_length)

        b, a = butter(2, [low, high], btype="band")
        filtered = filtfilt(b, a, signal)

        return self._frame_rms(filtered, 2048, hop_length)

    def _band_energy(
        self,
        signal: np.ndarray,
        sr: int,
        hop_length: int,
        low_hz: float = 20.0,
        high_hz: float = 250.0,
    ) -> np.ndarray:
        """Compute energy in a specific frequency band per frame."""
        from scipy.signal import butter, filtfilt

        nyq = sr / 2.0
        low = low_hz / nyq
        high = min(high_hz / nyq, 0.99)

        if low >= high:
            return np.zeros(1 + (len(signal) - 2048) // hop_length, dtype=np.float64)

        b, a = butter(2, [low, high], btype="band")
        filtered = filtfilt(b, a, signal)

        return self._frame_rms(filtered, 2048, hop_length)

    def _detect_bass_transients(
        self, bass: np.ndarray, sr: int, features: dict
    ) -> list[dict]:
        """Detect bass transients (onset/attack events).

        Uses onset strength + RMS for transient detection.
        """
        rms = features["rms"]
        onset_env = features["onset_strength"]
        hop_length = features["hop_length"]

        if len(rms) == 0 or len(onset_env) == 0:
            return []

        rms_norm = self._normalize(rms)
        onset_norm = self._normalize(onset_env)

        min_len = min(len(rms_norm), len(onset_norm))
        rms_norm = rms_norm[:min_len]
        onset_norm = onset_norm[:min_len]

        combined = 0.5 * rms_norm + 0.5 * onset_norm

        mean_val = np.mean(combined)
        std_val = np.std(combined)
        threshold = mean_val + 1.5 * std_val

        events = []
        frame_times = np.arange(min_len) * hop_length / sr

        in_event = False
        event_start_idx = 0

        for i in range(min_len):
            if combined[i] >= threshold and not in_event:
                in_event = True
                event_start_idx = i
            elif (combined[i] < threshold or i == min_len - 1) and in_event:
                in_event = False
                event_end_idx = i if combined[i] < threshold else i + 1

                region = combined[event_start_idx:event_end_idx]
                peak_local_idx = np.argmax(region)
                peak_idx = event_start_idx + peak_local_idx

                peak_time = float(frame_times[peak_idx])
                peak_strength = float(rms_norm[peak_idx])
                peak_onset = float(onset_norm[peak_idx])
                event_duration = float(
                    (event_end_idx - event_start_idx) * hop_length / sr
                )

                if event_duration < 0.02:
                    continue

                # Normalized energy relative to track peak
                normalized_energy = float(rms[peak_idx] / features["peak_rms"])

                events.append({
                    "time": peak_time,
                    "strength": float(np.clip(peak_strength, 0.0, 1.0)),
                    "raw_rms": float(rms[peak_idx]),
                    "normalized_energy": normalized_energy,
                    "duration": event_duration,
                    "onset_strength": peak_onset,
                    "frame_index": int(peak_idx),
                    "event_kind": "transient",
                })

        logger.info("Detected %d bass transients", len(events))
        return events

    def _detect_bass_activity(
        self, bass: np.ndarray, sr: int, features: dict
    ) -> list[dict]:
        """Detect sustained bass activity from low-frequency energy.

        This captures sustained sub-bass/bass that may not have repeated onsets.
        Uses the low-frequency energy envelope with a combination of:
        1. Absolute energy threshold (relative to track peak)
        2. Adaptive threshold for regions with energy variation
        """
        low_freq = features["low_freq_energy"]
        subbass = features["subbass_energy"]
        hop_length = features["hop_length"]
        peak_rms = features["peak_rms"]

        if len(low_freq) == 0:
            return []

        # Use the maximum of low-freq and subbass energy
        min_len = min(len(low_freq), len(subbass))
        energy = np.maximum(low_freq[:min_len], subbass[:min_len])

        # Normalize relative to track peak
        if peak_rms > 1e-10:
            energy_relative = energy / peak_rms
        else:
            energy_relative = self._normalize(energy)

        # Use a lower threshold based on absolute energy level
        # A bass event should have at least 30% of the track's peak energy
        threshold = max(BASS_ACTIVITY_ENERGY_THRESHOLD, 0.3)

        frame_times = np.arange(min_len) * hop_length / sr
        events = []

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
                event_duration = float(event_duration_frames * hop_length / sr)

                # Skip events shorter than minimum duration
                if event_duration < BASS_ACTIVITY_MIN_DURATION:
                    continue

                # Representative timestamp: middle of the activity region
                mid_idx = (event_start_idx + event_end_idx) // 2
                mid_time = float(frame_times[mid_idx])

                # Strength: average energy in the region, normalized
                region_energy = energy[event_start_idx:event_end_idx]
                avg_energy = float(np.mean(region_energy))
                normalized_energy = avg_energy / peak_rms if peak_rms > 0 else 0.0

                # Peak within region
                peak_local = np.argmax(energy_relative[event_start_idx:event_end_idx])
                peak_idx = event_start_idx + peak_local

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
                })

        logger.info("Detected %d bass activity regions", len(events))
        return events

    def _merge_events(
        self, transients: list[dict], activity: list[dict]
    ) -> list[dict]:
        """Merge transient and activity events.

        Activity events that overlap with transients are removed.
        Activity events get a 'time_start' and 'time_end' for interval display.
        """
        if not activity:
            return transients
        if not transients:
            return activity

        # Build a set of times covered by transients (with tolerance)
        transient_times = set()
        for t in transients:
            # Mark frames near this transient
            frame = t.get("frame_index", 0)
            for offset in range(-3, 4):
                transient_times.add(frame + offset)

        merged = list(transients)

        for act in activity:
            peak_frame = act.get("frame_index", 0)
            # Check if this activity's peak overlaps with any transient
            if peak_frame in transient_times:
                continue

            # Convert to AnalysisEvent-compatible format
            # Activity events use 'bass_activity' type
            merged.append({
                "time": act["time"],
                "strength": act["strength"],
                "raw_rms": act["raw_rms"],
                "normalized_energy": act["normalized_energy"],
                "duration": act["duration"],
                "onset_strength": 0.0,
                "frame_index": act["frame_index"],
                "event_kind": "activity",
                "start_time": act.get("start_time", act["time"]),
                "end_time": act.get("end_time", act["time"] + act["duration"]),
            })

        # Sort by time
        merged.sort(key=lambda e: e["time"])

        return merged

    @staticmethod
    def _normalize(arr: np.ndarray) -> np.ndarray:
        """Min-max normalize to 0-1."""
        if len(arr) == 0:
            return arr
        min_val = arr.min()
        max_val = arr.max()
        if max_val - min_val < 1e-10:
            return np.zeros_like(arr)
        return (arr - min_val) / (max_val - min_val)
