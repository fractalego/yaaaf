#!/usr/bin/env python3
"""
Generate "bad" bash responses from a weaker model for DPO training.

This script:
1. Loads the bash_dataset.csv (with good responses)
2. Groups rows by trajectory_id to process as conversations
3. For each step, builds the conversation history using GOOD responses up to that point
4. Calls a weaker model (via Ollama or vLLM) to generate the "bad" response for that step
5. Saves to CSV with bad_response column

Usage:
    # Using Ollama (default)
    python generate_bad_bash_responses.py --input bash_dataset.csv --output bash_bad_responses.csv

    # Using vLLM with HuggingFace model
    python generate_bad_bash_responses.py --backend vllm --model Qwen/Qwen2.5-32B --input bash_dataset.csv --output bad.csv

    # Batch processing (process 8 trajectories in parallel)
    python generate_bad_bash_responses.py --backend vllm --concurrency 8 --input bash_dataset.csv --output bad.csv

    # Limit samples for testing
    python generate_bad_bash_responses.py --input bash_dataset.csv --output bad.csv --num-samples 10

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
            "num_predict": 1024,
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
        "max_tokens": 1024,
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
    conversation_history: list[dict],
) -> str:
    """Assemble the full conversation prompt including history."""
    parts = []
    parts.append(f"TASK: {instruction}")

    for i, step in enumerate(conversation_history, 1):
        parts.append("")
        parts.append(f"--- Step {i} ---")
        parts.append("")
        parts.append("COMMAND:")
        parts.append(step.get("response", ""))
        parts.append("")
        parts.append("OUTPUT:")
        parts.append(step.get("executor_response", ""))

    if conversation_history:
        parts.append("")
        parts.append(f"--- Step {len(conversation_history) + 1} ---")
        parts.append("")
        parts.append("Based on the previous outputs, provide your next bash command:")
    else:
        parts.append("")
        parts.append("Provide your first bash command to start investigating:")

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

        if steps_to_process > 0 and verbose:
            print(f"  [{traj_id}] Processing {steps_to_process} steps...", flush=True)

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

            user_prompt = assemble_conversation_prompt(
                instruction=instruction,
                conversation_history=conversation_history,
            )

            if verbose:
                print(f"      Calling LLM for step {step_num}...", flush=True)

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
                    "command": row.get("command", ""),
                })
                if verbose:
                    print(f"    Step {step_num}: OK ({len(bad_response)} chars)", flush=True)
            else:
                errors += 1
                if verbose:
                    print(f"    Step {step_num}: ERROR", flush=True)

            conversation_history.append({
                "response": row.get("response", ""),
                "executor_response": row.get("executor_response", ""),
            })

        if steps_to_process > 0 and verbose:
            print(f"  [{traj_id}] Done: {processed_steps - errors}/{steps_to_process} successful", flush=True)

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
                "command",
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
        description="Generate bad bash responses for DPO training (with batch processing)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input CSV file (bash_dataset.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="bash_bad_responses.csv",
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
        default=60.0,
        help="Request timeout in seconds (default: 60)",
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
                    "command",
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
