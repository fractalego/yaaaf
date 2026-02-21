#!/usr/bin/env python3
"""
Generate fine-tuning dataset for BashAgent from SWE-smith trajectories.

This script:
1. Loads resolved SWE-smith trajectories
2. Extracts all bash tool calls
3. Uses GPT-4o-mini to generate ONE instruction per trajectory (summarizing the task)
4. Generates executor_response for each command (matching BashExecutor output format)
5. Outputs CSV with trajectory_id, step_number, instruction, response, executor_response

Usage:
    export OPENAI_API_KEY=your_key
    python generate_bash_dataset.py --num-samples 1000 --output bash_dataset.csv

    # For all resolved trajectories (~8k)
    python generate_bash_dataset.py --num-samples 10000 --output bash_dataset.csv
"""

import argparse
import csv
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from datasets import load_dataset
from openai import OpenAI


# Initialize OpenAI client
client = None


@dataclass
class BashState:
    """Tracks state through a bash trajectory."""
    problem_description: str = ""
    working_dir: str = "/testbed"


def init_openai():
    """Initialize OpenAI client."""
    global client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    client = OpenAI(api_key=api_key)


def generate_trajectory_instruction(problem_description: str) -> Optional[str]:
    """Use GPT-4o-mini to generate ONE instruction for the entire trajectory.

    Args:
        problem_description: The original problem/bug description from the issue

    Returns:
        A clear instruction string summarizing the overall task
    """
    prompt = f"""You are helping create training data for a bash command AI agent that helps with debugging and fixing code.

Given the following bug report/problem description, generate a clear, actionable instruction that tells the agent what needs to be investigated and fixed.

PROBLEM DESCRIPTION:
{problem_description[:2000]}

Generate a 1-3 sentence instruction that:
1. Describes what needs to be investigated or debugged
2. Mentions what kind of exploration might be needed (finding files, searching code, running tests)
3. Gives context about the bug or issue

Examples of good instructions:
- "Investigate the MoneyField validation error in django-money. Find where MoneyField is defined, understand how validation works, and create a reproduction script to verify the bug."
- "Debug the CSV translation loading issue in Tornado. Locate the translation files, check how they're loaded, and run the failing tests to understand the problem."
- "Explore the test failures in the astropy separability module. Find the relevant test files, run the failing tests, and identify what's causing the incorrect matrix computation."

Generate only the instruction text, nothing else:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error generating instruction: {e}")
        return None


def extract_problem_description(messages: list) -> str:
    """Extract problem description from trajectory messages."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        # Extract PR description
                        pr_match = re.search(
                            r"<pr_description>(.*?)</pr_description>",
                            text,
                            re.DOTALL
                        )
                        if pr_match:
                            return pr_match.group(1).strip()
                        return text[:1500].strip()
            elif isinstance(content, str):
                return content[:1500].strip()
    return ""


def parse_bash_tool_call(tool_call: dict) -> Optional[dict]:
    """Parse a bash tool call into a structured dict."""
    if not isinstance(tool_call, dict):
        return None

    func = tool_call.get("function", {})
    name = func.get("name", tool_call.get("name", ""))

    # Only process bash calls
    if name != "bash":
        return None

    args_raw = func.get("arguments", "{}")
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            return None
    else:
        args = args_raw

    command = args.get("command", "")
    if not command:
        return None

    return {
        "command": command,
    }


def extract_bash_output_from_tool_result(result_content) -> str:
    """Extract bash command output from a tool result.

    Returns:
        The command output string
    """
    if not result_content:
        return ""

    # Handle list format
    if isinstance(result_content, list):
        for item in result_content:
            if isinstance(item, dict) and item.get("type") == "text":
                result_content = item.get("text", "")
                break
        else:
            return ""

    if isinstance(result_content, str):
        return result_content.strip()

    return ""


def format_bash_response(command: str) -> str:
    """Format the bash command as a response block.

    Args:
        command: The bash command

    Returns:
        Formatted bash block string
    """
    return f"""```bash
{command}
```"""


def generate_executor_response(command: str, output: str, return_code: int = 0) -> str:
    """Generate the executor response that would be returned after a bash command.

    This simulates the actual BashExecutor response format.

    Args:
        command: The bash command that was executed
        output: The command output
        return_code: The return code (0 for success)

    Returns:
        A string mimicking the BashExecutor response format
    """
    # Parse output to separate stdout and stderr if possible
    # Most tool results just have the output directly

    if not output:
        return f"STDOUT:\n\nSTDERR:\n\nReturn code: {return_code}"

    # Check if output already has STDOUT/STDERR format
    if "STDOUT:" in output or "STDERR:" in output:
        return output

    # Assume output is stdout
    result = f"STDOUT:\n{output}\n\nSTDERR:\n\nReturn code: {return_code}"
    return result


