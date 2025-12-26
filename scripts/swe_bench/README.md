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

## Scripts

### 1. Download the dataset

```bash
python download_dataset.py
```

Options:
- `--output-dir`: Directory to save the dataset (default: `./swe_smith_trajectories`)
- `--split`: Specific split to download (e.g., `train`). If not specified, downloads all splits.

### 2. Explore the dataset structure

```bash
python explore_dataset.py --num-samples 5 --output exploration_results.txt
```

Options:
- `--num-samples`: Number of samples to examine (default: 3)
- `--split`: Which split to examine: `tool`, `xml`, or `ticks` (default: tool)
- `--resolved-only`: Only show successfully resolved trajectories
- `--output`: Output file path (default: stdout)

### 3. Convert to planner dataset format

```bash
python convert_to_planner.py --num-samples 100 --output swe_bench_planner.csv
```

Options:
- `--num-samples`, `-n`: Number of samples to convert (default: 100)
- `--output`, `-o`: Output CSV file path (default: `swe_bench_planner_dataset.csv`)
- `--split`: Which split to use: `tool`, `xml`, or `ticks` (default: tool)
- `--resolved-only`: Only include successfully resolved trajectories
- `--include-metadata`: Include extra columns (instance_id, resolved, tool_counts)

## Dataset Info

- **Source**: [SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories)
- **Description**: 76k trajectories from running SWE-agent + Claude 3.7 Sonnet on SWE-smith tasks
- **Splits**: `tool` (24k), `xml` (26k), `ticks` (26k) - different message formats

## Tool to Agent Mapping

The converter maps SWE-bench tools to YAAAF agents:

| SWE-bench Tool | YAAAF Agent |
|----------------|-------------|
| `str_replace_editor` (view, create, str_replace) | `CodeEditAgent` |
| `bash` (find, grep, cd, python, pytest, etc.) | `BashAgent` |
| Problem analysis & synthesis | `AnswererAgent` |

## Generated Workflow Pattern

The converter generates workflows following this pattern:

```yaml
assets:
  problem_analysis:
    agent: AnswererAgent
    description: "Analyze the bug report"
    type: text

  relevant_files:
    agent: BashAgent
    description: "Find relevant source files"
    type: text
    inputs: [problem_analysis]

  code_analysis:
    agent: CodeEditAgent
    description: "View the source files"
    type: text
    inputs: [relevant_files]

  code_fix:
    agent: CodeEditAgent
    description: "Apply the fix"
    type: text
    inputs: [code_analysis, problem_analysis]

  verification:
    agent: BashAgent
    description: "Run tests"
    type: text
    inputs: [code_fix]

  fix_summary:
    agent: AnswererAgent
    description: "Summarize the fix"
    type: text
    inputs: [verification]
```
