"""Full analysis pipeline: orchestrates all stages.

Updated to use filter-bank bass analysis on the original audio
(no Demucs required for bass detection) while keeping Demucs
available for drum stem separation and diagnostics.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import numpy as np

from hearbeat.audio_extractor import extract_audio, get_audio_duration, check_audio_stream
from hearbeat.beat_analyzer import BeatAnalyzer, BeatAnalysisError
from hearbeat.config import OUTPUT_DIR
from hearbeat.event_fusion import fuse_events
from hearbeat.models import (
    AnalysisMode,
    AnalysisResult,
    BassEventDetail,
    DrumEventDetail,
    RhythmInfo,
    SourceInfo,
)

logger = logging.getLogger(__name__)


class AnalysisPipelineError(Exception):
    """Raised when the analysis pipeline fails."""


def analyze_file(
    input_path: Path,
    output_dir: Path | None = None,
    output_json: bool = True,
    mode: str = "music",
) -> AnalysisResult:
    """Run the full analysis pipeline on a media file.

    Args:
        input_path: Path to audio/video file (MP4, MP3, etc.)
        output_dir: Where to save JSON output. None = auto.
        output_json: Whether to write the JSON file.
        mode: Analysis mode - 'music' or 'drumming'.

    Returns:
        AnalysisResult with all events and metadata.
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    all_warnings: list[str] = []
    metadata: dict = {"mode": mode}

    # Step 1: Check for audio stream
    logger.info("=== Step 1: Checking audio stream ===")
    if not check_audio_stream(input_path):
        raise AnalysisPipelineError(
            f"No audio stream found in: {input_path}"
        )

    # Step 2: Extract and normalize audio
    logger.info("=== Step 2: Extracting audio ===")
    try:
        wav_path = extract_audio(input_path)
    except Exception as e:
        raise AnalysisPipelineError(f"Audio extraction failed: {e}") from e

    duration = get_audio_duration(wav_path)
    sample_rate = 44100

    source_info = SourceInfo(
        filename=input_path.name,
        duration_seconds=round(duration, 3),
        sample_rate=sample_rate,
    )

    # Step 3: Beat analysis (always needed)
    logger.info("=== Step 3: Beat analysis ===")
    beat_analyzer = BeatAnalyzer()
    try:
        beat_result = beat_analyzer.analyze(wav_path)
    except BeatAnalysisError as e:
        logger.warning("Beat analysis failed: %s", e)
        beat_result = {
            "bpm": 0.0,
            "confidence": 0.0,
            "beats": [],
            "beat_count": 0,
            "duration": duration,
            "warnings": [f"Beat analysis failed: {e}"],
        }
        all_warnings.append(f"Beat analysis failed: {e}")

    all_warnings.extend(beat_result.get("warnings", []))

    rhythm_info = RhythmInfo(
        bpm=beat_result["bpm"],
        confidence=beat_result["confidence"],
        beat_count=beat_result["beat_count"],
        beats=beat_result["beats"],
    )

    # Step 4: Load original audio for filter-bank analysis
    logger.info("=== Step 4: Loading audio for analysis ===")
    import soundfile as sf
    original_audio, _ = sf.read(str(wav_path), dtype="float32")
    if original_audio.ndim > 1:
        original_audio = original_audio.mean(axis=1)

    # Step 5: Source separation (for drum stem and diagnostics)
    logger.info("=== Step 5: Source separation ===")
    stems: dict[str, tuple] = {}
    try:
        from hearbeat.stem_extractor import StemExtractor, StemExtractionError
        stem_extractor = StemExtractor()
        stems = stem_extractor.separate(wav_path)
    except Exception as e:
        logger.warning("Source separation failed: %s", e)
        all_warnings.append(f"Source separation failed: {e}")

    # Step 6: Bass analysis (filter-bank on original audio)
    logger.info("=== Step 6: Bass analysis (filter-bank) ===")
    bass_events: list[dict] = []
    bass_details: list[BassEventDetail] = []

    from hearbeat.bass_analyzer import BassAnalyzer
    bass_analyzer = BassAnalyzer(sr=sample_rate)
    try:
        bass_result = bass_analyzer.analyze_audio(original_audio)
        bass_events = bass_result.get("events", [])
        all_warnings.extend(bass_result.get("warnings", []))
        logger.info("Bass analysis: %d events", len(bass_events))
    except Exception as e:
        logger.warning("Bass analysis failed: %s", e)
        all_warnings.append(f"Bass analysis failed: {e}")

    # Step 7: Drum analysis (with dedicated kick path)
    logger.info("=== Step 7: Drum analysis ===")
    drum_events_raw: list[dict] = []
    drum_details: list[DrumEventDetail] = []
    events: list = []

    if mode == AnalysisMode.DRUMMING:
        events, drum_events_raw, drum_details = _run_drumming_pipeline(
            stems, beat_result, duration, all_warnings
        )
    else:
        # Music mode: still run drum analysis for kick detection
        events, drum_events_raw, drum_details = _run_music_drum_analysis(
            stems, beat_result, duration, all_warnings
        )

    # Fuse all events together
    events, bass_details, fusion_warnings = fuse_events(
        beat_result, bass_events, drum_events_raw
    )
    all_warnings.extend(fusion_warnings)

    result = AnalysisResult(
        schema_version="0.2" if mode == AnalysisMode.DRUMMING else "0.1",
        mode=mode,
        source=source_info,
        rhythm=rhythm_info,
        events=events,
        bass_events_raw=bass_details,
        drum_events_raw=drum_details,
        warnings=all_warnings,
        metadata=metadata,
    )

    # Step 8: Save JSON
    if output_json:
        stem = input_path.stem
        json_path = output_dir / f"{stem}.json"
        json_path.write_text(result.model_dump_json(indent=2))
        logger.info("Saved analysis to: %s", json_path)

    # Clean up temp WAV
    try:
        wav_path.unlink(missing_ok=True)
    except Exception:
        pass

    logger.info(
        "Analysis complete (mode=%s): %d events",
        mode,
        len(events),
    )

    return result


