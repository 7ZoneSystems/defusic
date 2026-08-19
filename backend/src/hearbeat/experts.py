"""Independent onset detection experts for multi-expert fusion.

Each expert computes an onset strength envelope from audio or a shared
spectrogram. Experts are designed to be complementary:

- HFC: strong for percussive/high-frequency events (hi-hat, cymbal)
- Complex-domain: sensitive to magnitude AND phase changes (good for kicks)
- Spectral Flux: general magnitude-spectrum change detector
- RMS Difference: energy envelope onset detector

All experts use the same STFT representation where possible.

References:
- Essentia onset detection: https://essentia.upf.edu/reference/streaming_OnsetDetection.html
- Score-level fusion: https://www.researchgate.net/publication/220722982
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExpertOutput:
    """Output from a single onset expert."""

    name: str
    onset_envelope: np.ndarray
    sample_rate: int
    hop_length: int

    @property
    def n_frames(self) -> int:
        return len(self.onset_envelope)

    def frame_to_time(self, frame: int) -> float:
        return frame * self.hop_length / self.sample_rate


def compute_stft(
    audio: np.ndarray,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute STFT magnitude and phase.

    Returns:
        (magnitude, phase) arrays of shape (n_freq_bins, n_frames)
    """
    try:
        import librosa
        stft = librosa.stft(
            audio.astype(np.float32),
            n_fft=n_fft,
            hop_length=hop_length,
        )
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        return magnitude, phase
    except ImportError:
        from scipy.signal import stft as scipy_stft
        _, _, Zxx = scipy_stft(audio, fs=44100, nperseg=n_fft, noverlap=n_fft - hop_length)
        magnitude = np.abs(Zxx)
        phase = np.angle(Zxx)
        return magnitude, phase


def hfc_expert(
    magnitude: np.ndarray,
    sr: int,
    hop_length: int,
) -> ExpertOutput:
    """High Frequency Content onset detector.

    Weights each frequency bin by its frequency, emphasizing high-frequency
    content. Strong for hi-hat, cymbal, and sharp percussive events.

    Reference: Essentia OnsetDetection (HFC method).
    """
    n_freqs, n_frames = magnitude.shape
    freqs = np.arange(n_freqs, dtype=np.float64)

    # Weight by frequency: HFC = sum(magnitude * freq_index)
    weights = freqs[:, np.newaxis]
    hfc = np.sum(magnitude * weights, axis=0)

    # Normalize
    if hfc.max() > 0:
        hfc = hfc / hfc.max()

    return ExpertOutput(
        name="hfc",
        onset_envelope=hfc.astype(np.float64),
        sample_rate=sr,
        hop_length=hop_length,
    )


def complex_domain_expert(
    magnitude: np.ndarray,
    phase: np.ndarray,
    sr: int,
    hop_length: int,
) -> ExpertOutput:
    """Complex-domain onset detector.

    Sensitive to both magnitude and phase changes. Good for detecting
    onsets that have phase discontinuities (e.g., kick drum attacks).

    The complex-domain ODF computes:
        ODF[n] = sum |X[n] - X[n-1] * exp(j * delta_phase)|^2

    where delta_phase is the expected phase advance based on the STFT hop.

    Reference: Essentia OnsetDetection (complex method).
    """
    n_freqs, n_frames = magnitude.shape

    if n_frames < 2:
        return ExpertOutput(
            name="complex",
            onset_envelope=np.zeros(n_frames, dtype=np.float64),
            sample_rate=sr,
            hop_length=hop_length,
        )

    # Expected phase advance per hop
    expected_phase = 2.0 * np.pi * hop_length * np.arange(n_freqs) / (n_freqs * 2)

    odf = np.zeros(n_frames, dtype=np.float64)
    for n in range(1, n_frames):
        # Predicted complex spectrum based on previous frame
        predicted = magnitude[:, n - 1] * np.exp(1j * (phase[:, n - 1] + expected_phase))
        # Actual complex spectrum
        actual = magnitude[:, n] * np.exp(1j * phase[:, n])
        # Complex difference
        diff = actual - predicted
        odf[n] = np.sum(np.abs(diff) ** 2)

    # Normalize
    if odf.max() > 0:
        odf = odf / odf.max()

    return ExpertOutput(
        name="complex",
        onset_envelope=odf.astype(np.float64),
        sample_rate=sr,
        hop_length=hop_length,
    )


