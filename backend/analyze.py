#!/usr/bin/env python3
"""Hearbeat: Stage 1 Bass + Beat Musical Event Extraction Engine.

Usage:
    python analyze.py <input_file> [-o output_dir] [-v]

Example:
    python analyze.py song.mp4
    python analyze.py song.mp3 -o ./results -v
"""

from hearbeat.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
