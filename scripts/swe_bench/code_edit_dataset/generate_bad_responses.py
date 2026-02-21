#!/usr/bin/env python3
"""
Generate "bad" responses from a weaker model for DPO training.

This script:
1. Loads the code_edit_dataset.csv (with good responses)
2. Groups rows by trajectory_id to process as conversations
3. For each step, builds the conversation history using GOOD responses up to that point
4. Calls a weaker model (via Ollama or vLLM) to generate the "bad" response for that step
5. Saves to CSV with bad_response column

The key insight: each bad_response is generated in context of the good conversation
history, so step N sees: instruction + good_response_1 + executor_response_1 + ... + good_response_{N-1} + executor_response_{N-1}

Usage:
    # Using Ollama (default)
    python generate_bad_responses.py --input code_edit_dataset.csv --output code_edit_bad_responses.csv

    # Using vLLM with HuggingFace model
    python generate_bad_responses.py --backend vllm --model Qwen/Qwen2.5-32B --input code_edit_dataset.csv --output bad.csv

    # Batch processing (process 8 trajectories in parallel)
    python generate_bad_responses.py --backend vllm --concurrency 8 --input code_edit_dataset.csv --output bad.csv

    # Limit samples for testing
    python generate_bad_responses.py --input code_edit_dataset.csv --output bad.csv --num-samples 100

Starting vLLM server with 4-bit quantization:
    # Option 1: bitsandbytes (on-the-fly quantization)
    python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-32B --quantization bitsandbytes --load-format bitsandbytes

    # Option 2: Pre-quantized AWQ model (faster loading)
    python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-32B-Instruct-AWQ --quantization awq
"""

import argparse
import asyncio
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


async def call_ollama_async(
    client: httpx.AsyncClient,
    prompt: str,
    system_prompt: str,
    model: str = "qwen2.5:32b",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> Optional[str]:
    """Call Ollama API async with retry on timeout."""
    url = f"{host}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        }
    }

    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                return None
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return None

    return None


