#!/usr/bin/env python3
"""Download all required models for HearBeat analysis.

Run this once before first use:
    cd backend
    source .venv/bin/activate
    python setup_models.py

Models are saved to backend/models/ and used offline.
"""

import shutil
import sys
from pathlib import Path


def download_htdemucs(target_dir: Path) -> None:
    """Download htdemucs model to a local directory."""
    try:
        from huggingface_hub import hf_hub_download
        import yaml
    except ImportError:
        print("ERROR: huggingface_hub is required. Install with: pip install huggingface-hub")
        sys.exit(1)

    print("Downloading htdemucs model...")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Download config
    config_path = hf_hub_download("adefossez/HTDemucs", "htdemucs.yaml")
    shutil.copy(config_path, target_dir / "htdemucs.yaml")
    print(f"  Config: {target_dir / 'htdemucs.yaml'}")

    # Download model weights
    with open(config_path) as f:
        bag = yaml.safe_load(f)
    for sig in bag.get("models", []):
        weights_path = hf_hub_download("adefossez/HTDemucs", f"{sig}.safetensors")
        shutil.copy(weights_path, target_dir / f"{sig}.safetensors")
        size_mb = Path(target_dir / f"{sig}.safetensors").stat().st_size / 1024 / 1024
        print(f"  Weights: {target_dir / f'{sig}.safetensors'} ({size_mb:.1f} MB)")

    print(f"  Done: {target_dir}")


def main() -> None:
    target_dir = Path(__file__).parent / "models"
    print(f"Target directory: {target_dir}\n")

    download_htdemucs(target_dir)

    print("\nAll models downloaded. The backend will use local copies.")
    print(f"Models directory: {target_dir}")


if __name__ == "__main__":
    main()
