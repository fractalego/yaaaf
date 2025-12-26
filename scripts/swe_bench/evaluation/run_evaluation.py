#!/usr/bin/env python3
"""
Run YAAAF evaluation on SWE-bench Lite instances.

Requires YAAAF backend to be running:
    python -m yaaaf backend 4000

Usage:
    # Run on a single instance by ID
    python run_evaluation.py --instance-id django__django-11099

    # Run on first N instances from the test set
    python run_evaluation.py --num-instances 5

    # Run on all instances (300 total)
    python run_evaluation.py --all

    # List available instances
    python run_evaluation.py --list
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from datasets import load_dataset

from repo_manager import RepoManager
from yaaaf_runner import YaaafRunner

_logger = logging.getLogger(__name__)


def load_swe_bench_lite(split: str = "test"):
    """Load the SWE-bench Lite dataset.

    Args:
        split: Dataset split ("dev" or "test")

    Returns:
        Dataset object
    """
    _logger.info(f"Loading SWE-bench Lite ({split} split)...")
    dataset = load_dataset("SWE-bench/SWE-bench_Lite", split=split)
    _logger.info(f"Loaded {len(dataset)} instances")
    return dataset


def get_instance_by_id(dataset, instance_id: str) -> dict | None:
    """Find an instance by its ID.

    Args:
        dataset: SWE-bench dataset
        instance_id: Instance ID to find

    Returns:
        Instance dict or None
    """
    for instance in dataset:
        if instance["instance_id"] == instance_id:
            return instance
    return None


def list_instances(dataset):
    """Print all instance IDs grouped by repo."""
    repos = {}
    for instance in dataset:
        repo = instance["repo"]
        if repo not in repos:
            repos[repo] = []
        repos[repo].append(instance["instance_id"])

    print(f"\nSWE-bench Lite: {len(dataset)} instances from {len(repos)} repos\n")
    for repo, instances in sorted(repos.items()):
        print(f"{repo} ({len(instances)} instances):")
        for inst_id in instances[:5]:
            print(f"  - {inst_id}")
        if len(instances) > 5:
            print(f"  ... and {len(instances) - 5} more")
        print()


def evaluate_instance(
    instance: dict,
    repo_manager: RepoManager,
    yaaaf_runner: YaaafRunner,
    output_dir: Path,
) -> dict:
    """Evaluate YAAAF on a single SWE-bench instance.

    Args:
        instance: SWE-bench instance dict
        repo_manager: RepoManager for handling repos
        yaaaf_runner: YaaafRunner for running YAAAF
        output_dir: Directory to save results

    Returns:
        Evaluation result dict
    """
    instance_id = instance["instance_id"]
    repo = instance["repo"]
    base_commit = instance["base_commit"]
    problem_statement = instance["problem_statement"]
    hints = instance.get("hints_text", "")
    gold_patch = instance["patch"]
    fail_to_pass = json.loads(instance["FAIL_TO_PASS"])
    pass_to_pass = json.loads(instance["PASS_TO_PASS"])

    _logger.info(f"\n{'='*60}")
    _logger.info(f"Evaluating: {instance_id}")
    _logger.info(f"Repository: {repo}")
    _logger.info(f"Base commit: {base_commit}")
    _logger.info(f"Tests to fix: {len(fail_to_pass)}")
    _logger.info(f"{'='*60}")

    result = {
        "instance_id": instance_id,
        "repo": repo,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
    }

    try:
        # Step 1: Clone/setup repository
        _logger.info("Step 1: Setting up repository...")
        repo_path = repo_manager.clone_repo(repo)
        repo_manager.checkout_commit(repo, base_commit)
        repo_manager.reset_repo(repo)  # Clean state

        # Step 2: Setup Python environment
        _logger.info("Step 2: Setting up Python environment...")
        repo_manager.setup_environment(repo)

        # Step 3: Verify initial test state (tests should fail)
        _logger.info("Step 3: Verifying initial test state...")
        initial_test_result = repo_manager.run_tests(repo, fail_to_pass[:3])  # Sample
        result["initial_tests"] = initial_test_result

        # Step 4: Run YAAAF
        _logger.info("Step 4: Running YAAAF...")
        yaaaf_result = yaaaf_runner.run(
            problem_statement=problem_statement,
            repo_path=str(repo_path),
            hints=hints if hints else None,
        )
        result["yaaaf_response"] = yaaaf_result["response"]
        result["yaaaf_success"] = yaaaf_result["success"]

        # Step 5: Run tests after YAAAF's changes
        _logger.info("Step 5: Running tests after YAAAF changes...")
        final_test_result = repo_manager.run_tests(repo, fail_to_pass)
        result["final_tests"] = final_test_result

        # Step 6: Check pass_to_pass tests (regression)
        if pass_to_pass:
            _logger.info("Step 6: Checking for regressions...")
            regression_result = repo_manager.run_tests(repo, pass_to_pass[:10])  # Sample
            result["regression_tests"] = regression_result

        # Determine overall success
        resolved = final_test_result.get("success", False)
        result["resolved"] = resolved
        result["status"] = "resolved" if resolved else "failed"

        _logger.info(f"Result: {'RESOLVED' if resolved else 'FAILED'}")

    except Exception as e:
        _logger.error(f"Evaluation failed: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    # Save result
    result_file = output_dir / f"{instance_id.replace('/', '__')}.json"
    result_file.write_text(json.dumps(result, indent=2))
    _logger.info(f"Result saved to: {result_file}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run YAAAF evaluation on SWE-bench Lite"
    )
    parser.add_argument(
        "--instance-id",
        type=str,
        help="Specific instance ID to evaluate",
    )
    parser.add_argument(
        "--num-instances",
        "-n",
        type=int,
        default=1,
        help="Number of instances to evaluate (default: 1)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all instances",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available instances and exit",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["dev", "test"],
        help="Dataset split to use (default: test)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="./swe_bench_workspace",
        help="Workspace directory for repos and envs",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./evaluation_results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4000,
        help="YAAAF backend port (default: 4000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="YAAAF backend host (default: localhost)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load dataset
    dataset = load_swe_bench_lite(args.split)

    # List mode
    if args.list:
        list_instances(dataset)
        return

    # Setup output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup managers
    repo_manager = RepoManager(args.workspace)
    yaaaf_runner = YaaafRunner(host=args.host, port=args.port)

    # Check YAAAF server is running
    if not yaaaf_runner.check_server():
        print("\nError: YAAAF backend is not running.")
        print("Start it with: python -m yaaaf backend 4000")
        sys.exit(1)

    # Determine which instances to evaluate
    if args.instance_id:
        instance = get_instance_by_id(dataset, args.instance_id)
        if instance is None:
            print(f"Instance not found: {args.instance_id}")
            sys.exit(1)
        instances = [instance]
    elif args.all:
        instances = list(dataset)
    else:
        instances = list(dataset)[:args.num_instances]

    _logger.info(f"Evaluating {len(instances)} instance(s)")

    # Run evaluations
    results = []
    for instance in instances:
        result = evaluate_instance(
            instance, repo_manager, yaaaf_runner, output_dir
        )
        results.append(result)

    # Print summary
    resolved = sum(1 for r in results if r.get("resolved"))
    failed = sum(1 for r in results if r.get("status") == "failed")
    errors = sum(1 for r in results if r.get("status") == "error")

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total instances: {len(results)}")
    print(f"Resolved: {resolved} ({100*resolved/len(results):.1f}%)")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
