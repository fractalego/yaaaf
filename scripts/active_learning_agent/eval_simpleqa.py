"""
Evaluate epistemic foraging on SimpleQA.

Compares:
  - baseline: model answers directly (no search)
  - single_search: one brave search, then answer
  - foraging: full epistemic foraging loop with EFE action selection

Dataset: basicv8vc/SimpleQA (4326 factual questions with short answers)

Usage:
    python eval_simpleqa.py --n 50 --brave-key $BRAVE_API_KEY
    python eval_simpleqa.py --n 50 --brave-key $BRAVE_API_KEY --mode foraging
    python eval_simpleqa.py --n 50 --brave-key $BRAVE_API_KEY --mode all
"""

import os
import sys
import json
import argparse
import time
import numpy as np
import requests
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset

MODEL_NAME = "google/gemma-3-4b-it"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


_model = None
_tokenizer = None


def get_model():
    global _model, _tokenizer
    if _model is None:
        print(f"Loading {MODEL_NAME}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=torch.bfloat16,
            device_map="auto",
        )
        _model.eval()
        print("Model loaded.")
    return _model, _tokenizer


# ---------------------------------------------------------------------------
# LLM primitives
# ---------------------------------------------------------------------------


def generate(prompt, max_new_tokens=256, temperature=0.7):
    model, tokenizer = get_model()
    inputs = tokenizer(prompt, return_tensors="pt", return_attention_mask=True).to(model.device)
    gen_kwargs = dict(
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        attention_mask=inputs["attention_mask"],
    )
    if temperature > 0:
        gen_kwargs["do_sample"] = True
        gen_kwargs["temperature"] = temperature
    else:
        gen_kwargs["do_sample"] = False
    with torch.no_grad():
        out = model.generate(inputs["input_ids"], **gen_kwargs)
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()


def log_likelihood(context, candidate):
    """log p(candidate | context) from token-level logprobs."""
    model, tokenizer = get_model()

    context_ids = tokenizer.encode(context, add_special_tokens=False)
    full_ids = tokenizer.encode(context + candidate, add_special_tokens=False)
    candidate_start = len(context_ids)

    if candidate_start >= len(full_ids):
        return -1e6

    input_ids = torch.tensor([full_ids], device=model.device)
    with torch.no_grad():
        logits = model(input_ids).logits

    log_probs = torch.log_softmax(logits[0], dim=-1)
    total = 0.0
    for i in range(candidate_start, len(full_ids)):
        total += log_probs[i - 1, full_ids[i]].item()
    return total


# ---------------------------------------------------------------------------
# Brave search
# ---------------------------------------------------------------------------


def brave_search(query, api_key, count=5):
    """Search via Brave API. Returns list of {title, url, snippet}."""
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
        params={"q": query, "count": count},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("web", {}).get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in results
    ]