async def call_vllm_async(
    client: httpx.AsyncClient,
    prompt: str,
    system_prompt: str,
    model: str = "Qwen/Qwen2.5-32B",
    host: str = "http://localhost:8000",
    timeout: float = 120.0,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> Optional[str]:
    """Call vLLM OpenAI-compatible API async with retry on timeout."""
    url = f"{host}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload, timeout=httpx.Timeout(timeout))
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            print(f"      [Timeout attempt {attempt + 1}/{max_retries}]", flush=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                return None
        except httpx.ConnectError as e:
            print(f"      [Connection error: {e}]", flush=True)
            return None
        except Exception as e:
            print(f"      [Error calling vLLM: {e}]", flush=True)
            return None

    return None


async def call_llm_async(
    client: httpx.AsyncClient,
    prompt: str,
    system_prompt: str,
    backend: str = "ollama",
    model: str = "qwen2.5:32b",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> Optional[str]:
    """Call LLM API async (Ollama or vLLM)."""
    if backend == "vllm":
        return await call_vllm_async(client, prompt, system_prompt, model, host, timeout, max_retries, retry_delay)
    else:
        return await call_ollama_async(client, prompt, system_prompt, model, host, timeout, max_retries, retry_delay)


def assemble_conversation_prompt(
    instruction: str,
    file_content: str,
    file_path: str,
    conversation_history: list[dict],
) -> str:
    """Assemble the full conversation prompt including history."""
    parts = []

    if file_content:
        parts.append(f"FILE: {file_path}")
        parts.append("```")
        parts.append(file_content)
        parts.append("```")
        parts.append("")

    parts.append(f"TASK: {instruction}")

    for i, step in enumerate(conversation_history, 1):
        parts.append("")
        parts.append(f"--- Step {i} ---")
        parts.append("")
        parts.append("ASSISTANT:")
        parts.append(step.get("response", ""))
        parts.append("")
        parts.append("RESULT:")
        parts.append(step.get("executor_response", ""))

    if conversation_history:
        parts.append("")
        parts.append(f"--- Step {len(conversation_history) + 1} ---")
        parts.append("")
        parts.append("Now provide your next action:")

    return "\n".join(parts)


async def process_trajectory_async(
    client: httpx.AsyncClient,
    traj_id: str,
    traj_steps: list[dict],
    existing_keys: set,
    backend: str,
    model: str,
    host: str,
    timeout: float,
    semaphore: asyncio.Semaphore,
    verbose: bool = True,
) -> tuple[list[dict], int, int]:
    """Process a single trajectory asynchronously.

    Steps within a trajectory are processed sequentially (due to conversation history),
    but multiple trajectories can run in parallel.

    Returns:
        Tuple of (results, processed_steps, errors)
    """
    async with semaphore:
        results = []
        processed_steps = 0
        errors = 0
        conversation_history = []

        # Count how many steps need processing
        steps_to_process = sum(
            1 for row in traj_steps
            if f"{traj_id}_{row.get('step_number', 0)}" not in existing_keys
        )

        # Short trajectory ID for logging
        short_id = traj_id[:20] + "..." if len(traj_id) > 20 else traj_id

        if steps_to_process > 0 and verbose:
            print(f"  [{short_id}] Starting ({steps_to_process} steps)", flush=True)

        for step_idx, row in enumerate(traj_steps):
            step_num = row.get("step_number", step_idx + 1)
            key = f"{traj_id}_{step_num}"

            if key in existing_keys:
                conversation_history.append({
                    "response": row.get("response", ""),
                    "executor_response": row.get("executor_response", ""),
                })
                continue

            processed_steps += 1
            instruction = row.get("instruction", "")
            file_content = row.get("file_content", "")
            file_path = row.get("file_path", "")

            user_prompt = assemble_conversation_prompt(
                instruction=instruction,
                file_content=file_content,
                file_path=file_path,
                conversation_history=conversation_history,
            )

            bad_response = await call_llm_async(
                client=client,
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                backend=backend,
                model=model,
                host=host,
                timeout=timeout,
            )

            if bad_response:
                results.append({
                    "trajectory_id": traj_id,
                    "step_number": step_num,
                    "instruction": instruction,
                    "bad_response": bad_response,
                    "file_content": file_content,
                    "start_line": row.get("start_line", 0),
                    "end_line": row.get("end_line", 0),
                    "operation_type": row.get("operation_type", ""),
                    "file_path": file_path,
                })
                if verbose:
                    print(f"    [{short_id}] Step {step_num}/{steps_to_process}: OK ({len(bad_response)} chars)", flush=True)
            else:
                errors += 1
                if verbose:
                    print(f"    [{short_id}] Step {step_num}/{steps_to_process}: ERROR", flush=True)

            conversation_history.append({
                "response": row.get("response", ""),
                "executor_response": row.get("executor_response", ""),
            })

        if steps_to_process > 0 and verbose:
            print(f"  [{short_id}] Done: {processed_steps - errors}/{steps_to_process} successful", flush=True)

        return results, processed_steps, errors


async def process_batch_async(
    trajectories: dict,
    trajectory_ids: list[str],
    existing_keys: set,
    backend: str,
    model: str,
    host: str,
    timeout: float,
    concurrency: int,
    output_path: str,
) -> tuple[int, int, int]:
    """Process all trajectories with concurrent execution."""

    semaphore = asyncio.Semaphore(concurrency)
    total_processed = 0
    total_errors = 0
    total_trajectories = 0

    # Configure client with proper limits for concurrent requests
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(300.0)) as client:
        # Process in batches to allow periodic saving
        batch_size = concurrency * 2

        for batch_start in range(0, len(trajectory_ids), batch_size):
            batch_ids = trajectory_ids[batch_start:batch_start + batch_size]

            tasks = [
                process_trajectory_async(
                    client=client,
                    traj_id=traj_id,
                    traj_steps=trajectories[traj_id],
                    existing_keys=existing_keys,
                    backend=backend,
                    model=model,
                    host=host,
                    timeout=timeout,
                    semaphore=semaphore,
                )
                for traj_id in batch_ids
            ]

            # Process batch concurrently
            batch_results = await asyncio.gather(*tasks)

            # Collect results from batch
            all_results = []
            batch_steps = 0
            for results, processed, errors in batch_results:
                all_results.extend(results)
                total_processed += processed
                total_errors += errors
                total_trajectories += 1
                batch_steps += processed

            # Save batch results
            if all_results:
                save_results(output_path, all_results, append=True)

            # Progress update
            skipped_in_batch = len(batch_ids) - sum(1 for r, p, e in batch_results if p > 0)
            print(f"\n--- Batch complete: {total_trajectories}/{len(trajectory_ids)} trajectories, "
                  f"{total_processed} steps total, {total_errors} errors "
                  f"(batch: {batch_steps} steps, {skipped_in_batch} skipped) ---\n", flush=True)

    return total_trajectories, total_processed, total_errors


def save_results(output_path: str, results: list[dict], append: bool = False):
    """Save results to CSV."""
    mode = "a" if append else "w"
    write_header = not append

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


def reorder_output_to_match_input(input_path: str, output_path: str):
    """Reorder the output CSV to match the order of the input CSV."""
    input_order = {}
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            key = (row.get("trajectory_id", ""), row.get("step_number", ""))
            input_order[key] = idx

    output_rows = []
    fieldnames = None
    with open(output_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        output_rows = list(reader)

    if not output_rows:
        return

    def sort_key(row):
        key = (row.get("trajectory_id", ""), row.get("step_number", ""))
        return input_order.get(key, 999999)

    output_rows.sort(key=sort_key)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"  Reordered {len(output_rows)} rows to match input order")


def main():
    parser = argparse.ArgumentParser(
        description="Generate bad responses for DPO training (with batch processing)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input CSV file (code_edit_dataset.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="code_edit_bad_responses.csv",
        help="Output CSV file",
    )
    parser.add_argument(
        "--backend", "-b",
        type=str,
        choices=["ollama", "vllm"],
        default="ollama",
        help="Backend to use: 'ollama' or 'vllm' (default: ollama)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model name (default: qwen2.5:32b for ollama, Qwen/Qwen2.5-32B for vllm)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server URL (default: http://localhost:11434 for ollama, http://localhost:8000 for vllm)",
    )
    parser.add_argument(
        "--num-samples", "-n",
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
        "--concurrency", "-c",
        type=int,
        default=1,
        help="Number of trajectories to process concurrently (default: 1). "
             "Higher values speed up processing with vLLM batching.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if output file exists and append new rows",
    )

    args = parser.parse_args()

    # Set default model and host based on backend
    if args.model is None:
        args.model = "Qwen/Qwen2.5-32B" if args.backend == "vllm" else "qwen2.5:32b"
    if args.host is None:
        args.host = "http://localhost:8000" if args.backend == "vllm" else "http://localhost:11434"

    # Check server is running
    if args.backend == "vllm":
        print(f"Checking vLLM at {args.host}...")
        try:
            response = httpx.get(f"{args.host}/v1/models", timeout=5.0)
            response.raise_for_status()
            models = [m["id"] for m in response.json().get("data", [])]
            print(f"Available models: {models}")
            if args.model not in models and not any(args.model in m for m in models):
                print(f"Warning: Model '{args.model}' may not be available.")
        except Exception as e:
            print(f"Error connecting to vLLM: {e}")
            print("Make sure vLLM is running. Examples:")
            print("  # With 4-bit quantization (bitsandbytes):")
            print("  python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-32B --quantization bitsandbytes --load-format bitsandbytes")
            print("  # Or use a pre-quantized AWQ model:")
            print("  python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-32B-Instruct-AWQ --quantization awq")
            return
    else:
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

    print(f"Using backend: {args.backend}, model: {args.model}, concurrency: {args.concurrency}")

    # Load input CSV
    print(f"Loading {args.input}...")
    rows = []
    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows")

    # Group rows by trajectory_id, preserving order from CSV
    trajectories = {}
    trajectory_order = []
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

    # Apply sample limit
    trajectory_ids = trajectory_order
    if args.num_samples:
        trajectory_ids = trajectory_ids[:args.num_samples]
        print(f"Processing {len(trajectory_ids)} trajectories")

    # Handle existing output file
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

    # Process trajectories with async batch processing
    start_time = time.time()

    total_trajectories, total_processed, total_errors = asyncio.run(
        process_batch_async(
            trajectories=trajectories,
            trajectory_ids=trajectory_ids,
            existing_keys=existing_keys,
            backend=args.backend,
            model=args.model,
            host=args.host,
            timeout=args.timeout,
            concurrency=args.concurrency,
            output_path=args.output,
        )
    )

    elapsed = time.time() - start_time

    # Reorder output file to match input CSV order
    print(f"\nReordering output to match input CSV order...")
    reorder_output_to_match_input(args.input, args.output)

    print(f"\nDone!")
    print(f"  Trajectories processed: {total_trajectories}")
    print(f"  Steps processed: {total_processed}")
    print(f"  Successful: {total_processed - total_errors}")
    print(f"  Errors: {total_errors}")
    print(f"  Time: {elapsed:.1f}s ({total_processed / elapsed:.2f} steps/sec)" if elapsed > 0 else "")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
