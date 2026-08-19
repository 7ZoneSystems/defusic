"""Demucs-based source separation: extracts all stems from audio once."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from hearbeat.config import DEVICE, DEMUCS_MODEL, MODELS_DIR

logger = logging.getLogger(__name__)


class StemExtractionError(Exception):
    """Raised when source separation fails."""


class StemExtractor:
    """Extracts all stems (bass, drums, vocals, other) using Demucs.

    Separation is performed once; individual stems are cached.
    """

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or DEMUCS_MODEL
        self.device = device or DEVICE
        self.models_dir = MODELS_DIR
        self._separator = None

    def _ensure_loaded(self) -> None:
        if self._separator is not None:
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
                logger.info("Loading Demucs from cache/hub: %s", self.model_name)
                self._separator = Separator(
                    model=self.model_name,
                    device=self.device,
                )
            logger.info(
                "Loaded Demucs separator: model=%s, device=%s",
                self.model_name, self.device,
            )
        except ImportError as e:
            raise StemExtractionError(
                "Demucs is required for source separation. "
                "Install with: pip install demucs"
            ) from e

    def separate(self, wav_path: Path) -> dict[str, tuple[np.ndarray, int]]:
        """Separate audio into stems.

        Returns:
            Dict mapping stem name to (audio_array, sample_rate).
            Keys: 'bass', 'drums', 'vocals', 'other'
        """
        self._ensure_loaded()

        logger.info("Running Demucs separation on: %s", wav_path)
        _, separated = self._separator.separate_audio_file(str(wav_path))
        sr = self._separator.samplerate

        stems: dict[str, tuple[np.ndarray, int]] = {}
        for name, tensor in separated.items():
            audio = tensor.cpu().numpy()
            if audio.ndim > 1 and audio.shape[0] > 1:
                audio = audio.mean(axis=0)
            elif audio.ndim > 1:
                audio = audio[0]
            stems[name] = (audio.astype(np.float32), sr)
            logger.info("Extracted stem '%s': %.1fs", name, len(audio) / sr)

        return stems

    def get_stems_list(self) -> list[str]:
        """Return the list of stem names the model produces."""
        return ["bass", "drums", "vocals", "other"]
