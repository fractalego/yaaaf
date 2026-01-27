#!/usr/bin/env python3
"""
Generate unified fine-tuning dataset for CodeEditAgent (with bash support) from SWE-smith trajectories.

This script:
1. Loads resolved SWE-smith trajectories
2. Extracts ALL operations in chronological order:
   - code_edit operations (view, str_replace, create)
   - bash operations (command execution)
3. Uses GPT-4o-mini to generate ONE instruction per trajectory (summarizing the task)
4. Generates executor_response for each operation
5. Outputs unified CSV with all operation types using ```code_edit format

Usage:
    export OPENAI_API_KEY=your_key
    python generate_unified_dataset.py --num-samples 1000 --output unified_code_edit_dataset.csv

    # For all resolved trajectories (~8k)
    python generate_unified_dataset.py --num-samples 10000 --output unified_code_edit_dataset.csv
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
    prompt = f"""You are helping create training data for a unified code editing AI agent that can both edit code AND run bash commands.

Given the following bug report/problem description, generate a clear, actionable instruction that tells the agent what needs to be investigated, debugged, and fixed.

PROBLEM DESCRIPTION:
{problem_description[:2000]}

Generate a 1-3 sentence instruction that:
1. Describes what needs to be investigated or fixed
2. Mentions the files/modules involved if clear
3. Gives context about the bug or issue

Examples of good instructions:
- "Investigate and fix the MoneyField validation error in django-money forms/widgets.py. The decompress method should handle disabled fields correctly without failing validation."
- "Debug the separability_matrix function in astropy/modeling/separable.py to correctly handle nested CompoundModels. Find the bug, understand the expected behavior, and apply the fix."
- "Fix the QuerySet.distinct() issue in django/db/models/query.py. The method should properly handle being called without arguments on models with custom primary keys."

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


def parse_tool_call(tool_call: dict) -> Optional[dict]:
    """Parse a tool call into a structured operation dict.

    Handles both bash and str_replace_editor tool calls.

    Returns:
        Dict with 'operation_type' key and operation-specific data, or None
    """
    if not isinstance(tool_call, dict):
        return None

    func = tool_call.get("function", {})
    name = func.get("name", tool_call.get("name", ""))

    # Parse bash tool calls
    if name == "bash":
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
            "operation_type": "bash",
            "command": command,
        }

    # Parse str_replace_editor tool calls
    elif name == "str_replace_editor":
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
                "operation_type": "view",
                "path": path,
                "start_line": start,
                "end_line": end,
            }
        elif command == "create":
            return {
                "operation_type": "create",
                "path": path,
                "content": args.get("file_text", ""),
            }
        elif command == "str_replace":
            return {
                "operation_type": "str_replace",
                "path": path,
                "old_str": args.get("old_str", ""),
                "new_str": args.get("new_str", ""),
            }

    return None


def extract_file_content_from_tool_result(result_content) -> tuple[str, int, int]:
    """Extract file content and line range from a tool result.

    Returns:
        Tuple of (content, start_line, end_line)
    """
    content = ""
    start_line = 0
    end_line = 0

    # Handle list format
    if isinstance(result_content, list):
        for item in result_content:
            if isinstance(item, dict) and item.get("type") == "text":
                result_content = item.get("text", "")
                break
        else:
            return ("", 0, 0)

    if not isinstance(result_content, str):
        return ("", 0, 0)

    # Extract numbered file content
    # Format: "File: path\nLines: X-Y of Z\n----\n  1\tline content..."
    lines_match = re.search(r"Lines:\s*(\d+)-(\d+)", result_content)
    if lines_match:
        start_line = int(lines_match.group(1))
        end_line = int(lines_match.group(2))

    # Extract content after the separator line
    separator_idx = result_content.find("---")
    if separator_idx != -1:
        content = result_content[separator_idx + 3:].lstrip("\n")
    else:
        content = result_content

    return (content, start_line, end_line)


def extract_bash_output_from_tool_result(result_content) -> str:
    """Extract bash command output from a tool result."""
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


def add_line_numbers_to_str(text: str, start_line: int = 1) -> str:
    """Add line numbers to a string."""
    if not text:
        return text

    lines = text.split('\n')
    numbered_lines = []
    for i, line in enumerate(lines):
        line_num = start_line + i
        # Format: "    42\t    code content"
        numbered_lines.append(f"    {line_num:>2}\t{line}")

    return '\n'.join(numbered_lines)


def find_line_number_for_str(file_content: str, search_str: str) -> int:
    """Find the starting line number for a string in file content."""
    if not file_content or not search_str:
        return 1

    # Remove line numbers from search_str if present
    search_lines = search_str.split('\n')
    clean_search = '\n'.join([line.split('\t', 1)[-1] if '\t' in line else line
                              for line in search_lines])

    # Find in file content
    file_lines = file_content.split('\n')
    for i, line in enumerate(file_lines):
        # Extract actual code (after line number)
        if '\t' in line:
            code = line.split('\t', 1)[1]
        else:
            code = line

        if clean_search.strip().startswith(code.strip()):
            # Try to extract line number from the numbered format
            line_num_match = re.match(r'\s*(\d+)\t', line)
            if line_num_match:
                return int(line_num_match.group(1))
            return i + 1

    return 1


