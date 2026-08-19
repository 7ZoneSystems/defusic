"""Reusable Butterworth SOS filter bank for frequency-band analysis.

Provides configurable bandpass filtering using scipy.signal Butterworth IIR
filters in second-order-section (SOS) representation. Designed for both
offline analysis (sosfiltfilt) and future real-time streaming (sosfilt).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt

logger = logging.getLogger(__name__)

# Default filter order — modest, stable, suitable for music analysis
DEFAULT_FILTER_ORDER = 4

# Default bands for bass/kick analysis
DEFAULT_BANDS: dict[str, tuple[float, float]] = {
    "subbass": (20.0, 60.0),
    "bass": (60.0, 150.0),
    "lowmid": (150.0, 250.0),
    "kick_analysis": (25.0, 180.0),
}


@dataclass
class FilterBand:
    """A single frequency band with its SOS filter coefficients."""

    name: str
    low_hz: float
    high_hz: float
    order: int
    sos: np.ndarray = field(repr=False)

    @property
    def center_hz(self) -> float:
        return (self.low_hz + self.high_hz) / 2.0

    @property
    def bandwidth_hz(self) -> float:
        return self.high_hz - self.low_hz


class FilterBank:
    """Configurable Butterworth SOS filter bank.

    Creates bandpass filters for specified frequency ranges and provides
    both offline (zero-phase) and causal filtering methods.

    Usage:
        fb = FilterBank(sr=44100, bands={"bass": (60, 150), "kick": (25, 180)})
        bass_filtered = fb.filter_band(audio, "bass", causal=False)
        kick_filtered = fb.filter_band(audio, "kick", causal=True)
    """

    def __init__(
        self,
        sr: int,
        bands: dict[str, tuple[float, float]] | None = None,
        order: int = DEFAULT_FILTER_ORDER,
    ) -> None:
        self.sr = sr
        self.order = order
        self.nyq = sr / 2.0
        self._bands: dict[str, FilterBand] = {}

        band_defs = bands or DEFAULT_BANDS
        for name, (low_hz, high_hz) in band_defs.items():
            self._add_band(name, low_hz, high_hz, order)

    def _add_band(self, name: str, low_hz: float, high_hz: float, order: int) -> None:
        """Create and store a Butterworth SOS bandpass filter."""
        nyq = self.nyq
        low = low_hz / nyq
        high = high_hz / nyq

        # Clamp to valid range
        low = max(low, 1e-5)
        high = min(high, 0.9999)

        if low >= high:
            logger.warning(
                "Filter band '%s' has invalid range [%.1f, %.1f] Hz at sr=%d — skipping",
                name, low_hz, high_hz, self.sr,
            )
            return

        sos = butter(order, [low, high], btype="band", output="sos")
        self._bands[name] = FilterBand(
            name=name,
            low_hz=low_hz,
            high_hz=high_hz,
            order=order,
            sos=sos,
        )

    @property
    def band_names(self) -> list[str]:
        return list(self._bands.keys())

    def get_band(self, name: str) -> FilterBand | None:
        return self._bands.get(name)

    def filter_band(
        self,
        audio: np.ndarray,
        band_name: str,
        causal: bool = False,
    ) -> np.ndarray:
        """Filter audio through a specific band.

        Args:
            audio: Input audio signal (1D float array).
            band_name: Name of the band to filter through.
            causal: If True, use sosfilt (causal, real-time compatible).
                    If False, use sosfiltfilt (zero-phase, offline only).

        Returns:
            Filtered audio array.
        """
        band = self._bands.get(band_name)
        if band is None:
            raise ValueError(f"Unknown filter band: {band_name}")

        if causal:
            return sosfilt(band.sos, audio).astype(np.float32)
        else:
            return sosfiltfilt(band.sos, audio).astype(np.float32)

    def filter_all(
        self,
        audio: np.ndarray,
        causal: bool = False,
    ) -> dict[str, np.ndarray]:
        """Filter audio through all bands.

        Returns:
            Dict mapping band name to filtered audio.
        """
        return {
            name: self.filter_band(audio, name, causal=causal)
            for name in self._bands
        }

    def band_energy_envelope(
        self,
        audio: np.ndarray,
        band_name: str,
        hop_length: int = 512,
        frame_length: int = 2048,
        causal: bool = False,
    ) -> np.ndarray:
        """Compute RMS energy envelope for a filtered band.

        Args:
            audio: Input audio signal.
            band_name: Band to filter through.
            hop_length: Hop between frames.
            frame_length: Window size in samples.
            causal: Whether to use causal filtering.

        Returns:
            RMS energy per frame (1D array).
        """
        filtered = self.filter_band(audio, band_name, causal=causal)
        return _frame_rms(filtered, frame_length, hop_length)

    def multi_band_energy(
        self,
        audio: np.ndarray,
        hop_length: int = 512,
        frame_length: int = 2048,
        causal: bool = False,
    ) -> dict[str, np.ndarray]:
        """Compute energy envelopes for all bands.

        Returns:
            Dict mapping band name to RMS energy array.
        """
        return {
            name: self.band_energy_envelope(
                audio, name, hop_length, frame_length, causal=causal,
            )
            for name in self._bands
        }


def _frame_rms(
    signal: np.ndarray, frame_length: int, hop_length: int
) -> np.ndarray:
    """Compute RMS energy per frame using stride tricks."""
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
