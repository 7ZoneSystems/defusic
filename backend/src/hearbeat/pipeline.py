"""Full analysis pipeline: orchestrates all stages."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from hearbeat.audio_extractor import extract_audio, get_audio_duration, check_audio_stream
from hearbeat.beat_analyzer import BeatAnalyzer, BeatAnalysisError
from hearbeat.bass_analyzer import BassAnalyzer, BassAnalysisError
from hearbeat.config import OUTPUT_DIR
from hearbeat.event_fusion import fuse_events
from hearbeat.models import AnalysisResult, RhythmInfo, SourceInfo

logger = logging.getLogger(__name__)


class AnalysisPipelineError(Exception):
    """Raised when the analysis pipeline fails."""


def analyze_file(
    input_path: Path,
    output_dir: Path | None = None,
    output_json: bool = True,
) -> AnalysisResult:
    """Run the full analysis pipeline on a media file.

    Args:
        input_path: Path to audio/video file (MP4, MP3, etc.)
        output_dir: Where to save JSON output. None = auto.
        output_json: Whether to write the JSON file.

    Returns:
        AnalysisResult with all events and metadata.
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    all_warnings: list[str] = []
    metadata: dict = {}

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

    # Get duration
    duration = get_audio_duration(wav_path)
    sample_rate = 44100  # We normalize to this

    source_info = SourceInfo(
        filename=input_path.name,
        duration_seconds=round(duration, 3),
        sample_rate=sample_rate,
    )

    # Step 3: Beat analysis
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

    # Step 4: Bass analysis
    logger.info("=== Step 4: Bass analysis ===")
    bass_analyzer = BassAnalyzer()
    try:
        bass_result = bass_analyzer.analyze(wav_path)
    except BassAnalysisError as e:
        logger.warning("Bass analysis failed: %s", e)
        bass_result = {
            "events": [],
            "warnings": [f"Bass analysis failed: {e}"],
        }
        all_warnings.append(f"Bass analysis failed: {e}")

    all_warnings.extend(bass_result.get("warnings", []))

    bass_events = bass_result.get("events", [])

    # Step 5: Event fusion
    logger.info("=== Step 5: Event fusion ===")
    events, bass_details, fusion_warnings = fuse_events(beat_result, bass_events)
    all_warnings.extend(fusion_warnings)

    # Build result
    result = AnalysisResult(
        source=source_info,
        rhythm=rhythm_info,
        events=events,
        bass_events_raw=bass_details,
        warnings=all_warnings,
        metadata=metadata,
    )

    # Step 6: Save JSON
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
        "Analysis complete: %d events (%d beats, %d bass)",
        len(events),
        sum(1 for e in events if e.type.value == "beat"),
        sum(1 for e in events if e.type.value.startswith("bass")),
    )

    return result
