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
import gc
import os
import warnings
from dataclasses import dataclass
from typing import Optional

# Suppress Mistral tokenizer warning about tokenize=False
warnings.filterwarnings("ignore", message=".*tokenize=False.*")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers.tokenization_mistral_common")

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
    TrainingArguments,
)
from trl import DPOConfig, DPOTrainer


def clear_memory():
    """Aggressively clear GPU and CPU memory."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def compute_log_probs_on_cpu(
    model,
    tokenizer,
    dataset,
    max_length: int,
    max_prompt_length: int = 1024,
    batch_size: int = 1,
):
    """
    Compute reference log probs and store on CPU.

    Matches TRL's DPO format: computes log probs only for completion tokens (not prompt).
    Returns dataset with 'reference_chosen_logps' and 'reference_rejected_logps' columns.
    """
    from tqdm import tqdm

    print("\n=== Computing Reference Log Probs (GPU->CPU) ===")

    model.eval()
    chosen_logps = []
    rejected_logps = []

    # Disable LoRA for reference model computation
    model.disable_adapter_layers()

    def compute_completion_logprobs(prompt_text, completion_text):
        """Compute log probs for completion tokens only."""
        # Tokenize prompt to get its length
        prompt_ids = tokenizer(
            prompt_text,
            return_tensors="pt",
            truncation=True,
            max_length=max_prompt_length,
            add_special_tokens=True,
        )["input_ids"]
        prompt_len = prompt_ids.shape[1]

        # Tokenize full sequence
        full_text = prompt_text + completion_text
        inputs = tokenizer(
            full_text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
            add_special_tokens=True,
        ).to(model.device)

        # Forward pass
        outputs = model(**inputs)
        logits = outputs.logits

        # Shift for next-token prediction
        shift_logits = logits[:, :-1, :]
        shift_labels = inputs["input_ids"][:, 1:]

        # Compute per-token log probs
        log_probs = torch.nn.functional.log_softmax(shift_logits, dim=-1)
        token_log_probs = torch.gather(
            log_probs, 2, shift_labels.unsqueeze(-1)
        ).squeeze(-1)

        # Only sum log probs for completion tokens (after prompt)
        # prompt_len-1 because of the shift
        completion_start = max(0, prompt_len - 1)
        completion_log_probs = token_log_probs[:, completion_start:]
        total_logp = completion_log_probs.sum().cpu().item()

        # Cleanup
        del inputs, outputs, logits, log_probs, token_log_probs
        return total_logp

    with torch.no_grad():
        for i in tqdm(range(len(dataset)), desc="Computing ref log probs"):
            example = dataset[i]
            prompt = example["prompt"]

            # Compute log probs for chosen completion
            chosen_logp = compute_completion_logprobs(prompt, example["chosen"])
            chosen_logps.append(chosen_logp)

            # Compute log probs for rejected completion
            rejected_logp = compute_completion_logprobs(prompt, example["rejected"])
            rejected_logps.append(rejected_logp)

            # Clear GPU memory periodically
            if i % 5 == 0:
                clear_memory()

    # Re-enable LoRA
    model.enable_adapter_layers()

    # Add to dataset (TRL expects these exact column names in the batch)
    dataset = dataset.add_column("ref_chosen_logps", chosen_logps)
    dataset = dataset.add_column("ref_rejected_logps", rejected_logps)

    print(f"  Computed {len(chosen_logps)} reference log probs")

    return dataset


class MemoryCleanupCallback(TrainerCallback):
    """Callback to clear memory at key points during training."""

    def on_train_begin(self, args, state, control, **kwargs):
        """Clear memory after precomputation and before training loop starts."""
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
        # Format prompt with system message
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ex.prompt},
        ]

        # Try with add_generation_prompt (Qwen, Llama), fall back without (Mistral)
        try:
            formatted_prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        except (ValueError, TypeError):
            # Mistral tokenizer doesn't support add_generation_prompt
            formatted_prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False
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
        default="mistralai/Devstral-Small-2507",
        help="Base model name (default: mistralai/Devstral-Small-2507)",
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
    parser.add_argument(
        "--minimal-lora",
        action="store_true",
        help="Use minimal LoRA targets (q_proj, v_proj only) to save memory",
    )
    parser.add_argument(
        "--cpu-offload",
        action="store_true",
        help="Offload optimizer states to CPU (slower but saves VRAM)",
    )
    parser.add_argument(
        "--precompute-on-cpu",
        action="store_true",
        help="Compute reference log probs on CPU to save GPU memory for training",
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
    # Try to load a compatible tokenizer (Mistral's MistralCommonTokenizer isn't compatible with TRL)
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
        # Check if it's a compatible type
        from transformers import PreTrainedTokenizerBase
        if not isinstance(tokenizer, PreTrainedTokenizerBase):
            print("  Warning: Non-standard tokenizer detected, trying slow tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=False)
    except Exception as e:
        print(f"  Tokenizer load error: {e}, trying with trust_remote_code...")
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)

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

    # Flag to track if we did our own precomputation
    did_manual_precompute = False

    # If precompute-on-cpu is set, load model, compute log probs, then fully unload
    if args.precompute_on_cpu:
        print(f"\n=== Phase 1: Precompute Reference Log Probs ===")
        print(f"Loading model for precomputation...")

        precompute_model = AutoModelForCausalLM.from_pretrained(
            args.model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
        )
        precompute_model = prepare_model_for_kbit_training(precompute_model)
        precompute_model = get_peft_model(precompute_model, lora_config)

        # Compute log probs for train and eval datasets
        train_dataset = compute_log_probs_on_cpu(
            precompute_model, tokenizer, train_dataset,
            args.max_length, args.max_prompt_length
        )
        eval_dataset = compute_log_probs_on_cpu(
            precompute_model, tokenizer, eval_dataset,
            args.max_length, args.max_prompt_length
        )

        # Completely unload model to free GPU memory
        print("\n=== Unloading precomputation model ===")
        del precompute_model
        clear_memory()

        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"  GPU memory after unload: {allocated:.2f} GiB allocated, {reserved:.2f} GiB reserved")

        did_manual_precompute = True

    # Load fresh model for training
    print(f"\n=== Loading Model for Training (4-bit Quantization) ===")
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

    ref_model = None

    # Verify quantization is active
    print("\n=== Memory Configuration ===")
    print(f"  Base model quantized: {model.base_model.model.model.embed_tokens.weight.dtype}")
    if hasattr(model.base_model.model.model.layers[0].self_attn.q_proj, 'weight'):
        w = model.base_model.model.model.layers[0].self_attn.q_proj.weight
        print(f"  Attention weights quantized: {hasattr(w, 'quant_state')}")
    print("  Reference model: using frozen quantized base (no separate copy)")
    print("  LoRA adapters: bfloat16 (trainable)")
    if did_manual_precompute:
        print("  Reference log probs: precomputed and stored on CPU")

    # Configure training
    print(f"\n=== Configuring Training ===")

    # Adjust settings based on memory constraints
    if args.cpu_offload:
        print("  Using CPU offloading for optimizer states")
        # Use paged optimizer which can spill to CPU when needed
        optim = "paged_adamw_8bit"
        dataloader_num_workers = 0  # Reduce memory pressure
        dataloader_pin_memory = False
    else:
        optim = "paged_adamw_8bit"
        dataloader_num_workers = 4
        dataloader_pin_memory = True

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
        gradient_checkpointing_kwargs={"use_reentrant": False},  # More memory-efficient
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        max_completion_length=args.max_completion_length,
        beta=args.beta,
        remove_unused_columns=False,
        report_to="none",  # Set to "wandb" if you want W&B logging
        # Always set to True - if we did manual precomputation, TRL will find
        # the ref_chosen_logps/ref_rejected_logps columns and skip recomputing
        precompute_ref_log_probs=True,
        # Performance optimizations
        optim=optim,
        # torch_compile disabled - incompatible with transformers+PEFT+TRL+quantization stack
        dataloader_num_workers=dataloader_num_workers,
        dataloader_pin_memory=dataloader_pin_memory,
    )

    # Initialize trainer with memory cleanup callback
    print(f"\n=== Initializing DPO Trainer ===")
    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,  # renamed from 'tokenizer' in newer TRL versions
        callbacks=[MemoryCleanupCallback()],
    )

    # If we did manual precomputation, tell TRL to skip its own precomputation
    if did_manual_precompute:
        print("  Skipping TRL precomputation (already done manually)")
        trainer._precomputed_train_ref_log_probs = True
        trainer._precomputed_eval_ref_log_probs = True

        # Verify columns survived TRL's processing
        train_cols = trainer.train_dataset.column_names
        print(f"  Train dataset columns: {train_cols}")
        if "ref_chosen_logps" not in train_cols:
            print("  WARNING: ref_chosen_logps column missing after TRL processing!")

    # Clear memory before training to free any allocation from setup
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
