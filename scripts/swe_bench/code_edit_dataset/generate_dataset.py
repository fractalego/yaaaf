#!/usr/bin/env python3
"""
Generate fine-tuning dataset for CodeEditAgent from SWE-smith trajectories.

This script:
1. Loads resolved SWE-smith trajectories
2. Extracts all code_edit operations (view, str_replace, create)
3. Uses GPT-4o-mini to generate ONE instruction per trajectory (summarizing the task)
4. Generates executor_response for each operation (matching CodeEditExecutor output format)
5. Tracks file contents from view operations
6. Adds line numbers to str_replace old_str/new_str
7. Outputs CSV with trajectory_id, step_number, instruction, response, executor_response, file_content

Usage:
    export OPENAI_API_KEY=your_key
    python generate_dataset.py --num-samples 1000 --output code_edit_dataset.csv

    # For all resolved trajectories (~8k)
    python generate_dataset.py --num-samples 10000 --output code_edit_dataset.csv
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
class FileState:
    """Tracks the state of a file through the trajectory."""
    path: str
    content: str = ""
    start_line: int = 0  # 0 means whole file
    end_line: int = 0    # 0 means whole file
    last_view_content: str = ""  # Content as shown in last view


@dataclass
class TrajectoryState:
    """Tracks state through a trajectory."""
    files: dict = field(default_factory=dict)  # path -> FileState
    problem_description: str = ""


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
    prompt = f"""You are helping create training data for a code editing AI agent.

Given the following bug report/problem description, generate a clear, actionable instruction that tells the agent what needs to be fixed.

PROBLEM DESCRIPTION:
{problem_description[:2000]}

Generate a 1-3 sentence instruction that:
1. Clearly states what file(s) need to be modified
2. Describes the bug or issue that needs to be fixed
3. Gives a high-level description of what the fix should do

Examples of good instructions:
- "Fix the separability_matrix function in astropy/modeling/separable.py to correctly handle nested CompoundModels. The function currently returns incorrect results when a CompoundModel contains another CompoundModel."
- "Modify the decompress method in django/utils/compress.py to handle None values. Currently the method raises an exception when passed None instead of returning an empty result."
- "Update the QuerySet.distinct() method in django/db/models/query.py to properly handle the case when called without arguments on a model with a custom primary key."

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


def generate_executor_response(
    operation: dict,
    file_state: Optional[FileState],
) -> str:
    """Generate the executor response that would be returned after an operation.

    This simulates the actual CodeEditExecutor responses.

    Args:
        operation: The code_edit operation that was performed
        file_state: Current state of the file (for view operations)

    Returns:
        A string mimicking the CodeEditExecutor response format
    """
    op_type = operation.get("type", "unknown")
    op_path = operation.get("path", "unknown")

    if op_type == "view":
        # Simulate view response
        if file_state and file_state.last_view_content:
            content = file_state.last_view_content
            lines = content.split('\n')
            total_lines = len(lines)

            start_line = file_state.start_line or 1
            end_line = file_state.end_line or total_lines

            result = f"File: {op_path}\n"
            result += f"Lines: {start_line}-{end_line} of {total_lines}\n"
            result += "-" * 60 + "\n"
            result += content
            return result
        else:
            # Fallback if no content available
            return f"File: {op_path}\nLines: 1-0 of 0\n" + "-" * 60

    elif op_type == "create":
        content = operation.get("content", "")
        line_count = content.count('\n') + 1 if content else 0
        size = len(content)

        result = f"Created file: {op_path}\n"
        result += f"Lines written: {line_count}\n"
        result += f"Size: {size} bytes"
        return result

    elif op_type == "str_replace":
        old_str = operation.get("old_str", "")
        new_str = operation.get("new_str", "")

        old_lines = old_str.count('\n') + 1 if old_str else 0
        new_lines = new_str.count('\n') + 1 if new_str else 0

        # Try to detect line numbers in old_str to determine line range
        first_line_match = re.match(r'\s*(\d+)\t', old_str.split('\n')[0] if old_str else "")
        if first_line_match:
            min_line = int(first_line_match.group(1))
            max_line = min_line + old_lines - 1
            result = f"Replaced lines in file: {op_path}\n"
            result += f"Replaced lines {min_line}-{max_line} ({old_lines} lines) with {new_lines} new lines"
        else:
            result = f"Replaced in file: {op_path}\n"
            result += f"Removed {old_lines} lines, Added {new_lines} lines"

        return result

    return f"Unknown operation: {op_type}"


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


