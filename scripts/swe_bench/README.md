# SWE-bench Scripts

Scripts for working with SWE-bench datasets and evaluating YAAAF on software engineering tasks.

## Structure

```
swe_bench/
├── planner_examples/     # Generate planner dataset from SWE-smith trajectories
│   ├── convert_to_planner.py
│   ├── download_dataset.py
│   ├── explore_dataset.py
│   └── requirements.txt
│
└── evaluation/           # Evaluate YAAAF on SWE-bench Lite
    ├── run_evaluation.py
    ├── repo_manager.py
    ├── yaaaf_runner.py
    └── requirements.txt
```

## Subfolders

### `planner_examples/`
Scripts to download SWE-smith trajectories and convert them to planner dataset format.
Used to generate training examples for the PlannerAgent.

See [planner_examples/README.md](planner_examples/README.md) for details.

### `evaluation/`
Scripts to evaluate YAAAF on SWE-bench Lite benchmark (300 real GitHub issues).

Quick start:
```bash
cd evaluation
pip install -r requirements.txt

# List available instances
python run_evaluation.py --list

# Run on a single instance
python run_evaluation.py --instance-id django__django-11099

# Run on first 5 instances
python run_evaluation.py --num-instances 5
```

See [evaluation/README.md](evaluation/README.md) for details.
