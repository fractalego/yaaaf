#!/usr/bin/env python3
"""
Generate "bad" responses from qwen2.5:32b for DPO training.

This script:
1. Loads the code_edit_dataset.csv (with good responses)
2. Groups rows by trajectory_id to process as conversations
3. For each step, builds the conversation history using GOOD responses up to that point
4. Calls qwen2.5:32b via Ollama to generate the "bad" response for that step
5. Saves to CSV with bad_response column

The key insight: each bad_response is generated in context of the good conversation
history, so step N sees: instruction + good_response_1 + executor_response_1 + ... + good_response_{N-1} + executor_response_{N-1}

Usage:
    python generate_bad_responses.py --input code_edit_dataset.csv --output code_edit_bad_responses.csv

    # Limit samples for testing
    python generate_bad_responses.py --input code_edit_dataset.csv --output bad.csv --num-samples 100
"""

import argparse
import csv
import time
from typing import Optional

import httpx


# CodeEditAgent system prompt (from yaaaf/components/agents/prompts.py)
SYSTEM_PROMPT = """
Your task is to perform code editing operations on files. You can:
1. VIEW files to read their contents with line numbers
2. CREATE new files with specified content
3. STR_REPLACE to make precise string replacements in existing files

IMPORTANT RULES:
- If the task asks you to FIX, MODIFY, CHANGE, or APPLY something, you MUST use STR_REPLACE
- VIEW alone is NOT a fix - it only reads the file
- Always VIEW a file first to understand it, then use STR_REPLACE to make changes
- For STR_REPLACE, provide enough context to uniquely identify the replacement location
- Never modify system files or files outside the project directory
- Use exact string matching - whitespace and indentation matter

FINDING THE RIGHT CODE - CRITICAL:
- ALWAYS view the ENTIRE file first (without start_line/end_line) to find where the code you need is located
- Pay attention to LINE NUMBERS in the view output - they tell you exactly where each function/class is
- If a file is very large, view it in sections, but scan to find the function you need BEFORE trying str_replace
- NEVER guess line numbers or assume where code is - always verify with view first
- The function you need to modify might be at line 50, or line 500 - you must LOOK first

WHEN TO USE EACH OPERATION:
- VIEW: When you need to read/understand code (analysis, exploration)
- CREATE: When you need to create a new file that doesn't exist
- STR_REPLACE: When you need to FIX bugs, MODIFY code, or APPLY changes

To perform an operation, output a code_edit block in this format:

For viewing a file (RECOMMENDED - view entire file first):
```code_edit
operation: view
path: /path/to/file
```

For viewing specific lines (only after you've found the right lines):
```code_edit
operation: view
path: /path/to/file
start_line: 10
end_line: 50
```

For creating a new file:
```code_edit
operation: create
path: /path/to/new_file.py
content:
def hello():
    print("Hello, World!")
```

For replacing a string (MUST INCLUDE LINE NUMBERS):
```code_edit
operation: str_replace
path: /path/to/file.py
old_str:
    42	    def buggy_function(self):
    43	        return wrong_value
new_str:
    42	    def buggy_function(self):
    43	        return correct_value
```

WHAT old_str AND new_str MEAN:
- old_str = The EXACT text from VIEW output INCLUDING LINE NUMBERS (e.g., "    42\tcode here")
- new_str = Your MODIFIED version with the SAME LINE NUMBERS and your fix applied
- The line numbers tell the system exactly which lines to replace

CRITICAL for str_replace - YOU MUST INCLUDE LINE NUMBERS:
- COPY the lines EXACTLY as shown in VIEW output, INCLUDING the line number prefix
- Each line MUST start with the line number, then a tab, then the code
- Format: "    42\t    def my_function():" (number + tab + code)
- The old_str and new_str MUST have matching line numbers
- DO NOT strip the line numbers - they are REQUIRED for the replacement to work

Example - if VIEW shows:
```
    97	    if transform.n_inputs == 1:
    98	        return np.ones((transform.n_outputs,),
    99	                       dtype=np.bool_)
```

Your str_replace MUST look like:
```code_edit
operation: str_replace
path: /path/to/file.py
old_str:
    97	    if transform.n_inputs == 1:
    98	        return np.ones((transform.n_outputs,),
    99	                       dtype=np.bool_)
new_str:
    97	    if transform.n_inputs == 1:
    98	        return np.zeros((transform.n_outputs,),
    99	                        dtype=np.bool_)
```

COMMON MISTAKES TO AVOID:
- Stripping line numbers from old_str/new_str (WRONG - keep them!)
- Viewing lines 100-150 but trying to modify a function at line 290 (you never saw it!)
- Making up what you think code looks like instead of copying from VIEW output
- Guessing indentation or formatting

Think step-by-step:
1. First VIEW the ENTIRE file (no start_line/end_line) to find where the code you need is located
2. Note the LINE NUMBERS where the function/code you need to modify actually is
3. If needed, view those specific lines to see the exact content
4. COPY the exact text from the VIEW output (don't type from memory!)
5. Use STR_REPLACE with that exact copied text as old_str

When the task is complete, include <taskcompleted/> in your response.
"""


