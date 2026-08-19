"""CLI entry point for hearbeat analysis."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from hearbeat.pipeline import analyze_file
from hearbeat.models import EventType


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hearbeat",
        description="Stage 1: Bass + Beat Musical Event Extraction Engine",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to audio/video file (MP4, MP3, WAV, etc.)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="Output directory for JSON (default: ./outputs)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing JSON file (print to stdout only)",
    )
    parser.add_argument(
        "--play",
        action="store_true",
        help="Play the extracted beat click track through speakers",
    )
    parser.add_argument(
        "--play-bass",
        action="store_true",
        help="Play a multi-layer track with beats + bass events",
    )
    parser.add_argument(
        "--save-click-track",
        type=Path,
        default=None,
        metavar="PATH",
        help="Save the beat click track as a WAV file",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.input.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        result = analyze_file(
            input_path=args.input,
            output_dir=args.output_dir,
            output_json=not args.no_json,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.no_json:
        print(result.model_dump_json(indent=2))
    else:
        stem = args.input.stem
        out_dir = args.output_dir or Path("./outputs")
        json_path = out_dir / f"{stem}.json"
        print(f"Analysis saved to: {json_path}")
        print(f"  BPM: {result.rhythm.bpm:.2f} (confidence: {result.rhythm.confidence:.3f})")
        print(f"  Beats: {result.rhythm.beat_count}")
        print(f"  Events: {len(result.events)}")
        print(f"  Bass events: {len(result.bass_events_raw)}")
        if result.warnings:
            print(f"  Warnings: {len(result.warnings)}")
            for w in result.warnings:
                print(f"    - {w}")

    # Beat playback
    if args.play or args.play_bass or args.save_click_track:
        from hearbeat.beat_player import (
            generate_click_train,
            generate_multi_track,
            play_audio,
            save_wav,
        )

        beats = result.rhythm.beats
        bass_beat_times = [
            e.time for e in result.events if e.type == EventType.BASS_BEAT
        ]
        bass_offbeat_times = [
            e.time for e in result.events if e.type == EventType.BASS_OFFBEAT
        ]

        if args.play_bass or args.save_click_track:
            audio, sr = generate_multi_track(
                beat_timestamps=beats,
                bass_beat_timestamps=bass_beat_times,
                bass_offbeat_timestamps=bass_offbeat_times,
            )
            label = "multi-track"
        else:
            audio, sr = generate_click_train(beats)
            label = "beat clicks"

        if args.save_click_track:
            save_wav(audio, args.save_click_track, sr)
            print(f"  Click track saved: {args.save_click_track}")

        if args.play:
            print(f"  Playing {label}... (Ctrl+C to stop)")
            try:
                play_audio(audio, sr)
            except KeyboardInterrupt:
                print("\n  Stopped.")
            print("  Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
