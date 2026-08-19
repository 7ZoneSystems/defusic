"""Beat analysis using Essentia's RhythmExtractor2013."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class BeatAnalysisError(Exception):
    """Raised when beat analysis fails."""


class BeatAnalyzer:
    """Extracts BPM and beat timestamps using Essentia."""

    def __init__(self) -> None:
        self._algorithm = None

    def _ensure_loaded(self) -> None:
        if self._algorithm is not None:
            return
        try:
            import essentia
            import essentia.standard as es

            self._algorithm = es.RhythmExtractor2013(method="multifeature")
            logger.info("Loaded Essentia RhythmExtractor2013 (multifeature)")
        except ImportError as e:
            raise BeatAnalysisError(
                "Essentia is required for beat analysis. "
                "Install with: pip install essentia"
            ) from e

    def analyze(self, wav_path: Path) -> dict:
        """Analyze beats in a WAV file.

        Returns:
            dict with keys: bpm, confidence, beats (list of float timestamps)
        """
        self._ensure_loaded()

        import essentia.standard as es

        logger.info("Loading audio for beat analysis: %s", wav_path)
        loader = es.MonoLoader(filename=str(wav_path), sampleRate=44100)
        audio = loader()

        if len(audio) == 0:
            raise BeatAnalysisError("Audio file is empty or unreadable")

        duration = len(audio) / 44100.0
        logger.info("Loaded %.1fs of audio for beat analysis", duration)

        bpm, beats, beats_confidence, _, _ = self._algorithm(audio)

        # Essentia can return confidence > 1.0; clamp to 0-1
        beats_confidence = max(0.0, min(1.0, float(beats_confidence)))

        logger.info(
            "Beat analysis: BPM=%.2f, confidence=%.3f, %d beats detected",
            bpm, beats_confidence, len(beats),
        )

        # Handle edge cases
        warnings: list[str] = []
        if beats_confidence < 0.3:
            warnings.append(
                f"Low-confidence tempo estimate (confidence={beats_confidence:.3f})"
            )
        if bpm < 50:
            warnings.append(f"Very low BPM detected ({bpm:.1f}), possible half-time")
        if bpm > 200:
            warnings.append(f"Very high BPM detected ({bpm:.1f}), possible double-time")

        return {
            "bpm": float(bpm),
            "confidence": float(beats_confidence),
            "beats": [float(b) for b in beats],
            "beat_count": len(beats),
            "duration": duration,
            "warnings": warnings,
        }