def format_search_results(results):
    parts = []
    for r in results:
        parts.append(f"- {r['title']}: {r['snippet']}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Belief helpers
# ---------------------------------------------------------------------------


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def entropy(log_scores):
    p = softmax(log_scores)
    return -np.sum(p * np.log(p + 1e-10))


# ---------------------------------------------------------------------------
# Mode 1: baseline (no search)
# ---------------------------------------------------------------------------


def run_baseline(question):
    prompt = (
        f"Answer the following question with a short, direct answer. "
        f"Just give the answer, nothing else.\n\n"
        f"Question: {question}\nAnswer:"
    )
    return generate(prompt, max_new_tokens=64, temperature=0.0)


# ---------------------------------------------------------------------------
# Mode 2: single search
# ---------------------------------------------------------------------------


def run_single_search(question, api_key):
    results = brave_search(question, api_key, count=5)
    evidence = format_search_results(results)

    prompt = (
        f"Based on the following search results, answer the question "
        f"with a short, direct answer. Just give the answer, nothing else.\n\n"
        f"Search results:\n{evidence}\n\n"
        f"Question: {question}\nAnswer:"
    )
    return generate(prompt, max_new_tokens=64, temperature=0.0)


# ---------------------------------------------------------------------------
# Mode 3: epistemic foraging
# ---------------------------------------------------------------------------


def generate_candidates(question, k=5):
    prompt = (
        f"Given this question, generate {k} diverse possible answers.\n"
        f"Each answer should be short and direct (a few words).\n"
        f"One per line, numbered 1-{k}.\n\n"
        f"Question: {question}\n\n"
    )
    raw = generate(prompt, temperature=0.9)
    candidates = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            text = line.split(".", 1)[-1].strip() if "." in line[:3] else line
            text = text.split(")", 1)[-1].strip() if ")" in text[:3] else text
            if text:
                candidates.append(text)
    return candidates[:k]


def score_candidates(candidates, context, question):
    prefix = f"Question: {question}\n\nEvidence:\n{context}\n\nAnswer:"
    scores = np.zeros(len(candidates))
    for i, c in enumerate(candidates):
        scores[i] = log_likelihood(prefix, " " + c)
    return scores


def generate_search_queries(question, context):
    prompt = (
        f"Given this question and evidence so far, suggest 3 different "
        f"web search queries that would help find the answer.\n"
        f"One per line, numbered 1-3. Just the query, no explanation.\n\n"
        f"Question: {question}\n"
        f"Evidence: {context if context else '(none yet)'}\n\n"
    )
    raw = generate(prompt, temperature=0.7)
    actions = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            text = line.split(".", 1)[-1].strip() if "." in line[:3] else line
            text = text.split(")", 1)[-1].strip() if ")" in text[:3] else text
            if text:
                actions.append(text)
    return actions[:3]


def predict_observation(action, context):
    """q(o|a) -- LLM as world model."""
    prompt = (
        f'If I search the web for: "{action}"\n\n'
        f"What results would I likely find? Summarise in 2-3 sentences.\n\n"
    )
    return generate(prompt, max_new_tokens=128, temperature=0.5)


def compute_efe(action, candidates, context, question):
    """G(a) = ambiguity after predicted observation."""
    o_predicted = predict_observation(action, context)
    updated_context = f"{context}\n\n{o_predicted}" if context else o_predicted
    updated_scores = score_candidates(candidates, updated_context, question)
    return entropy(updated_scores)


def run_foraging(question, api_key, threshold=0.5, max_iterations=3, k=5):
    trace = {"candidates": [], "iterations": [], "final": {}}

    candidates = generate_candidates(question, k=k)
    if not candidates:
        return run_single_search(question, api_key), {"fallback": "no candidates"}

    trace["candidates"] = candidates

    context = ""
    searches = []

    for t in range(max_iterations):
        scores = score_candidates(candidates, context, question)
        H = entropy(scores)
        p = softmax(scores)

        iteration = {
            "t": t,
            "entropy": round(float(H), 4),
            "beliefs": {c: round(float(p[i]), 4) for i, c in enumerate(candidates)},
            "log_scores": {c: round(float(scores[i]), 2) for i, c in enumerate(candidates)},
        }

        if H < threshold:
            iteration["action"] = "converged"
            trace["iterations"].append(iteration)
            break

        actions = generate_search_queries(question, context)
        if not actions:
            iteration["action"] = "no queries generated"
            trace["iterations"].append(iteration)
            break

        G_values = []
        for a in actions:
            G = compute_efe(a, candidates, context, question)
            G_values.append(G)

        best_idx = int(np.argmin(G_values))
        best_action = actions[best_idx]
        searches.append(best_action)

        iteration["candidate_queries"] = [
            {"query": a, "G": round(float(G_values[i]), 4)}
            for i, a in enumerate(actions)
        ]
        iteration["selected_query"] = best_action
        iteration["selected_G"] = round(float(G_values[best_idx]), 4)

        results = brave_search(best_action, api_key, count=5)
        evidence = format_search_results(results)
        context += f"\n\n---\nSearch: {best_action}\nResults:\n{evidence}"

        iteration["search_results"] = [
            {"title": r["title"], "snippet": r["snippet"][:120]}
            for r in results[:5]
        ]
        iteration["num_results"] = len(results)

        trace["iterations"].append(iteration)

    # final scoring
    scores = score_candidates(candidates, context, question)
    p = softmax(scores)
    winner_idx = int(np.argmax(scores))
    winner = candidates[winner_idx]

    trace["final"] = {
        "entropy": round(float(entropy(scores)), 4),
        "beliefs": {c: round(float(p[i]), 4) for i, c in enumerate(candidates)},
        "log_scores": {c: round(float(scores[i]), 2) for i, c in enumerate(candidates)},
        "winner": winner,
        "num_searches": len(searches),
    }

    return winner, trace


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def normalize(text):
    """Normalize for comparison."""
    return text.strip().lower().rstrip(".")


def is_correct(predicted, gold):
    """Check if predicted answer matches gold.

    Uses substring matching: correct if gold appears in predicted
    or predicted appears in gold.
    """
    p = normalize(predicted)
    g = normalize(gold)
    return g in p or p in g


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global MODEL_NAME

    parser = argparse.ArgumentParser(description="Evaluate foraging on SimpleQA")
    parser.add_argument("--n", type=int, default=50, help="Number of questions")
    parser.add_argument("--offset", type=int, default=0, help="Start index")
    parser.add_argument("--brave-key", type=str, default=None)
    parser.add_argument(
        "--mode",
        choices=["baseline", "single_search", "foraging", "all"],
        default="all",
    )
    parser.add_argument("--model", type=str, default=MODEL_NAME)
    parser.add_argument("--threshold", type=float, default=0.5, help="Entropy threshold for foraging")
    parser.add_argument("--max-iter", type=int, default=3, help="Max foraging iterations")
    parser.add_argument("--output", type=str, default="simpleqa_results.jsonl")
    args = parser.parse_args()

    MODEL_NAME = args.model

    api_key = args.brave_key or os.getenv("BRAVE_API_KEY")
    if not api_key and args.mode in ("single_search", "foraging", "all"):
        print("Error: --brave-key or BRAVE_API_KEY required for search modes")
        sys.exit(1)

    # load dataset
    print("Loading SimpleQA dataset...")
    ds = load_dataset("basicv8vc/SimpleQA", split="test")
    subset = ds.select(range(args.offset, min(args.offset + args.n, len(ds))))
    print(f"Evaluating {len(subset)} questions (offset={args.offset})")

    modes = (
        ["baseline", "single_search", "foraging"]
        if args.mode == "all"
        else [args.mode]
    )

    results = {m: {"correct": 0, "total": 0, "details": []} for m in modes}

    for idx, example in enumerate(subset):
        question = example["problem"]
        gold = example["answer"]
        print(f"\n[{idx+1}/{len(subset)}] Q: {question}")
        print(f"  Gold: {gold}")

        for mode in modes:
            t0 = time.time()
            trace = None
            try:
                if mode == "baseline":
                    predicted = run_baseline(question)
                elif mode == "single_search":
                    predicted = run_single_search(question, api_key)
                elif mode == "foraging":
                    predicted, trace = run_foraging(
                        question,
                        api_key,
                        threshold=args.threshold,
                        max_iterations=args.max_iter,
                    )
                else:
                    continue
            except Exception as e:
                predicted = f"ERROR: {e}"
            elapsed = time.time() - t0

            correct = is_correct(predicted, gold)
            results[mode]["correct"] += int(correct)
            results[mode]["total"] += 1

            detail = {
                "question": question,
                "gold": gold,
                "predicted": predicted,
                "correct": correct,
                "time": round(elapsed, 2),
                "mode": mode,
            }
            if trace is not None:
                detail["trace"] = trace
            results[mode]["details"].append(detail)

            mark = "OK" if correct else "WRONG"
            print(f"  [{mode}] {mark} -> {predicted}  ({elapsed:.1f}s)")

    # summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for mode in modes:
        r = results[mode]
        acc = r["correct"] / r["total"] if r["total"] > 0 else 0
        print(f"  {mode:15s}: {r['correct']}/{r['total']} = {acc:.1%}")

    # save details
    with open(args.output, "w") as f:
        for mode in modes:
            for d in results[mode]["details"]:
                f.write(json.dumps(d) + "\n")
    print(f"\nDetails saved to {args.output}")


if __name__ == "__main__":
    main()
