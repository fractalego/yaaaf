# SWE-bench Lite Evaluation

Evaluate YAAAF on the SWE-bench Lite benchmark (300 real GitHub issues).

## Setup

```bash
cd scripts/swe_bench/evaluation
pip install -r requirements.txt
```

## Prerequisites

**1. Start YAAAF backend** (in a separate terminal):
```bash
# With default config (needs code_edit agent)
YAAAF_CONFIG=/path/to/config.json python -m yaaaf backend 4000
```

Your config.json should include the `code_edit` agent:
```json
{
  "client": {
    "model": "qwen2.5:32b",
    "host": "http://localhost:11434"
  },
  "agents": ["bash", "code_edit", "answerer"]
}
```

**2. Ensure Ollama is running**:
```bash
ollama serve
ollama pull qwen2.5:32b
```

## Usage

### List available instances

```bash
python run_evaluation.py --list
```

### Run on a single instance

```bash
python run_evaluation.py --instance-id django__django-11099
```

### Run on first N instances

```bash
python run_evaluation.py --num-instances 5
```

### Run on all 300 instances

```bash
python run_evaluation.py --all
```

### Options

| Option | Description |
|--------|-------------|
| `--instance-id ID` | Evaluate specific instance |
| `--num-instances N` | Number of instances to evaluate |
| `--all` | Evaluate all 300 instances |
| `--list` | List available instances |
| `--split {dev,test}` | Dataset split (default: test) |
| `--workspace DIR` | Directory for cloned repos (default: ./swe_bench_workspace) |
| `--output DIR` | Directory for results (default: ./evaluation_results) |
| `--model MODEL` | Ollama model (default: qwen2.5:32b) |
| `--host URL` | Ollama host (default: http://localhost:11434) |
| `--verbose` | Enable verbose logging |

## How it Works

1. **Load instance**: Fetches issue from SWE-bench Lite dataset
2. **Clone repo**: Clones the GitHub repo at the base commit
3. **Setup env**: Creates Python virtualenv and installs dependencies
4. **Run YAAAF**: Passes the issue to YAAAF with BashAgent + CodeEditAgent
5. **Run tests**: Executes the `FAIL_TO_PASS` tests to verify the fix
6. **Check regressions**: Runs `PASS_TO_PASS` tests to ensure no regressions

## Output

Results are saved as JSON files in the output directory:

```json
{
  "instance_id": "django__django-11099",
  "repo": "django/django",
  "resolved": true,
  "status": "resolved",
  "yaaaf_response": "...",
  "final_tests": {
    "success": true,
    "passed": 5,
    "failed": 0
  }
}
```

## Dataset Info

**SWE-bench Lite** contains 300 issues from 11 Python repositories:
- django/django
- matplotlib/matplotlib
- scikit-learn/scikit-learn
- sympy/sympy
- pytest-dev/pytest
- And more...

Each issue has:
- `problem_statement`: The GitHub issue text
- `base_commit`: Starting point (before fix)
- `patch`: Gold standard solution
- `FAIL_TO_PASS`: Tests that should pass after fix
- `PASS_TO_PASS`: Tests that must still pass
