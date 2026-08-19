"""Drum analysis: onset detection, kick/snare/hat classification, beat alignment.

Enhanced with dedicated kick detection path alongside the existing
general onset detector. The general onset path handles hi-hat and
generic drum events. The kick path uses low-frequency filtering and
spectral features for kick-specific classification.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class DrumAnalysisError(Exception):
    """Raised when drum analysis fails."""


class DrumAnalyzer:
    """Analyzes a drum stem for percussion events.

    Uses librosa for onset detection (spectral flux / HFC),
    then applies spectral features for classification.

    Enhanced with a dedicated kick detection path that operates
    on the low-frequency content of the drum signal.
    """

    def __init__(self, sr: int = 44100) -> None:
        self.sr = sr
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            import librosa  # noqa: F401
            self._loaded = True
        except ImportError as e:
            raise DrumAnalysisError(
                "librosa is required for drum analysis. "
                "Install with: pip install librosa"
            ) from e

    def analyze(
        self,
        drums: np.ndarray,
        sr: int,
        beats: list[float],
        bpm: float,
        duration: float,
    ) -> dict:
        """Analyze drum stem for percussion events.

        Args:
            drums: Drum stem audio array (mono).
            sr: Sample rate.
            beats: Beat timestamps from beat analysis.
            bpm: BPM from beat analysis.
            duration: Audio duration in seconds.

        Returns:
            dict with events, warnings, features.
        """
        self._ensure_loaded()

        if len(drums) == 0:
            return {"events": [], "warnings": ["Drum stem is empty"], "features": {}}

        warnings: list[str] = []
        beats_arr = np.array(beats, dtype=np.float64)

        # --- Path 1: General onset detection (hi-hat, snare, drum_onset) ---
        onsets, onset_strengths = self._detect_onsets(drums, sr)

        general_events: list[dict] = []
        if len(onsets) > 0:
            features = self._extract_features(drums, sr, onsets)

            for i, onset_time in enumerate(onsets):
                strength = float(onset_strengths[i]) if i < len(onset_strengths) else 0.5
                feat = {k: v[i] for k, v in features.items()}

                nearest_beat, beat_delta = self._align_to_beat(onset_time, beats_arr)
                event_type, confidence = self._classify_event(feat)

                general_events.append({
                    "time": float(onset_time),
                    "type": event_type,
                    "strength": strength,
                    "confidence": confidence,
                    "nearest_beat": nearest_beat,
                    "beat_delta_seconds": round(beat_delta, 6),
                    "beat_position": self._beat_position(onset_time, beats_arr),
                    "source": "general_onset",
                })

        # --- Path 2: Dedicated kick detection ---
        kick_events = self._detect_kicks(drums, beats_arr)

        # --- Merge: remove general events that overlap with kicks ---
        events = self._merge_events(general_events, kick_events)

        logger.info(
            "Detected %d drum events (%s)",
            len(events),
            self._type_summary(events),
        )

        return {
            "events": events,
            "warnings": warnings,
            "features": {
                "onset_count": len(onsets),
                "kick_count": sum(1 for e in events if e["type"] == "kick"),
            },
        }

    def _detect_kicks(
        self, drums: np.ndarray, beats: np.ndarray
    ) -> list[dict]:
        """Run the dedicated kick detector."""
        from hearbeat.kick_detector import KickDetector

        detector = KickDetector(sr=self.sr)
        return detector.detect(drums, beats)

    def _merge_events(
        self, general: list[dict], kicks: list[dict]
    ) -> list[dict]:
        """Merge general onset events with kick events.

        Kick events take priority. General events within 50ms of a kick
        are reclassified as drum_onset (they likely represent the same
        physical event).
        """
        if not kicks:
            return general

        kick_times = np.array([e["time"] for e in kicks])
        min_gap = 0.05  # 50ms

        merged = list(kicks)
        for ge in general:
            if len(kick_times) > 0:
                min_dist = float(np.min(np.abs(kick_times - ge["time"])))
                if min_dist < min_gap:
                    # This general event overlaps with a kick — reclassify
                    ge["type"] = "drum_onset"
                    ge["confidence"] = max(ge["confidence"], 0.3)
            merged.append(ge)

        merged.sort(key=lambda e: e["time"])
        return merged

    def _detect_onsets(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
        """Detect onsets using librosa (reliable cross-platform)."""
        import librosa

        hop_length = 512
        onset_env = librosa.onset.onset_strength(
            y=audio.astype(np.float32), sr=sr, hop_length=hop_length
        )
        onset_frames = librosa.onset.onset_detect(
            y=audio.astype(np.float32), sr=sr, hop_length=hop_length, onset_envelope=onset_env
        )

        if len(onset_frames) == 0:
            return np.array([]), np.array([])

        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

        strengths = np.zeros(len(onset_frames))
        for i, frame in enumerate(onset_frames):
            if frame < len(onset_env):
                strengths[i] = onset_env[frame]

        if strengths.max() > 0:
            strengths = strengths / strengths.max()

        return onset_times, strengths

    def _extract_features(
        self, audio: np.ndarray, sr: int, onset_times: np.ndarray
    ) -> dict[str, np.ndarray]:
        """Extract spectral features at each onset time for classification."""
        frame_size = 2048
        n_onsets = len(onset_times)

        spectral_centroid = np.zeros(n_onsets)
        low_band_energy = np.zeros(n_onsets)
        mid_band_energy = np.zeros(n_onsets)
        high_band_energy = np.zeros(n_onsets)
        total_energy = np.zeros(n_onsets)
        spectral_bandwidth = np.zeros(n_onsets)

        for i, t in enumerate(onset_times):
            center = int(t * sr)
            start = max(0, center - frame_size // 2)
            end = min(len(audio), center + frame_size // 2)
            segment = audio[start:end]

            if len(segment) < 2:
                continue

            fft = np.abs(np.fft.rfft(segment))
            freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)

            if fft.sum() > 0:
                spectral_centroid[i] = np.sum(freqs * fft) / np.sum(fft)
                mean_centroid = spectral_centroid[i]
                spectral_bandwidth[i] = np.sqrt(
                    np.sum(fft * (freqs - mean_centroid) ** 2) / np.sum(fft)
                )
            else:
                spectral_centroid[i] = 0.0
                spectral_bandwidth[i] = 0.0

            total_energy[i] = np.sum(fft ** 2)
            if total_energy[i] > 0:
                low_mask = freqs < 200
                mid_mask = (freqs >= 200) & (freqs < 2000)
                high_mask = freqs >= 2000

                low_band_energy[i] = np.sum(fft[low_mask] ** 2) / total_energy[i] if low_mask.any() else 0
                mid_band_energy[i] = np.sum(fft[mid_mask] ** 2) / total_energy[i] if mid_mask.any() else 0
                high_band_energy[i] = np.sum(fft[high_mask] ** 2) / total_energy[i] if high_mask.any() else 0

        return {
            "spectral_centroid": spectral_centroid,
            "spectral_bandwidth": spectral_bandwidth,
            "low_band_energy": low_band_energy,
            "mid_band_energy": mid_band_energy,
            "high_band_energy": high_band_energy,
            "total_energy": total_energy,
        }

    def _classify_event(self, feat: dict[str, float]) -> tuple[str, float]:
        """Classify a drum event based on spectral features.

        Returns (event_type, confidence).
        Uses conservative classification - returns 'drum_onset' when uncertain.
        """
        centroid = feat.get("spectral_centroid", 0)
        low_e = feat.get("low_band_energy", 0)
        mid_e = feat.get("mid_band_energy", 0)
        high_e = feat.get("high_band_energy", 0)
        bandwidth = feat.get("spectral_bandwidth", 0)

        kick_score = 0.0
        snare_score = 0.0
        hihat_score = 0.0

        # Kick: low centroid, high low-band energy, narrow bandwidth
        if centroid < 200:
            kick_score += 0.3
        if centroid < 150:
            kick_score += 0.2
        if low_e > 0.5:
            kick_score += 0.3
        if low_e > 0.7:
            kick_score += 0.2
        if bandwidth < 500:
            kick_score += 0.2

        # Snare: mid centroid, high mid-band energy, moderate bandwidth
        if 300 < centroid < 1500:
            snare_score += 0.3
        if mid_e > 0.3:
            snare_score += 0.3
        if 400 < bandwidth < 1500:
            snare_score += 0.2
        if 500 < centroid < 1200:
            snare_score += 0.2

        # Hi-hat: high centroid, high high-band energy, wide bandwidth
        if centroid > 2000:
            hihat_score += 0.3
        if centroid > 4000:
            hihat_score += 0.2
        if high_e > 0.3:
            hihat_score += 0.3
        if high_e > 0.5:
            hihat_score += 0.2
        if bandwidth > 1500:
            hihat_score += 0.2

        scores = {
            "kick": kick_score,
            "snare": snare_score,
            "hihat": hihat_score,
        }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score >= 0.6:
            return best_type, min(best_score, 1.0)

        return "drum_onset", max(best_score, 0.3)

    def _align_to_beat(
        self, onset_time: float, beats: np.ndarray
    ) -> tuple[float, float]:
        """Find nearest beat and delta."""
        if len(beats) == 0:
            return 0.0, 0.0

        idx = int(np.argmin(np.abs(beats - onset_time)))
        nearest = float(beats[idx])
        delta = onset_time - nearest
        return nearest, delta

    def _beat_position(self, onset_time: float, beats: np.ndarray) -> float:
        """Calculate normalized position within beat cycle (0.0 to 1.0)."""
        if len(beats) < 2:
            return 0.0

        idx = int(np.searchsorted(beats, onset_time)) - 1
        idx = max(0, min(idx, len(beats) - 2))

        beat_start = beats[idx]
        beat_end = beats[idx + 1]
        beat_duration = beat_end - beat_start

        if beat_duration <= 0:
            return 0.0

        position = (onset_time - beat_start) / beat_duration
        return float(np.clip(position, 0.0, 1.0))

    @staticmethod
    def _type_summary(events: list[dict]) -> str:
        """Summarize event type distribution."""
        counts: dict[str, int] = {}
        for e in events:
            t = e["type"]
            counts[t] = counts.get(t, 0) + 1
        parts = [f"{v} {k}" for k, v in sorted(counts.items())]
        return ", ".join(parts) if parts else "none"
