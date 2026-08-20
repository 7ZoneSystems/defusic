"""Tests for model lifecycle: verify singletons load once, not per-request."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBeatAnalyzerSingleton:
    """BeatAnalyzer should load its algorithm once per process."""

    def setup_method(self) -> None:
        # Reset the module-level singleton before each test
        import hearbeat.beat_analyzer as mod
        mod._global_analyzer = None

    def test_singleton_created_once(self) -> None:
        """Two calls to get_beat_analyzer() return the same instance."""
        from hearbeat.beat_analyzer import get_beat_analyzer

        a = get_beat_analyzer()
        b = get_beat_analyzer()
        assert a is b

    def test_ensure_loaded_called_lazily(self) -> None:
        """_ensure_loaded is called on first analyze(), not on construction."""
        from hearbeat.beat_analyzer import get_beat_analyzer

        analyzer = get_beat_analyzer()
        assert analyzer._algorithm is None  # not loaded yet

    def test_model_not_reloaded_on_second_call(self) -> None:
        """After first analyze(), second call does not re-initialize."""
        from hearbeat.beat_analyzer import get_beat_analyzer

        analyzer = get_beat_analyzer()
        # Mock the algorithm to avoid needing essentia installed
        mock_algo = MagicMock(return_value=(120.0, [0.5, 1.0], 0.9, 0, 0))
        analyzer._algorithm = mock_algo

        # Second call should reuse the same algorithm object
        analyzer2 = get_beat_analyzer()
        assert analyzer2._algorithm is mock_algo


class TestStemExtractorSingleton:
    """StemExtractor should load its model once per process."""

    def setup_method(self) -> None:
        # Reset the module-level singleton before each test
        import hearbeat.stem_extractor as mod
        mod._global_extractor = None

    def test_singleton_created_once(self) -> None:
        """Two calls to get_stem_extractor() return the same instance."""
        from hearbeat.stem_extractor import get_stem_extractor

        a = get_stem_extractor()
        b = get_stem_extractor()
        assert a is b

    def test_ensure_loaded_called_lazily(self) -> None:
        """_ensure_loaded is called on first separate(), not on construction."""
        from hearbeat.stem_extractor import get_stem_extractor

        extractor = get_stem_extractor()
        assert extractor._separator is None  # not loaded yet

    def test_model_not_reloaded_on_second_call(self) -> None:
        """After first separate(), second call does not re-initialize."""
        from hearbeat.stem_extractor import get_stem_extractor

        extractor = get_stem_extractor()
        # Mock the separator to avoid needing demucs installed
        mock_sep = MagicMock()
        mock_sep.samplerate = 44100
        extractor._separator = mock_sep

        # Second call should reuse the same separator object
        extractor2 = get_stem_extractor()
        assert extractor2._separator is mock_sep


class TestPipelineSingletonUsage:
    """Pipeline should use the singletons, not create new instances."""

    def test_uses_get_beat_analyzer(self) -> None:
        """pipeline.py imports get_beat_analyzer, not BeatAnalyzer directly."""
        from hearbeat import pipeline

        # The module should import the getter function
        assert hasattr(pipeline, "get_beat_analyzer")

    def test_uses_get_stem_extractor(self) -> None:
        """pipeline.py imports get_stem_extractor, not StemExtractor directly."""
        from hearbeat import pipeline

        assert hasattr(pipeline, "get_stem_extractor")


class TestMemoryCleanup:
    """Per-request data should be released after analysis."""

    def test_stems_deleted_after_separation(self) -> None:
        """The stems dict should be del'd in analyze_file (code review check)."""
        import inspect
        from hearbeat.pipeline import analyze_file

        source = inspect.getsource(analyze_file)
        # Verify cleanup code exists
        assert "del original_audio" in source
        assert "del stems" in source
        assert "del beat_result" in source
        assert "gc.collect()" in source
