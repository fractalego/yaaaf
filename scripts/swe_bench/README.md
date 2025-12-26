# SWE-bench Dataset Scripts

Scripts for downloading and working with the SWE-bench/SWE-smith-trajectories dataset from HuggingFace.

## Setup

This directory is independent from the main repository. Install dependencies separately:

```bash
cd scripts/swe_bench
pip install -r requirements.txt
```

Or with a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Download the dataset

```bash
python download_dataset.py
```

### Options

- `--output-dir`: Directory to save the dataset (default: `./swe_smith_trajectories`)
- `--split`: Specific split to download (e.g., `train`). If not specified, downloads all splits.

### Examples

```bash
# Download all splits to default directory
python download_dataset.py

# Download to a custom directory
python download_dataset.py --output-dir ./data/swe_bench

# Download only the train split
python download_dataset.py --split train
```

## Dataset Info

- **Source**: [SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories)
- **Description**: Trajectories for SWE-smith, a tool for generating software engineering benchmarks