def parse_tool_call(tool_call: dict) -> Optional[dict]:
    """Parse a tool call into a structured operation dict."""
    if not isinstance(tool_call, dict):
        return None

    func = tool_call.get("function", {})
    name = func.get("name", tool_call.get("name", ""))

    # Only process str_replace_editor calls
    if name != "str_replace_editor":
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
    path = args.get("path", "")

    if command == "view":
        view_range = args.get("view_range", [])
        start = view_range[0] if len(view_range) > 0 else 0
        end = view_range[1] if len(view_range) > 1 else 0
        return {
            "type": "view",
            "path": path,
            "start_line": start,
            "end_line": end,
        }
    elif command == "create":
        return {
            "type": "create",
            "path": path,
            "content": args.get("file_text", ""),
        }
    elif command == "str_replace":
        return {
            "type": "str_replace",
            "path": path,
            "old_str": args.get("old_str", ""),
            "new_str": args.get("new_str", ""),
        }

    return None


def extract_file_content_from_tool_result(result_content: str) -> tuple[str, int, int]:
    """Extract file content from a tool result.

    Returns:
        Tuple of (content_with_line_numbers, start_line, end_line)
        If whole file, start_line and end_line are 0
    """
    if not result_content:
        return "", 0, 0

    # Handle list format
    if isinstance(result_content, list):
        for item in result_content:
            if isinstance(item, dict) and item.get("type") == "text":
                result_content = item.get("text", "")
                break
        else:
            return "", 0, 0

    # Look for the cat -n output pattern
    match = re.search(
        r"Here's the result of running `cat -n` on ([^\n:]+):\r?\n(.+)",
        result_content,
        re.DOTALL
    )

    if not match:
        return "", 0, 0

    content = match.group(2).strip()

    # Parse to find line range
    lines = content.split('\n')
    if not lines:
        return content, 0, 0

    # Extract first and last line numbers
    first_match = re.match(r'\s*(\d+)\t', lines[0])
    last_match = re.match(r'\s*(\d+)\t', lines[-1])

    if first_match and last_match:
        start_line = int(first_match.group(1))
        end_line = int(last_match.group(1))
        # If starts at 1, consider it whole file
        if start_line == 1:
            return content, 0, 0
        return content, start_line, end_line

    return content, 0, 0


def add_line_numbers_to_str(text: str, start_line: int = 1) -> str:
    """Add line numbers to a string.

    Format: "     42\t    code here"
    """
    lines = text.split('\n')
    numbered = []
    for i, line in enumerate(lines, start=start_line):
        numbered.append(f"{i:6d}\t{line}")
    return '\n'.join(numbered)


def find_line_number_for_str(file_content: str, search_str: str) -> int:
    """Find the starting line number where search_str appears in file_content.

    file_content should be the numbered content from a view operation.
    """
    if not search_str or not file_content:
        return 1

    # Try to find the first line of search_str in the file content
    search_lines = search_str.strip().split('\n')
    first_search_line = search_lines[0].strip()

    if not first_search_line:
        return 1

    for line in file_content.split('\n'):
        # Parse line number from the numbered format
        match = re.match(r'\s*(\d+)\t(.*)$', line)
        if match:
            line_num = int(match.group(1))
            line_content = match.group(2)
            if first_search_line in line_content:
                return line_num

    return 1


def format_code_edit_response(
    operation: dict,
    file_content: Optional[str] = None
) -> str:
    """Format the operation as a code_edit response block.

    Args:
        operation: The parsed operation dict
        file_content: Current file content (numbered, for finding line numbers)

    Returns:
        Formatted code_edit block string
    """
    op_type = operation["type"]
    path = operation["path"]

    if op_type == "view":
        start = operation.get("start_line", 0)
        end = operation.get("end_line", 0)

        if start == 0 and end == 0:
            return f"""```code_edit
operation: view
path: {path}
```"""
        else:
            return f"""```code_edit
operation: view
path: {path}
start_line: {start}
end_line: {end}
```"""

    elif op_type == "create":
        content = operation.get("content", "")
        return f"""```code_edit
operation: create
path: {path}
content:
{content}
```"""

    elif op_type == "str_replace":
        old_str = operation.get("old_str", "")
        new_str = operation.get("new_str", "")

        # Find starting line number from file content
        if file_content and old_str:
            start_line = find_line_number_for_str(file_content, old_str)
        else:
            start_line = 1

        # Add line numbers
        old_str_numbered = add_line_numbers_to_str(old_str, start_line)
        new_str_numbered = add_line_numbers_to_str(new_str, start_line)

        return f"""```code_edit
operation: str_replace
path: {path}
old_str:
{old_str_numbered}
new_str:
{new_str_numbered}
```"""

    return ""


