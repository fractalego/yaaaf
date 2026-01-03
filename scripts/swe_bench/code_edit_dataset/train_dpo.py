#!/usr/bin/env python3
"""
DPO (Direct Preference Optimization) training script for CodeEditAgent.

Trains a LoRA adapter on Qwen2.5-14B using:
- Good responses from code_edit_dataset.csv (chosen)
- Bad responses from code_edit_bad_responses.csv (rejected)

Each training example includes the full conversation history up to that step.

Usage:
    python train_dpo.py \
        --good-data code_edit_dataset.csv \
        --bad-data code_edit_bad_responses.csv \
        --output-dir ./dpo_output \
        --num-epochs 3

    # Resume from checkpoint
    python train_dpo.py \
        --good-data code_edit_dataset.csv \
        --bad-data code_edit_bad_responses.csv \
        --output-dir ./dpo_output \
        --resume-from-checkpoint

Requirements:
    pip install transformers trl peft bitsandbytes datasets accelerate
"""

import argparse
import csv
import os
from dataclasses import dataclass
from typing import Optional

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import DPOConfig, DPOTrainer


# Task completion marker - appended to the last step of each trajectory
TASK_COMPLETED_MARKER = "\n<taskcompleted/>"


# CodeEditAgent system prompt - adapted for training
SYSTEM_PROMPT = """Your task is to perform code editing operations on files. You can:
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

WHEN TO USE EACH OPERATION:
- VIEW: When you need to read/understand code (analysis, exploration)
- CREATE: When you need to create a new file that doesn't exist
- STR_REPLACE: When you need to FIX bugs, MODIFY code, or APPLY changes

To perform an operation, output a code_edit block in this format:

For viewing a file:
```code_edit
operation: view
path: /path/to/file
```

For viewing specific lines:
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

CRITICAL for str_replace - YOU MUST INCLUDE LINE NUMBERS:
- COPY the lines EXACTLY as shown in VIEW output, INCLUDING the line number prefix
- Each line MUST start with the line number, then a tab, then the code
- The old_str and new_str MUST have matching line numbers

When the task is complete, include <taskcompleted/> in your response."""


@dataclass
class TrainingExample:
    """A single DPO training example."""
    prompt: str
    chosen: str
    rejected: str


def load_csv(path: str) -> list[dict]:
    """Load a CSV file into a list of dicts."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_conversation_prompt(
    instruction: str,
    file_content: str,
    file_path: str,
    conversation_history: list[dict],
) -> str:
    """Build the user prompt including conversation history.

    Args:
        instruction: The task instruction
        file_content: Initial file content (with line numbers)
        file_path: Path to the file
        conversation_history: List of previous steps with 'response' and 'executor_response'

    Returns:
        Formatted prompt string
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

    # Add conversation history
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


def prepare_dpo_dataset(
    good_data_path: str,
    bad_data_path: str,
    max_samples: Optional[int] = None,
) -> list[TrainingExample]:
    """Prepare DPO training examples from good and bad response CSVs.

    Args:
        good_data_path: Path to code_edit_dataset.csv
        bad_data_path: Path to code_edit_bad_responses.csv
        max_samples: Maximum number of samples (for testing)

    Returns:
        List of TrainingExample objects
    """
    print(f"Loading good data from {good_data_path}...")
    good_rows = load_csv(good_data_path)
    print(f"  Loaded {len(good_rows)} rows")

    print(f"Loading bad data from {bad_data_path}...")
    bad_rows = load_csv(bad_data_path)
    print(f"  Loaded {len(bad_rows)} rows")

    # Index bad responses by (trajectory_id, step_number)
    bad_by_key = {}
    for row in bad_rows:
        key = (row.get("trajectory_id", ""), row.get("step_number", ""))
        bad_by_key[key] = row.get("bad_response", "")

    # Group good rows by trajectory_id
    trajectories = {}
    trajectory_order = []
    for row in good_rows:
        traj_id = row.get("trajectory_id", "unknown")
        if traj_id not in trajectories:
            trajectories[traj_id] = []
            trajectory_order.append(traj_id)
        trajectories[traj_id].append(row)

    # Sort each trajectory by step_number
    for traj_id in trajectories:
        trajectories[traj_id].sort(key=lambda x: int(x.get("step_number", 0)))

    print(f"Found {len(trajectories)} trajectories")

    # Build training examples
    examples = []
    skipped = 0
    completed_trajectories = 0

    for traj_id in trajectory_order:
        traj_steps = trajectories[traj_id]
        conversation_history = []
        num_steps = len(traj_steps)

        for step_idx, row in enumerate(traj_steps):
            step_num = row.get("step_number", "")
            key = (traj_id, step_num)
            is_last_step = (step_idx == num_steps - 1)

            # Get bad response for this step
            bad_response = bad_by_key.get(key)
            if not bad_response:
                skipped += 1
                # Still add to conversation history
                conversation_history.append({
                    "response": row.get("response", ""),
                    "executor_response": row.get("executor_response", ""),
                })
                continue

            # Build the prompt with conversation history
            prompt = build_conversation_prompt(
                instruction=row.get("instruction", ""),
                file_content=row.get("file_content", ""),
                file_path=row.get("file_path", ""),
                conversation_history=conversation_history,
            )

            # Get responses
            chosen = row.get("response", "")
            rejected = bad_response

            # Append completion marker to the last step of each trajectory
            if is_last_step:
                chosen = chosen + TASK_COMPLETED_MARKER
                rejected = rejected + TASK_COMPLETED_MARKER
                completed_trajectories += 1

            # Good response is "chosen", bad response is "rejected"
            examples.append(TrainingExample(
                prompt=prompt,
                chosen=chosen,
                rejected=rejected,
            ))

            # Add to conversation history for next step
            conversation_history.append({
                "response": row.get("response", ""),
                "executor_response": row.get("executor_response", ""),
            })

            if max_samples and len(examples) >= max_samples:
                break

        if max_samples and len(examples) >= max_samples:
            break

    print(f"Created {len(examples)} training examples ({skipped} skipped due to missing bad response)")
    print(f"  - {completed_trajectories} examples marked with completion token (last step of trajectory)")
    return examples