def _run_music_drum_analysis(
    stems: dict[str, tuple],
    beat_result: dict,
    duration: float,
    all_warnings: list[str],
) -> tuple[list, list[dict], list[DrumEventDetail]]:
    """Run drum analysis in music mode for kick detection."""
    from hearbeat.drum_analyzer import DrumAnalyzer, DrumAnalysisError
    from hearbeat.models import AnalysisEvent

    events = []
    drum_event_dicts = []
    drum_details = []

    if "drums" in stems:
        drums_audio, sr = stems["drums"]
        drum_analyzer = DrumAnalyzer(sr=sr)
        try:
            drum_result = drum_analyzer.analyze(
                drums_audio, sr,
                beat_result.get("beats", []),
                beat_result["bpm"],
                duration,
            )
            drum_event_dicts = drum_result.get("events", [])
            all_warnings.extend(drum_result.get("warnings", []))

            for de in drum_event_dicts:
                events.append(AnalysisEvent(
                    time=de["time"],
                    type=de["type"],
                    strength=de["strength"],
                    confidence=de.get("confidence"),
                    nearest_beat_time=de.get("nearest_beat"),
                    beat_delta_seconds=de.get("beat_delta_seconds"),
                ))
                drum_details.append(DrumEventDetail(
                    time=de["time"],
                    type=de["type"],
                    strength=de["strength"],
                    confidence=de.get("confidence", 0.3),
                    nearest_beat=de.get("nearest_beat", 0.0),
                    beat_delta_seconds=de.get("beat_delta_seconds", 0.0),
                    beat_position=de.get("beat_position", 0.0),
                ))
        except DrumAnalysisError as e:
            logger.warning("Drum analysis failed: %s", e)
            all_warnings.append(f"Drum analysis failed: {e}")
    else:
        all_warnings.append("Drum stem not available for kick detection")

    return events, drum_event_dicts, drum_details


def _run_drumming_pipeline(
    stems: dict[str, tuple],
    beat_result: dict,
    duration: float,
    all_warnings: list[str],
) -> tuple[list, list[dict], list[DrumEventDetail]]:
    """Run the Drumming mode pipeline."""
    from hearbeat.drum_analyzer import DrumAnalyzer, DrumAnalysisError
    from hearbeat.models import AnalysisEvent

    events = []
    drum_event_dicts = []
    drum_details = []

    # Add beat events first
    beats = beat_result.get("beats", [])
    confidence = beat_result.get("confidence", 0.0)
    for beat_time in beats:
        events.append(AnalysisEvent(
            time=float(beat_time),
            type="beat",
            strength=confidence,
        ))

    # Drum analysis
    if "drums" in stems:
        drums_audio, sr = stems["drums"]
        drum_analyzer = DrumAnalyzer(sr=sr)
        try:
            drum_result = drum_analyzer.analyze(
                drums_audio, sr, beats, beat_result["bpm"], duration
            )
            drum_event_dicts = drum_result.get("events", [])
            all_warnings.extend(drum_result.get("warnings", []))

            for de in drum_event_dicts:
                events.append(AnalysisEvent(
                    time=de["time"],
                    type=de["type"],
                    strength=de["strength"],
                    confidence=de.get("confidence"),
                    nearest_beat_time=de.get("nearest_beat"),
                    beat_delta_seconds=de.get("beat_delta_seconds"),
                ))
                drum_details.append(DrumEventDetail(
                    time=de["time"],
                    type=de["type"],
                    strength=de["strength"],
                    confidence=de.get("confidence", 0.3),
                    nearest_beat=de.get("nearest_beat", 0.0),
                    beat_delta_seconds=de.get("beat_delta_seconds", 0.0),
                    beat_position=de.get("beat_position", 0.0),
                ))
        except DrumAnalysisError as e:
            logger.warning("Drum analysis failed: %s", e)
            all_warnings.append(f"Drum analysis failed: {e}")
    else:
        all_warnings.append("Drum stem not available")

    return events, drum_event_dicts, drum_details