def process_trajectory(
    example: dict,
    trajectory_id: str,
    rate_limit_delay: float = 0.1
) -> list[dict]:
    """Process a single trajectory and extract bash examples.

    Returns:
        List of dicts with 'trajectory_id', 'step_number', 'instruction',
        'response', 'executor_response' keys
    """
    examples = []

    # Parse messages
    messages_raw = example.get("messages", "[]")
    try:
        if isinstance(messages_raw, str):
            messages = json.loads(messages_raw)
        else:
            messages = messages_raw
    except json.JSONDecodeError:
        return examples

    # Extract problem description
    problem_desc = extract_problem_description(messages)

    # First pass: count bash operations to see if this trajectory has any
    bash_ops = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                parsed = parse_bash_tool_call(tc)
                if parsed:
                    bash_ops.append(parsed)

    if not bash_ops:
        return examples  # No bash commands in this trajectory

    # Generate ONE instruction for the entire trajectory
    instruction = generate_trajectory_instruction(problem_desc)
    if not instruction:
        print("Failed to generate instruction, skipping trajectory")
        return examples

    # Rate limiting after instruction generation
    time.sleep(rate_limit_delay)

    # Track state
    state = BashState(problem_description=problem_desc)

    # Second pass: process bash operations with their outputs
    step_number = 0
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            tool_calls = msg.get("tool_calls", [])

            for tc_idx, tool_call in enumerate(tool_calls):
                parsed = parse_bash_tool_call(tool_call)
                if not parsed:
                    continue

                step_number += 1
                command = parsed["command"]

                # Look for corresponding tool result
                output = ""
                return_code = 0

                # Find the tool result message
                for j in range(i + 1, min(i + 10, len(messages))):
                    result_msg = messages[j]
                    if result_msg.get("role") == "tool":
                        result_raw = result_msg.get("content", "")
                        output = extract_bash_output_from_tool_result(result_raw)

                        # Try to detect return code from output
                        if "error" in output.lower() or "failed" in output.lower():
                            return_code = 1
                        break

                # Format the response (bash block)
                response = format_bash_response(command)

                # Generate executor response
                executor_response = generate_executor_response(command, output, return_code)

                examples.append({
                    "trajectory_id": trajectory_id,
                    "step_number": step_number,
                    "instruction": instruction,  # Same instruction for all steps
                    "response": response,
                    "executor_response": executor_response,
                    "command": command,  # Raw command for analysis
                })

        i += 1

    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Generate fine-tuning dataset for BashAgent"
    )
    parser.add_argument(
        "--num-samples",
        "-n",
        type=int,
        default=100,
        help="Max number of trajectories to process (default: 100)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="bash_dataset.csv",
        help="Output CSV file path",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="tool",
        help="Dataset split to use (default: tool)",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.05,
        help="Delay between OpenAI API calls in seconds (default: 0.05)",
    )

    args = parser.parse_args()

    # Initialize OpenAI
    print("Initializing OpenAI client...")
    init_openai()

    # Load dataset
    print(f"Loading SWE-smith trajectories (split: {args.split}, resolved only)...")

    # Load more than needed to filter for resolved
    max_to_fetch = args.num_samples * 3
    dataset = load_dataset(
        "SWE-bench/SWE-smith-trajectories",
        split=f"{args.split}[:{max_to_fetch}]",
    )

    # Filter for resolved
    resolved_examples = [ex for ex in dataset if ex.get("resolved")]
    print(f"Found {len(resolved_examples)} resolved trajectories")

    # Process trajectories
    all_examples = []
    processed = 0
    skipped_no_bash = 0

    for example in resolved_examples[:args.num_samples]:
        processed += 1
        # Use instance_id as trajectory_id, or generate one
        trajectory_id = example.get("instance_id", f"traj_{processed}")

        print(f"Processing trajectory {processed}/{min(args.num_samples, len(resolved_examples))} ({trajectory_id})... ", end="", flush=True)

        examples = process_trajectory(example, trajectory_id, args.rate_limit_delay)

        if examples:
            all_examples.extend(examples)
            print(f"extracted {len(examples)} bash steps")
        else:
            skipped_no_bash += 1
            print("no bash commands, skipped")

        if processed % 10 == 0:
            print(f"  Total steps so far: {len(all_examples)}")

    print(f"\nTotal examples extracted: {len(all_examples)}")
    print(f"Trajectories with bash commands: {processed - skipped_no_bash}")
    print(f"Trajectories without bash commands: {skipped_no_bash}")

    # Analyze command types
    command_types = {}
    for ex in all_examples:
        cmd = ex.get("command", "")
        first_word = cmd.strip().split()[0] if cmd.strip() else "empty"
        first_word = first_word.split("/")[-1]  # Remove path prefix
        command_types[first_word] = command_types.get(first_word, 0) + 1

    print("\nBy command type (top 15):")
    for cmd, count in sorted(command_types.items(), key=lambda x: -x[1])[:15]:
        print(f"  - {cmd}: {count}")

    # Write CSV
    print(f"\nWriting to {args.output}...")

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "trajectory_id",
                "step_number",
                "instruction",
                "response",
                "executor_response",
                "command",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(all_examples)

    # Count unique trajectories
    unique_trajectories = len(set(ex["trajectory_id"] for ex in all_examples))
    print(f"Done! Saved {len(all_examples)} steps from {unique_trajectories} trajectories to {args.output}")


if __name__ == "__main__":
    main()
