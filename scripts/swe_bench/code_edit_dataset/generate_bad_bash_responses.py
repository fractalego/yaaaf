#!/usr/bin/env python3
"""
Generate "bad" bash responses from qwen2.5:32b for DPO training.

This script:
1. Loads the bash_dataset.csv (with good responses)
2. Groups rows by trajectory_id to process as conversations
3. For each step, builds the conversation history using GOOD responses up to that point
4. Calls qwen2.5:32b via Ollama to generate the "bad" response for that step
5. Saves to CSV with bad_response column

Usage:
    python generate_bad_bash_responses.py --input bash_dataset.csv --output bash_bad_responses.csv

    # Limit samples for testing
    python generate_bad_bash_responses.py --input bash_dataset.csv --output bad.csv --num-samples 10
"""

import argparse
import csv
import time
from collections import defaultdict
from typing import Optional

import httpx


# BashAgent system prompt (from yaaaf/components/agents/prompts.py)
SYSTEM_PROMPT = """
Your task is to create bash commands for filesystem operations based on the user's instructions.

CURRENT WORKING DIRECTORY: /testbed

You can help with:
- Listing directory contents (ls, find)
- Reading file contents (cat, head, tail, less)
- Writing content to files (echo, tee)
- Creating directories (mkdir)
- Moving or copying files (mv, cp)
- Searching file contents (grep, find)
- Checking file permissions and details (ls -l, stat)
- Basic file operations (touch, rm for single files)
- Running Python scripts and tests (python, pytest)

IMPORTANT SAFETY RULES:
1. Never suggest commands that could damage the system (rm -rf, sudo, etc.)
2. Always prioritize read operations over write operations
3. For write operations, be very specific about the target files
4. Avoid commands that modify system files or install software

CRITICAL - COMMAND FORMAT RULES:
1. Each command runs in a fresh shell at the WORKING DIRECTORY shown above
2. NEVER use just "cd dir" alone - it does nothing useful
3. Use paths relative to the working directory, or absolute paths
4. If you need to run in a subdirectory, use: cd subdir && command

When you need to execute a command, output it in this format:
```bash
YOUR_COMMAND_HERE
```

After the command is executed, you'll receive the results and can:
- Provide additional commands if needed
- Interpret the results for the user
- Complete the task using <taskcompleted/>

Think step-by-step about the filesystem operation needed and provide clear, safe commands.
"""


def call_ollama(
    prompt: str,
    system_prompt: str,
    model: str = "qwen2.5:32b",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> Optional[str]:
    """Call Ollama API to generate a response.

    Args:
        prompt: The user prompt
        system_prompt: The system prompt
        model: Model name
        host: Ollama host URL
        timeout: Request timeout in seconds

    Returns:
        Generated response or None on error
    """
    url = f"{host}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,  # Some randomness for variety
            "num_predict": 1024,  # Max tokens (bash commands are shorter)
        }
    }

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except httpx.TimeoutException:
        print("Timeout calling Ollama")
        return None
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


def assemble_conversation_prompt(
    instruction: str,
    conversation_history: list[dict],
) -> str:
    """Assemble the full conversation prompt including history.

    Args:
        instruction: The task instruction (same for all steps in trajectory)
        conversation_history: List of previous steps, each with 'response' and 'executor_response'

    Returns:
        Assembled prompt with full conversation history
    """
    parts = []

    # Initial task
    parts.append(f"TASK: {instruction}")

    # Add conversation history (good responses + executor responses)
    for i, step in enumerate(conversation_history, 1):
        parts.append("")
        parts.append(f"--- Step {i} ---")
        parts.append("")
        parts.append("COMMAND:")
        parts.append(step.get("response", ""))
        parts.append("")
        parts.append("OUTPUT:")
        parts.append(step.get("executor_response", ""))

    # Prompt for next response
    if conversation_history:
        parts.append("")
        parts.append(f"--- Step {len(conversation_history) + 1} ---")
        parts.append("")
        parts.append("Based on the previous outputs, provide your next bash command:")
    else:
        parts.append("")
        parts.append("Provide your first bash command to start investigating:")

    return "\n".join(parts)


