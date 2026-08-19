"""Bass analysis using Demucs source separation + signal features."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np

from hearbeat.config import DEVICE, DEMUCS_MODEL, MODELS_DIR

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
            from demucs.hf import get_hf_model, load_safetensors_model, BagOfModels
            import yaml

            # Try local model directory first
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
                self._separator = Separator(
                    model=self.model_name,
                    device=self.device,
                )
                # Override the loaded model with our local one
                self._separator._model = model
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

        # Demucs returns a dict: {"bass": tensor, "drums": tensor, ...}
        if "bass" not in separated:
            raise BassAnalysisError(
                f"Demucs did not produce a bass stem. Available: {list(separated.keys())}"
            )

        bass = separated["bass"].cpu().numpy()

        # Mix down to mono if stereo
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
    """Analyzes bass signal for musical events."""

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
        events = self._detect_bass_events(bass_audio, sr, features)

        return {
            "bass_audio": bass_audio,
            "sample_rate": sr,
            "features": features,
            "events": events,
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

        return {
            "rms": rms,
            "onset_strength": onset_env,
            "hop_length": hop_length,
            "frame_length": frame_length,
            "duration": len(bass) / sr,
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
            # Fallback: simple spectral flux via scipy
            return self._spectral_flux_fallback(signal, sr, hop_length)

    def _spectral_flux_fallback(
        self, signal: np.ndarray, sr: int, hop_length: int
    ) -> np.ndarray:
        """Fallback onset detection using scipy FFT."""
        from scipy.signal import stft

        _, _, Zxx = stft(signal, fs=sr, nperseg=2048, noverlap=2048 - hop_length)
        magnitude = np.abs(Zxx)

        # Spectral flux (half-wave rectified difference)
        diff = np.diff(magnitude, axis=1)
        flux = np.maximum(0, diff).sum(axis=0)
        return flux.astype(np.float64)

    def _detect_bass_events(
        self, bass: np.ndarray, sr: int, features: dict
    ) -> list[dict]:
        """Detect meaningful bass events from features.

        Conservative approach: find peaks in onset strength that represent
        genuine bass transients, not every nonzero sample.
        """
        rms = features["rms"]
        onset_env = features["onset_strength"]
        hop_length = features["hop_length"]

        if len(rms) == 0 or len(onset_env) == 0:
            return []

        # Normalize features to 0-1
        rms_norm = self._normalize(rms)
        onset_norm = self._normalize(onset_env)

        # Ensure same length
        min_len = min(len(rms_norm), len(onset_norm))
        rms_norm = rms_norm[:min_len]
        onset_norm = onset_norm[:min_len]

        # Combine RMS and onset strength for event detection
        combined = 0.5 * rms_norm + 0.5 * onset_norm

        # Adaptive threshold: mean + 1.5 * std
        mean_val = np.mean(combined)
        std_val = np.std(combined)
        threshold = mean_val + 1.5 * std_val

        # Find peaks above threshold
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

                # Find peak within the event region
                region = combined[event_start_idx:event_end_idx]
                peak_local_idx = np.argmax(region)
                peak_idx = event_start_idx + peak_local_idx

                peak_time = float(frame_times[peak_idx])
                peak_strength = float(rms_norm[peak_idx])
                peak_onset = float(onset_norm[peak_idx])
                event_duration = float(
                    (event_end_idx - event_start_idx) * hop_length / sr
                )

                # Skip extremely short events (< 20ms)
                if event_duration < 0.02:
                    continue

                events.append({
                    "time": peak_time,
                    "strength": float(np.clip(peak_strength, 0.0, 1.0)),
                    "raw_rms": float(rms[peak_idx]),
                    "duration": event_duration,
                    "onset_strength": peak_onset,
                    "frame_index": int(peak_idx),
                })

        logger.info("Detected %d bass events", len(events))
        return events

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