def call_ollama(
    prompt: str,
    system_prompt: str,
    model: str = "qwen2.5:32b",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> Optional[str]:
    """Call Ollama API to generate a response with retry on timeout.

    Args:
        prompt: The user prompt
        system_prompt: The system prompt
        model: Model name
        host: Ollama host URL
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries on timeout
        retry_delay: Delay between retries in seconds

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
            "num_predict": 2048,  # Max tokens
        }
    }

    for attempt in range(max_retries):
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                print(f"Timeout (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s... ", end="", flush=True)
                time.sleep(retry_delay)
            else:
                print(f"Timeout after {max_retries} attempts")
                return None
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return None

    return None


def assemble_conversation_prompt(
    instruction: str,
    file_content: str,
    file_path: str,
    conversation_history: list[dict],
) -> str:
    """Assemble the full conversation prompt including history.

    Args:
        instruction: The task instruction (same for all steps in trajectory)
        file_content: The initial file content (with line numbers)
        file_path: Path to the file
        conversation_history: List of previous steps, each with 'response' and 'executor_response'

    Returns:
        Assembled prompt with full conversation history
    """
    parts = []

    # Initial context: file content and task
    if file_content:
        parts.append(f"FILE: {file_path}")
        parts.append("```")
        parts.append(file_content)
        parts.append("```")
        parts.append("")

    parts.append(f"TASK: {instruction}")

    # Add conversation history (good responses + executor responses)
    for i, step in enumerate(conversation_history, 1):
        parts.append("")
        parts.append(f"--- Step {i} ---")
        parts.append("")
        parts.append("ASSISTANT:")
        parts.append(step.get("response", ""))
        parts.append("")
        parts.append("RESULT:")
        parts.append(step.get("executor_response", ""))

    # Prompt for next response
    if conversation_history:
        parts.append("")
        parts.append(f"--- Step {len(conversation_history) + 1} ---")
        parts.append("")
        parts.append("Now provide your next action:")

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
    file_content = row.get("file_content", "")
    file_path = row.get("file_path", "")

    # Assemble prompt with full conversation history
    user_prompt = assemble_conversation_prompt(
        instruction=instruction,
        file_content=file_content,
        file_path=file_path,
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
        "file_content": file_content,
        "start_line": row.get("start_line", 0),
        "end_line": row.get("end_line", 0),
        "operation_type": row.get("operation_type", ""),
        "file_path": file_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate bad responses from qwen2.5:32b for DPO training"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input CSV file (code_edit_dataset.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="code_edit_bad_responses.csv",
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
        default=120.0,
        help="Request timeout in seconds (default: 120)",
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

    # Group rows by trajectory_id, preserving order from CSV
    trajectories = {}
    trajectory_order = []  # Track order of first appearance
    for row in rows:
        traj_id = row.get("trajectory_id", "unknown")
        if traj_id not in trajectories:
            trajectories[traj_id] = []
            trajectory_order.append(traj_id)
        trajectories[traj_id].append(row)

    # Sort each trajectory by step_number
    for traj_id in trajectories:
        trajectories[traj_id].sort(key=lambda x: int(x.get("step_number", 0)))

    print(f"Found {len(trajectories)} unique trajectories")

    # Use the order from the CSV file
    trajectory_ids = trajectory_order
    if args.num_samples:
        # Limit by number of trajectories, not rows
        trajectory_ids = trajectory_ids[:args.num_samples]
        print(f"Processing {len(trajectory_ids)} trajectories")

    # Handle existing output file
    existing_keys = set()
    if args.skip_existing:
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Use trajectory_id + step_number as unique key
                    key = f"{row.get('trajectory_id', '')}_{row.get('step_number', '')}"
                    existing_keys.add(key)
            print(f"Found {len(existing_keys)} existing results to skip")
        except FileNotFoundError:
            pass
    else:
        # Create fresh output file with header
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "trajectory_id",
                    "step_number",
                    "instruction",
                    "bad_response",
                    "file_content",
                    "start_line",
                    "end_line",
                    "operation_type",
                    "file_path"
                ],
                quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
        print(f"Created fresh output file: {args.output}")

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

        # Save immediately after each trajectory completes
        if results:
            save_results(args.output, results, append=True)
            print(f"  Saved {len(results)} steps to {args.output}")
            results = []  # Clear after saving

    # Reorder output file to match input CSV order
    print(f"\nReordering output to match input CSV order...")
    reorder_output_to_match_input(args.input, args.output)

    print(f"\nDone!")
    print(f"  Trajectories processed: {processed_trajectories}")
    print(f"  Steps processed: {processed_steps}")
    print(f"  Successful: {processed_steps - errors}")
    print(f"  Errors: {errors}")
    print(f"  Output: {args.output}")


def reorder_output_to_match_input(input_path: str, output_path: str):
    """Reorder the output CSV to match the order of the input CSV.

    Args:
        input_path: Path to the input (good) CSV
        output_path: Path to the output (bad) CSV to reorder
    """
    # Load input CSV to get the correct order
    input_order = {}
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            key = (row.get("trajectory_id", ""), row.get("step_number", ""))
            input_order[key] = idx

    # Load output CSV
    output_rows = []
    fieldnames = None
    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        output_rows = list(reader)

    if not output_rows:
        return

    # Sort output rows to match input order
    def sort_key(row):
        key = (row.get("trajectory_id", ""), row.get("step_number", ""))
        return input_order.get(key, 999999)

    output_rows.sort(key=sort_key)

    # Write back sorted
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"  Reordered {len(output_rows)} rows to match input order")


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
                "file_content",
                "start_line",
                "end_line",
                "operation_type",
                "file_path"
            ],
            quoting=csv.QUOTE_ALL,
        )

        if write_header:
            writer.writeheader()

        writer.writerows(results)


if __name__ == "__main__":
    main()
