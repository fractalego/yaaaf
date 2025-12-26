#!/usr/bin/env python3
"""
Download the SWE-bench/SWE-smith-trajectories dataset from HuggingFace.

Usage:
    python download_dataset.py [--output-dir OUTPUT_DIR] [--split SPLIT]

Examples:
    python download_dataset.py
    python download_dataset.py --output-dir ./data
    python download_dataset.py --split train
"""

import argparse
from pathlib import Path

from datasets import load_dataset


def download_swe_smith_trajectories(
    output_dir: str = "./swe_smith_trajectories",
    split: str | None = None,
) -> None:
    """
    Download the SWE-smith-trajectories dataset from HuggingFace.

    Args:
        output_dir: Directory to save the dataset
        split: Specific split to download (e.g., 'train', 'test'). If None, downloads all.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading SWE-bench/SWE-smith-trajectories dataset...")
    print(f"Output directory: {output_path.absolute()}")

    if split:
        print(f"Downloading split: {split}")
        dataset = load_dataset("SWE-bench/SWE-smith-trajectories", split=split)
        dataset.save_to_disk(output_path / split)
        print(f"Saved {split} split to {output_path / split}")
    else:
        print("Downloading all splits...")
        dataset = load_dataset("SWE-bench/SWE-smith-trajectories")
        dataset.save_to_disk(output_path)
        print(f"Saved dataset to {output_path}")

    print("Download complete!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the SWE-bench/SWE-smith-trajectories dataset from HuggingFace"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./swe_smith_trajectories",
        help="Directory to save the dataset (default: ./swe_smith_trajectories)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default=None,
        help="Specific split to download (e.g., 'train'). If not specified, downloads all.",
    )

    args = parser.parse_args()
    download_swe_smith_trajectories(output_dir=args.output_dir, split=args.split)


if __name__ == "__main__":
    main()