def format_for_qwen(
    tokenizer,
    system_prompt: str,
    user_prompt: str,
    assistant_response: str,
) -> str:
    """Format a conversation for Qwen's chat template.

    Args:
        tokenizer: The tokenizer with chat template
        system_prompt: System prompt
        user_prompt: User message
        assistant_response: Assistant response

    Returns:
        Formatted string
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": assistant_response},
    ]

    # Use tokenizer's chat template
    return tokenizer.apply_chat_template(messages, tokenize=False)


def examples_to_dataset(
    examples: list[TrainingExample],
    tokenizer,
) -> Dataset:
    """Convert training examples to a HuggingFace Dataset for DPO.

    DPO expects columns: prompt, chosen, rejected
    """
    data = {
        "prompt": [],
        "chosen": [],
        "rejected": [],
    }

    for ex in examples:
        # Format prompt with system message for Qwen
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ex.prompt},
        ]
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        data["prompt"].append(formatted_prompt)
        data["chosen"].append(ex.chosen)
        data["rejected"].append(ex.rejected)

    return Dataset.from_dict(data)


def main():
    parser = argparse.ArgumentParser(
        description="DPO training for CodeEditAgent using LoRA on Qwen2.5-14B"
    )
    parser.add_argument(
        "--good-data",
        type=str,
        required=True,
        help="Path to code_edit_dataset.csv (good responses)",
    )
    parser.add_argument(
        "--bad-data",
        type=str,
        required=True,
        help="Path to code_edit_bad_responses.csv (bad responses)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./dpo_output",
        help="Output directory for checkpoints and final model",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="Qwen/Qwen2.5-14B",
        help="Base model name (default: Qwen/Qwen2.5-14B)",
    )
    parser.add_argument(
        "--num-epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Per-device batch size (default: 1)",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=8,
        help="Gradient accumulation steps (default: 8, effective batch = batch_size * grad_accum)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-5,
        help="Learning rate (default: 5e-5)",
    )
    parser.add_argument(
        "--lora-rank",
        type=int,
        default=16,
        help="LoRA rank (default: 16)",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=32,
        help="LoRA alpha (default: 32)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum training samples (for testing)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=4096,
        help="Maximum total sequence length (prompt + response) (default: 4096)",
    )
    parser.add_argument(
        "--max-prompt-length",
        type=int,
        default=3072,
        help="Maximum prompt length (default: 3072)",
    )
    parser.add_argument(
        "--max-completion-length",
        type=int,
        default=1024,
        help="Maximum completion/response length (default: 1024)",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=0.1,
        help="DPO beta parameter (default: 0.1)",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        action="store_true",
        help="Resume training from latest checkpoint",
    )
    parser.add_argument(
        "--merge-and-save",
        action="store_true",
        default=True,
        help="Merge LoRA weights and save full model (default: True)",
    )

    args = parser.parse_args()

    # Prepare dataset
    print("\n=== Preparing Dataset ===")
    examples = prepare_dpo_dataset(
        good_data_path=args.good_data,
        bad_data_path=args.bad_data,
        max_samples=args.max_samples,
    )

    if len(examples) == 0:
        print("No training examples found. Check your data files.")
        return

    # Load tokenizer
    print(f"\n=== Loading Tokenizer ===")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Convert to HuggingFace Dataset
    print("\n=== Converting to Dataset ===")
    dataset = examples_to_dataset(examples, tokenizer)
    print(f"Dataset size: {len(dataset)}")

    # Split into train/eval (95/5)
    dataset = dataset.train_test_split(test_size=0.05, seed=42)
    train_dataset = dataset["train"]
    eval_dataset = dataset["test"]
    print(f"Train size: {len(train_dataset)}, Eval size: {len(eval_dataset)}")

    # Configure 4-bit quantization
    print(f"\n=== Loading Model with 4-bit Quantization ===")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # Load model with Flash Attention 2 (requires PyTorch 2.5 + flash-attn wheel)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
    )

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    # Configure LoRA
    print(f"\n=== Configuring LoRA (rank={args.lora_rank}, alpha={args.lora_alpha}) ===")
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    # Apply LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # For DPO, we need a reference model (the original model)
    # With PEFT/LoRA, we set ref_model=None which makes DPOTrainer use the frozen
    # base weights as reference (avoiding loading a second full model copy).
    # Combined with precompute_ref_log_probs=True in DPOConfig, this significantly
    # reduces VRAM usage by:
    # 1. Not keeping a separate reference model in memory during training
    # 2. Computing reference log probs once at start instead of during each batch
    #
    # Memory layout:
    # - Base model: 4-bit quantized (~7GB for 14B params), shared & frozen
    # - LoRA adapters: bfloat16 (~50-100MB), trainable
    # - Reference = base model with adapters disabled (no extra memory)
    # - Policy = base model + LoRA adapters
    ref_model = None

    # Verify quantization is active
    print("\n=== Memory Configuration ===")
    print(f"  Base model quantized: {model.base_model.model.model.embed_tokens.weight.dtype}")
    if hasattr(model.base_model.model.model.layers[0].self_attn.q_proj, 'weight'):
        w = model.base_model.model.model.layers[0].self_attn.q_proj.weight
        print(f"  Attention weights quantized: {hasattr(w, 'quant_state')}")
    print("  Reference model: using frozen quantized base (no separate copy)")
    print("  LoRA adapters: bfloat16 (trainable)")

    # Configure training
    print(f"\n=== Configuring Training ===")
    training_args = DPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        logging_steps=10,
        save_steps=100,
        eval_steps=100,
        eval_strategy="steps",
        save_total_limit=3,
        bf16=True,
        gradient_checkpointing=True,  # Saves ~40% VRAM
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        max_completion_length=args.max_completion_length,
        beta=args.beta,
        remove_unused_columns=False,
        report_to="none",  # Set to "wandb" if you want W&B logging
        # With ref_model=None and LoRA, reference log probs are computed by
        # temporarily disabling adapters on the same quantized model - no extra VRAM
        precompute_ref_log_probs=False,
        # Performance optimizations
        optim="paged_adamw_8bit",  # 8-bit optimizer reduces memory, may allow larger batch
        # torch_compile disabled - incompatible with transformers+PEFT+TRL+quantization stack
        dataloader_num_workers=4,  # Parallel data loading
        dataloader_pin_memory=True,  # Faster CPU->GPU transfer
    )

    # Initialize trainer
    print(f"\n=== Initializing DPO Trainer ===")
    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,  # renamed from 'tokenizer' in newer TRL versions
    )

    # Train
    print(f"\n=== Starting Training ===")
    print(f"  Epochs: {args.num_epochs}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Gradient accumulation: {args.gradient_accumulation_steps}")
    print(f"  Effective batch size: {args.batch_size * args.gradient_accumulation_steps}")
    print(f"  Learning rate: {args.learning_rate}")
    print(f"  DPO beta: {args.beta}")
    print()

    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)

    # Save LoRA adapter
    print(f"\n=== Saving LoRA Adapter ===")
    lora_output_dir = os.path.join(args.output_dir, "lora_adapter")
    trainer.save_model(lora_output_dir)
    tokenizer.save_pretrained(lora_output_dir)
    print(f"LoRA adapter saved to: {lora_output_dir}")

    # Merge and save full model
    if args.merge_and_save:
        print(f"\n=== Merging LoRA and Saving Full Model ===")
        merged_output_dir = os.path.join(args.output_dir, "merged_model")

        # Merge LoRA weights
        merged_model = model.merge_and_unload()

        # Save merged model
        merged_model.save_pretrained(merged_output_dir)
        tokenizer.save_pretrained(merged_output_dir)
        print(f"Merged model saved to: {merged_output_dir}")

    print(f"\n=== Training Complete ===")
    print(f"Output directory: {args.output_dir}")
    print(f"  - LoRA adapter: {lora_output_dir}")
    if args.merge_and_save:
        print(f"  - Merged model: {merged_output_dir}")


if __name__ == "__main__":
    main()