def process_step(
    row: dict,
    conversation_history: list[dict],
    model: str,
    host: str,
    timeout: float
) -> Optional[dict]:
    """Process a single step and generate bad response using conversation history.

    Args:
        row: Current row from the CSV
        conversation_history: List of previous steps with 'response' and 'executor_response'
        model: Ollama model name
        host: Ollama host URL
        timeout: Request timeout

    Returns:
        New row with bad_response or None on error
    """
    instruction = row.get("instruction", "")

    # Assemble prompt with full conversation history
    user_prompt = assemble_conversation_prompt(
        instruction=instruction,
        conversation_history=conversation_history,
    )

    # Call Ollama
    bad_response = call_ollama(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        model=model,
        host=host,
        timeout=timeout,
    )

    if bad_response is None:
        return None

    # Return row with bad_response
    return {
        "trajectory_id": row.get("trajectory_id", ""),
        "step_number": row.get("step_number", 0),
        "instruction": instruction,
        "bad_response": bad_response,
        "command": row.get("command", ""),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate bad bash responses from qwen2.5:32b for DPO training"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input CSV file (bash_dataset.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="bash_bad_responses.csv",
        help="Output CSV file",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="qwen2.5:32b",
        help="Ollama model to use (default: qwen2.5:32b)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:11434",
        help="Ollama host URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--num-samples",
        "-n",
        type=int,
        default=None,
        help="Max number of trajectories to process (default: all)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if output file exists and append new rows",
    )

    args = parser.parse_args()

    # Check Ollama is running
    print(f"Checking Ollama at {args.host}...")
    try:
        response = httpx.get(f"{args.host}/api/tags", timeout=5.0)
        response.raise_for_status()
        models = [m["name"] for m in response.json().get("models", [])]
        if args.model not in models and not any(args.model in m for m in models):
            print(f"Warning: Model '{args.model}' may not be available. Available: {models}")
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        return

    # Load input CSV
    print(f"Loading {args.input}...")
    rows = []
    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows")

    # Group rows by trajectory_id
    trajectories = defaultdict(list)
    for row in rows:
        traj_id = row.get("trajectory_id", "unknown")
        trajectories[traj_id].append(row)

    # Sort each trajectory by step_number
    for traj_id in trajectories:
        trajectories[traj_id].sort(key=lambda x: int(x.get("step_number", 0)))

    print(f"Found {len(trajectories)} unique trajectories")

    # Limit trajectories if requested
    trajectory_ids = list(trajectories.keys())
    if args.num_samples:
        trajectory_ids = trajectory_ids[:args.num_samples]
        print(f"Processing {len(trajectory_ids)} trajectories")

    # Load existing results if skip_existing
    existing_keys = set()
    if args.skip_existing:
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = f"{row.get('trajectory_id', '')}_{row.get('step_number', '')}"
                    existing_keys.add(key)
            print(f"Found {len(existing_keys)} existing results to skip")
        except FileNotFoundError:
            pass

    # Process trajectories
    results = []
    processed_steps = 0
    processed_trajectories = 0
    errors = 0

    for traj_idx, traj_id in enumerate(trajectory_ids):
        traj_steps = trajectories[traj_id]
        processed_trajectories += 1

        print(f"\nTrajectory {processed_trajectories}/{len(trajectory_ids)}: {traj_id} ({len(traj_steps)} steps)")

        # Build conversation history as we process each step
        conversation_history = []

        for step_idx, row in enumerate(traj_steps):
            step_num = row.get("step_number", step_idx + 1)

            # Check if already processed
            key = f"{traj_id}_{step_num}"
            if key in existing_keys:
                # Still need to add to conversation history for subsequent steps
                conversation_history.append({
                    "response": row.get("response", ""),
                    "executor_response": row.get("executor_response", ""),
                })
                continue

            processed_steps += 1
            print(f"  Step {step_num}... ", end="", flush=True)

            # Process this step with conversation history
            result = process_step(
                row=row,
                conversation_history=conversation_history,
                model=args.model,
                host=args.host,
                timeout=args.timeout,
            )

            if result:
                results.append(result)
                print(f"OK ({len(result.get('bad_response', ''))} chars)")
            else:
                errors += 1
                print("ERROR")

            # Add this step's GOOD response to conversation history for next step
            conversation_history.append({
                "response": row.get("response", ""),
                "executor_response": row.get("executor_response", ""),
            })

            # Delay between requests
            time.sleep(args.delay)

        # Save periodically (after each trajectory)
        if len(results) >= 50 and len(results) % 50 < len(traj_steps):
            print(f"  Saving checkpoint ({len(results)} results)...")
            save_results(args.output, results, append=args.skip_existing)
            results = []  # Clear after saving to avoid duplicates

    # Final save
    if results:
        save_results(args.output, results, append=args.skip_existing)

    print(f"\nDone!")
    print(f"  Trajectories processed: {processed_trajectories}")
    print(f"  Steps processed: {processed_steps}")
    print(f"  Successful: {processed_steps - errors}")
    print(f"  Errors: {errors}")
    print(f"  Output: {args.output}")


def save_results(output_path: str, results: list[dict], append: bool = False):
    """Save results to CSV.

    Args:
        output_path: Output file path
        results: List of result dicts
        append: If True, append to existing file
    """
    mode = "a" if append else "w"
    write_header = not append

    # Check if file exists for append mode
    if append:
        try:
            with open(output_path, "r") as f:
                pass
        except FileNotFoundError:
            write_header = True

    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "trajectory_id",
                "step_number",
                "instruction",
                "bad_response",
                "command",
            ],
            quoting=csv.QUOTE_ALL,
        )

        if write_header:
            writer.writeheader()

        writer.writerows(results)


if __name__ == "__main__":
    main()