def spectral_flux_expert(
    magnitude: np.ndarray,
    sr: int,
    hop_length: int,
) -> ExpertOutput:
    """Spectral flux onset detector.

    Measures the positive change in magnitude spectrum between frames.
    Good general-purpose transient detector.

    Flux = sum(max(0, |X[n]| - |X[n-1]|))
    """
    n_freqs, n_frames = magnitude.shape

    if n_frames < 2:
        return ExpertOutput(
            name="flux",
            onset_envelope=np.zeros(n_frames, dtype=np.float64),
            sample_rate=sr,
            hop_length=hop_length,
        )

    diff = np.diff(magnitude, axis=1)
    flux = np.maximum(0, diff).sum(axis=0)

    # Pad to match frame count
    flux = np.concatenate([[0.0], flux])

    # Normalize
    if flux.max() > 0:
        flux = flux / flux.max()

    return ExpertOutput(
        name="flux",
        onset_envelope=flux.astype(np.float64),
        sample_rate=sr,
        hop_length=hop_length,
    )


def rms_difference_expert(
    audio: np.ndarray,
    sr: int,
    hop_length: int,
    n_fft: int = 2048,
) -> ExpertOutput:
    """RMS energy difference onset detector.

    Computes the positive difference of the RMS energy envelope.
    Simple but effective for detecting sudden energy increases.
    """
    n_frames = 1 + (len(audio) - n_fft) // hop_length
    if n_frames <= 0:
        return ExpertOutput(
            name="rms_diff",
            onset_envelope=np.zeros(1, dtype=np.float64),
            sample_rate=sr,
            hop_length=hop_length,
        )

    # Compute RMS per frame
    frames = np.lib.stride_tricks.as_strided(
        audio,
        shape=(n_frames, n_fft),
        strides=(audio.strides[0] * hop_length, audio.strides[0]),
    )
    rms = np.sqrt(np.mean(frames**2, axis=1))

    # Positive difference
    diff = np.diff(rms)
    pos_diff = np.maximum(0, diff)
    rms_odf = np.concatenate([[0.0], pos_diff])

    # Normalize
    if rms_odf.max() > 0:
        rms_odf = rms_odf / rms_odf.max()

    return ExpertOutput(
        name="rms_diff",
        onset_envelope=rms_odf.astype(np.float64),
        sample_rate=sr,
        hop_length=hop_length,
    )


def compute_all_experts(
    audio: np.ndarray,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    experts: list[str] | None = None,
) -> dict[str, ExpertOutput]:
    """Compute all onset experts for an audio signal.

    Shares the STFT computation across experts.

    Args:
        audio: Mono audio signal.
        sr: Sample rate.
        n_fft: STFT window size.
        hop_length: STFT hop length.
        experts: List of expert names to compute. None = all.

    Returns:
        Dict mapping expert name to ExpertOutput.
    """
    all_expert_names = ["hfc", "complex", "flux", "rms_diff"]
    requested = experts or all_expert_names

    # Shared STFT
    magnitude, phase = compute_stft(audio, n_fft=n_fft, hop_length=hop_length)

    result: dict[str, ExpertOutput] = {}

    if "hfc" in requested:
        result["hfc"] = hfc_expert(magnitude, sr, hop_length)

    if "complex" in requested:
        result["complex"] = complex_domain_expert(magnitude, phase, sr, hop_length)

    if "flux" in requested:
        result["flux"] = spectral_flux_expert(magnitude, sr, hop_length)

    if "rms_diff" in requested:
        result["rms_diff"] = rms_difference_expert(audio, sr, hop_length, n_fft)

    return result
