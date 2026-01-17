#!/usr/bin/env python3
"""
SFT (Supervised Fine-Tuning) training script for CodeEditAgent.

Trains a LoRA adapter on Qwen2.5-32B using good responses from code_edit_dataset.csv.
Each training example includes the full conversation history up to that step.

Usage:
    python train_sft.py \
        --data code_edit_dataset.csv \
        --output-dir ./sft_output \
        --num-epochs 3

    # Resume from checkpoint
    python train_sft.py \
        --data code_edit_dataset.csv \
        --output-dir ./sft_output \
        --resume-from-checkpoint

Requirements:
    pip install transformers trl peft bitsandbytes datasets accelerate
"""

import argparse
import csv
import gc
import os
import warnings
from dataclasses import dataclass
from typing import Optional, List

# Suppress warnings
warnings.filterwarnings("ignore", message=".*tokenize=False.*")

import logging
logging.getLogger("transformers.tokenization_mistral_common").setLevel(logging.ERROR)

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
)
from trl import SFTConfig, SFTTrainer


def clear_memory():
    """Aggressively clear GPU and CPU memory."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


class MemoryCleanupCallback(TrainerCallback):
    """Callback to clear memory at key points during training."""

    def on_train_begin(self, args, state, control, **kwargs):
        """Clear memory before training loop starts."""
        print("\n=== Clearing memory before training loop ===")
        clear_memory()
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"  GPU memory: {allocated:.2f} GiB allocated, {reserved:.2f} GiB reserved")

    def on_step_end(self, args, state, control, **kwargs):
        """Periodically clear memory during training."""
        if state.global_step % 50 == 0:
            clear_memory()


# Task completion marker - appended to the last step of each trajectory
TASK_COMPLETED_MARKER = "\n<taskcompleted/>"


# CodeEditAgent system prompt
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
    """A single SFT training example."""
    prompt: str
    response: str


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
    """Build the user prompt including conversation history."""
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


def prepare_sft_dataset(
    data_path: str,
    max_samples: Optional[int] = None,
) -> List[TrainingExample]:
    """Prepare SFT training examples from good response CSV.

    Args:
        data_path: Path to code_edit_dataset.csv
        max_samples: Maximum number of samples (for testing)

    Returns:
        List of TrainingExample objects
    """
    print(f"Loading data from {data_path}...")
    rows = load_csv(data_path)
    print(f"  Loaded {len(rows)} rows")

    # Group rows by trajectory_id
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

    print(f"Found {len(trajectories)} trajectories")

    # Build training examples
    examples = []
    completed_trajectories = 0

    for traj_id in trajectory_order:
        traj_steps = trajectories[traj_id]
        conversation_history = []
        num_steps = len(traj_steps)

        for step_idx, row in enumerate(traj_steps):
            is_last_step = (step_idx == num_steps - 1)

            # Build the prompt with conversation history
            prompt = build_conversation_prompt(
                instruction=row.get("instruction", ""),
                file_content=row.get("file_content", ""),
                file_path=row.get("file_path", ""),
                conversation_history=conversation_history,
            )

            # Get response
            response = row.get("response", "")

            # Append completion marker to the last step of each trajectory
            if is_last_step:
                response = response + TASK_COMPLETED_MARKER
                completed_trajectories += 1

            examples.append(TrainingExample(
                prompt=prompt,
                response=response,
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

    print(f"Created {len(examples)} training examples")
    print(f"  - {completed_trajectories} examples marked with completion token (last step of trajectory)")
    return examples


def examples_to_dataset(
    examples: List[TrainingExample],
    tokenizer,
) -> Dataset:
    """Convert training examples to a HuggingFace Dataset for SFT.

    SFT expects a 'text' column with the full formatted conversation.
    """
    data = {"text": []}

    for ex in examples:
        # Format as chat messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ex.prompt},
            {"role": "assistant", "content": ex.response},
        ]

        # Apply chat template to get full formatted text
        try:
            formatted_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False
            )
        except (ValueError, TypeError):
            # Fallback for tokenizers that don't support add_generation_prompt
            formatted_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False
            )

        data["text"].append(formatted_text)

    return Dataset.from_dict(data)


def main():
    parser = argparse.ArgumentParser(
        description="SFT training for CodeEditAgent using LoRA on Qwen2.5-32B"
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to code_edit_dataset.csv (good responses)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./sft_output",
        help="Output directory for checkpoints and final model",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="Qwen/Qwen2.5-32B-Instruct",
        help="Base model name (default: Qwen/Qwen2.5-32B-Instruct)",
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
        default=2e-4,
        help="Learning rate (default: 2e-4)",
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
        "--max-seq-length",
        type=int,
        default=4096,
        help="Maximum sequence length (default: 4096)",
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
    parser.add_argument(
        "--minimal-lora",
        action="store_true",
        help="Use minimal LoRA targets (q_proj, v_proj only) to save memory",
    )

    args = parser.parse_args()

    # Prepare dataset
    print("\n=== Preparing Dataset ===")
    examples = prepare_sft_dataset(
        data_path=args.data,
        max_samples=args.max_samples,
    )

    if len(examples) == 0:
        print("No training examples found. Check your data file.")
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

    # Configure LoRA
    if args.minimal_lora:
        target_modules = ["q_proj", "v_proj"]
        lora_mode_str = "MINIMAL"
    else:
        target_modules = [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
        lora_mode_str = "FULL"

    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
    )

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    print(f"\n=== Configuring LoRA (rank={args.lora_rank}, alpha={args.lora_alpha}, {lora_mode_str} mode) ===")

    # Apply LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Verify quantization is active
    print("\n=== Memory Configuration ===")
    print(f"  Base model quantized: {model.base_model.model.model.embed_tokens.weight.dtype}")
    if hasattr(model.base_model.model.model.layers[0].self_attn.q_proj, 'weight'):
        w = model.base_model.model.model.layers[0].self_attn.q_proj.weight
        print(f"  Attention weights quantized: {hasattr(w, 'quant_state')}")
    print("  LoRA adapters: bfloat16 (trainable)")

    # Configure training
    print(f"\n=== Configuring Training ===")
    training_args = SFTConfig(
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
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=args.max_seq_length,
        dataset_text_field="text",
        report_to="none",
        optim="paged_adamw_8bit",
        dataloader_num_workers=4,
        dataloader_pin_memory=True,
    )

    # Initialize trainer
    print(f"\n=== Initializing SFT Trainer ===")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        callbacks=[MemoryCleanupCallback()],
    )

    # Clear memory before training
    print("\n=== Clearing memory before starting training ===")
    clear_memory()
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        print(f"  GPU memory: {allocated:.2f} GiB allocated, {reserved:.2f} GiB reserved")

    # Train
    print(f"\n=== Starting Training ===")
    print(f"  Epochs: {args.num_epochs}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Gradient accumulation: {args.gradient_accumulation_steps}")
    print(f"  Effective batch size: {args.batch_size * args.gradient_accumulation_steps}")
    print(f"  Learning rate: {args.learning_rate}")
    print(f"  Max sequence length: {args.max_seq_length}")
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