def process_trajectory(
    example: dict,
    trajectory_id: str,
    rate_limit_delay: float = 0.1
) -> list[dict]:
    """Process a single trajectory and extract code_edit examples.

    Returns:
        List of dicts with 'trajectory_id', 'step_number', 'instruction',
        'response', 'executor_response', 'file_content', 'start_line', 'end_line',
        'operation_type', 'file_path' keys
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

    # Generate ONE instruction for the entire trajectory
    instruction = generate_trajectory_instruction(problem_desc)
    if not instruction:
        print("Failed to generate instruction, skipping trajectory")
        return examples

    # Rate limiting after instruction generation
    time.sleep(rate_limit_delay)

    # Track state
    state = TrajectoryState(problem_description=problem_desc)

    # First pass: count total operations to estimate total_steps
    total_ops = 0
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                if parse_tool_call(tc):
                    total_ops += 1

    # Second pass: process operations
    step_number = 0
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            tool_calls = msg.get("tool_calls", [])

            for tc_idx, tool_call in enumerate(tool_calls):
                operation = parse_tool_call(tool_call)
                if not operation:
                    continue

                step_number += 1
                path = operation.get("path", "")
                op_type = operation.get("type", "")

                # Look for corresponding tool result
                result_content = ""
                result_start = 0
                result_end = 0

                # Find the tool result message
                for j in range(i + 1, min(i + 5, len(messages))):
                    result_msg = messages[j]
                    if result_msg.get("role") == "tool":
                        result_raw = result_msg.get("content", "")
                        result_content, result_start, result_end = extract_file_content_from_tool_result(result_raw)
                        break

                # Update file state from view operations
                if op_type == "view" and result_content:
                    if path not in state.files:
                        state.files[path] = FileState(path=path)
                    state.files[path].last_view_content = result_content
                    state.files[path].start_line = result_start
                    state.files[path].end_line = result_end

                # Get current file state
                file_state = state.files.get(path)

                # Format the response
                file_content_for_response = file_state.last_view_content if file_state else ""
                response = format_code_edit_response(operation, file_content_for_response)

                if not response:
                    continue

                # Generate executor response (simulating what CodeEditExecutor returns)
                executor_response = generate_executor_response(operation, file_state)

                # Determine file content and line range to include
                if file_state:
                    file_content_out = file_state.last_view_content
                    start_line_out = file_state.start_line
                    end_line_out = file_state.end_line
                else:
                    file_content_out = ""
                    start_line_out = 0
                    end_line_out = 0

                examples.append({
                    "trajectory_id": trajectory_id,
                    "step_number": step_number,
                    "instruction": instruction,  # Same instruction for all steps
                    "response": response,
                    "executor_response": executor_response,
                    "file_content": file_content_out,
                    "start_line": start_line_out,
                    "end_line": end_line_out,
                    "operation_type": op_type,
                    "file_path": path,
                })

                # Update file state after str_replace
                if op_type == "str_replace" and file_state:
                    old_str = operation.get("old_str", "")
                    new_str = operation.get("new_str", "")
                    if old_str and file_state.last_view_content:
                        file_state.last_view_content = file_state.last_view_content.replace(
                            old_str, new_str, 1
                        )

        i += 1

    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Generate fine-tuning dataset for CodeEditAgent"
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
        default="code_edit_dataset.csv",
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
    parser.add_argument(
        "--skip-instruction-generation",
        action="store_true",
        help="Skip GPT-4o-mini instruction generation (use simple template instead)",
    )

    args = parser.parse_args()

    # Initialize OpenAI (unless skipping)
    if not args.skip_instruction_generation:
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

    for example in resolved_examples[:args.num_samples]:
        processed += 1
        # Use instance_id as trajectory_id, or generate one
        trajectory_id = example.get("instance_id", f"traj_{processed}")

        print(f"Processing trajectory {processed}/{min(args.num_samples, len(resolved_examples))} ({trajectory_id})... ", end="", flush=True)

        examples = process_trajectory(example, trajectory_id, args.rate_limit_delay)
        all_examples.extend(examples)

        print(f"extracted {len(examples)} steps")

        if processed % 10 == 0:
            print(f"  Total steps so far: {len(all_examples)}")

    print(f"\nTotal examples extracted: {len(all_examples)}")

    # Count by operation type
    op_counts = {}
    for ex in all_examples:
        op = ex.get("operation_type", "unknown")
        op_counts[op] = op_counts.get(op, 0) + 1

    print("By operation type:")
    for op, count in sorted(op_counts.items()):
        print(f"  - {op}: {count}")

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
                "file_content",
                "start_line",
                "end_line",
                "operation_type",
                "file_path"
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