def format_unified_response(operation: dict, file_content: Optional[str] = None) -> str:
    """Format the operation as a unified ```code_edit response block.

    Args:
        operation: The parsed operation dict
        file_content: Current file content (numbered, for finding line numbers)

    Returns:
        Formatted code_edit block string
    """
    op_type = operation["operation_type"]

    if op_type == "bash":
        command = operation.get("command", "")
        return f"""```code_edit
operation: bash
command: {command}
```"""

    elif op_type == "view":
        path = operation.get("path", "")
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
        path = operation.get("path", "")
        content = operation.get("content", "")
        return f"""```code_edit
operation: create
path: {path}
content:
{content}
```"""

    elif op_type == "str_replace":
        path = operation.get("path", "")
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


def generate_code_edit_executor_response(
    operation: dict,
    file_state: Optional[FileState],
) -> str:
    """Generate executor response for code_edit operations (view, create, str_replace)."""
    op_type = operation.get("operation_type", "unknown")
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


def generate_bash_executor_response(command: str, output: str, return_code: int = 0) -> str:
    """Generate executor response for bash operations."""
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
    """Process a single trajectory and extract ALL operations (bash + code_edit).

    Returns:
        List of dicts with unified CSV columns
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

    # Process all operations in chronological order
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
                op_type = operation.get("operation_type", "")

                # Find corresponding tool result
                result_content_raw = ""
                for j in range(i + 1, min(i + 10, len(messages))):
                    result_msg = messages[j]
                    if result_msg.get("role") == "tool":
                        result_content_raw = result_msg.get("content", "")
                        break

                # Handle based on operation type
                if op_type == "bash":
                    command = operation.get("command", "")

                    # Extract bash output
                    output = extract_bash_output_from_tool_result(result_content_raw)

                    # Detect return code from output
                    return_code = 0
                    if "error" in output.lower() or "failed" in output.lower():
                        return_code = 1

                    # Format response
                    response = format_unified_response(operation)

                    # Generate executor response
                    executor_response = generate_bash_executor_response(command, output, return_code)

                    examples.append({
                        "trajectory_id": trajectory_id,
                        "step_number": step_number,
                        "instruction": instruction,
                        "response": response,
                        "executor_response": executor_response,
                        "operation_type": "bash",
                        "file_path": "",  # Empty for bash
                        "command": command,
                        "file_content": "",  # Empty for bash
                        "start_line": 0,  # Empty for bash
                        "end_line": 0,  # Empty for bash
                    })

                else:  # code_edit operations (view, create, str_replace)
                    path = operation.get("path", "")

                    # Extract file content from result
                    result_content, result_start, result_end = extract_file_content_from_tool_result(result_content_raw)

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
                    response = format_unified_response(operation, file_content_for_response)

                    if not response:
                        continue

                    # Generate executor response
                    executor_response = generate_code_edit_executor_response(operation, file_state)

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
                        "instruction": instruction,
                        "response": response,
                        "executor_response": executor_response,
                        "operation_type": op_type,
                        "file_path": path,
                        "command": "",  # Empty for code_edit
                        "file_content": file_content_out,
                        "start_line": start_line_out,
                        "end_line": end_line_out,
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
        description="Generate unified fine-tuning dataset for CodeEditAgent with bash support"
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
        default="unified_code_edit_dataset.csv",
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
    init_openai()

    # Load SWE-smith dataset
    print(f"Loading SWE-smith dataset (split: {args.split})...")
    # Load more than needed to filter for resolved trajectories
    max_to_fetch = args.num_samples * 3
    dataset = load_dataset(
        "SWE-bench/SWE-smith-trajectories",
        split=f"{args.split}[:{max_to_fetch}]",
    )

    # Filter to resolved trajectories
    print("Filtering to resolved trajectories...")
    resolved = [ex for ex in dataset if ex.get("resolved", False)]
    print(f"Found {len(resolved)} resolved trajectories")

    # Limit number of samples
    num_samples = min(args.num_samples, len(resolved))
    print(f"Processing {num_samples} trajectories...")

    # Process trajectories
    all_examples = []
    for idx, example in enumerate(resolved[:num_samples]):
        if idx % 10 == 0:
            print(f"Processing trajectory {idx + 1}/{num_samples}...")

        trajectory_id = example.get("instance_id", f"traj_{idx}")
        examples = process_trajectory(example, trajectory_id, args.rate_limit_delay)

        all_examples.extend(examples)

        if idx % 10 == 0:
            print(f"  Total examples so far: {len(all_examples)}")

    # Write to CSV
    print(f"\nWriting {len(all_examples)} examples to {args.output}...")
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        if all_examples:
            fieldnames = [
                "trajectory_id",
                "step_number",
                "instruction",
                "response",
                "executor_response",
                "operation_type",
                "file_path",
                "command",
                "file_content",
                "start_line",
                "end_line",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_examples)

    # Print statistics
    print("\n=== Dataset Statistics ===")
    print(f"Total examples: {len(all_examples)}")

    if all_examples:
        op_types = {}
        for ex in all_examples:
            op_type = ex["operation_type"]
            op_types[op_type] = op_types.get(op_type, 0) + 1

        print("\nExamples by operation type:")
        for op_type, count in sorted(op_types.items()):
            print(f"  {op_type}: {count}")

    print(f"\nDataset saved to: {args.output}")


if __name__ == "__main__":
    main()
