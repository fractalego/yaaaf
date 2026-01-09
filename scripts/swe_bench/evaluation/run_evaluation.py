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
    max_attempts: int = 5,
) -> dict:
    """Evaluate YAAAF on a single SWE-bench instance with multi-turn feedback.

    Args:
        instance: SWE-bench instance dict
        repo_manager: RepoManager for handling repos
        yaaaf_runner: YaaafRunner for running YAAAF
        output_dir: Directory to save results
        max_attempts: Maximum number of attempts (default: 5)

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
    _logger.info(f"Max attempts: {max_attempts}")
    _logger.info(f"{'='*60}")

    result = {
        "instance_id": instance_id,
        "repo": repo,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "attempts": [],
    }

    try:
        # Step 1: Clone/setup repository
        _logger.info("Step 1: Setting up repository...")
        repo_path = repo_manager.clone_repo(repo)
        repo_manager.checkout_commit(repo, base_commit)
        repo_manager.reset_repo(repo)  # Clean state

        # Step 2: Setup Python environment (force clean every time)
        _logger.info("Step 2: Setting up Python environment (clean rebuild)...")
        repo_manager.setup_environment(repo, force=True)

        # Step 3: Verify initial test state (tests should fail)
        _logger.info("Step 3: Verifying initial test state...")
        _logger.info(f"  FAIL_TO_PASS tests ({len(fail_to_pass)} total):")
        for test in fail_to_pass[:3]:
            _logger.info(f"    - {test}")
        if len(fail_to_pass) > 3:
            _logger.info(f"    ... and {len(fail_to_pass) - 3} more")
        initial_test_result = repo_manager.run_tests(repo, fail_to_pass[:3])  # Sample
        _logger.info(f"  Initial test result: passed={initial_test_result['passed']}, "
                     f"failed={initial_test_result['failed']}, errors={initial_test_result['errors']}")
        result["initial_tests"] = initial_test_result

        # Step 4: Multi-turn dialogue with YAAAF
        env_path = repo_manager.get_env_path(repo)
        resolved = False

        for attempt in range(1, max_attempts + 1):
            _logger.info(f"\n{'='*40}")
            _logger.info(f"ATTEMPT {attempt}/{max_attempts}")
            _logger.info(f"{'='*40}")

            attempt_result = {
                "attempt": attempt,
                "timestamp": datetime.now().isoformat(),
            }

            if attempt == 1:
                # First attempt: send initial prompt
                _logger.info("Step 4: Running YAAAF (initial attempt)...")
                yaaaf_result = yaaaf_runner.run(
                    problem_statement=problem_statement,
                    repo_path=str(repo_path),
                    hints=hints if hints else None,
                    env_path=str(env_path),
                    fail_to_pass=fail_to_pass,
                    pass_to_pass=pass_to_pass,
                )
            else:
                # Subsequent attempts: send feedback
                _logger.info(f"Step 4.{attempt}: Continuing with feedback...")
                yaaaf_result = yaaaf_runner.continue_with_feedback(feedback_message)

            attempt_result["yaaaf_response"] = yaaaf_result["response"]
            attempt_result["yaaaf_success"] = yaaaf_result["success"]

            # Step 5: Run FAIL_TO_PASS tests
            _logger.info(f"Step 5.{attempt}: Running FAIL_TO_PASS tests...")
            test_result = repo_manager.run_tests(repo, fail_to_pass)
            _logger.info(f"  Test result: passed={test_result['passed']}, "
                         f"failed={test_result['failed']}, errors={test_result['errors']}")
            attempt_result["fail_to_pass_tests"] = test_result

            # Step 6: Check for regressions
            regression_result = None
            if pass_to_pass:
                _logger.info(f"Step 6.{attempt}: Checking for regressions...")
                regression_result = repo_manager.run_tests(repo, pass_to_pass[:10])
                _logger.info(f"  Regression result: passed={regression_result['passed']}, "
                             f"failed={regression_result['failed']}, errors={regression_result['errors']}")
                attempt_result["regression_tests"] = regression_result

            result["attempts"].append(attempt_result)

            # Check if resolved (FAIL_TO_PASS tests pass AND no regressions)
            fail_to_pass_success = test_result.get("success", False)
            regression_success = regression_result.get("success", True) if regression_result else True

            if fail_to_pass_success and regression_success:
                _logger.info(f"✅ RESOLVED on attempt {attempt}!")
                resolved = True
                break
            else:
                if attempt < max_attempts:
                    # Build feedback message for next attempt
                    # Combine FAIL_TO_PASS and regression test outputs
                    combined_output = test_result.get("output", "")
                    if regression_result and not regression_success:
                        combined_output += "\n\n### Regression Test Failures:\n"
                        combined_output += regression_result.get("output", "")

                    feedback_message = yaaaf_runner.build_feedback_message(
                        test_output=combined_output,
                        test_passed=test_result.get("passed", 0),
                        test_failed=test_result.get("failed", 0),
                        test_errors=test_result.get("errors", 0),
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )
                    _logger.info(f"Preparing feedback for attempt {attempt + 1}...")
                else:
                    _logger.info(f"❌ FAILED after {max_attempts} attempts")

        # Final results
        result["final_tests"] = result["attempts"][-1]["fail_to_pass_tests"] if result["attempts"] else None
        if result["attempts"] and "regression_tests" in result["attempts"][-1]:
            result["regression_tests"] = result["attempts"][-1]["regression_tests"]
        result["resolved"] = resolved
        result["status"] = "resolved" if resolved else "failed"
        result["total_attempts"] = len(result["attempts"])

        # Also store the last YAAAF response for backward compatibility
        if result["attempts"]:
            result["yaaaf_response"] = result["attempts"][-1]["yaaaf_response"]
            result["yaaaf_success"] = result["attempts"][-1]["yaaaf_success"]

        _logger.info(f"\nFinal Result: {'RESOLVED' if resolved else 'FAILED'} (attempts: {len(result['attempts'])})")

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
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Maximum number of feedback attempts per instance (default: 5)",
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
            instance, repo_manager, yaaaf_runner, output_dir,
            max_attempts=args.max_attempts,
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
