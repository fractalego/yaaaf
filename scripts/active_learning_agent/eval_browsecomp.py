"""
Evaluate epistemic foraging on BrowseComp.

Compares:
  - baseline: model answers directly (no search)
  - single_search: one brave search, then answer
  - foraging: full epistemic foraging loop with EFE action selection

Dataset: BrowseComp (1266 hard web-search questions, OpenAI)

Usage:
    python eval_browsecomp.py --n 20 --brave-key $BRAVE_API_KEY --mode all
    python eval_browsecomp.py --n 50 --brave-key $BRAVE_API_KEY --mode foraging
"""

import os
import sys
import json
import argparse
import time
import base64
import hashlib
import numpy as np
import requests
import torch
import pandas as pd
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen3.5-27B"


# ---------------------------------------------------------------------------
# BrowseComp decryption
# ---------------------------------------------------------------------------


def _derive_key(password, length):
    h = hashlib.sha256()
    h.update(password.encode())
    key = h.digest()
    return key * (length // len(key)) + key[: length % len(key)]


def decrypt(ciphertext_b64, canary):
    encrypted = base64.b64decode(ciphertext_b64)
    key = _derive_key(canary, len(encrypted))
    return bytes(a ^ b for a, b in zip(encrypted, key)).decode()


def load_browsecomp(path="browse_comp_test_set.csv"):
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "question": decrypt(r["problem"], r["canary"]),
                "answer": decrypt(r["answer"], r["canary"]),
                "topic": r["problem_topic"],
            }
        )
    return rows


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
        from transformers import BitsAndBytesConfig
        quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            quantization_config=quantization_config,
            device_map="cuda",
        )
        _model.eval()
        print("Model loaded.")
    return _model, _tokenizer


# ---------------------------------------------------------------------------
# LLM primitives
# ---------------------------------------------------------------------------


def generate(prompt, max_new_tokens=256, temperature=0.7):
    model, tokenizer = get_model()
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(text, return_tensors="pt", return_attention_mask=True).to(model.device)
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
    return "\n".join(f"- {r['title']}: {r['snippet']}" for r in results)


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
    results = brave_search(question, api_key, count=10)
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


def generate_candidates(question, k=5, search_context=None):
    if search_context:
        prompt = (
            f"Based on the following search results, generate {k} diverse possible "
            f"answers to the question below.\n"
            f"Each answer should be short and direct (a few words).\n"
            f"One per line, numbered 1-{k}.\n\n"
            f"Search results:\n{search_context}\n\n"
            f"Question: {question}\n\n"
        )
    else:
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
        f"You need to find the answer to a hard trivia question. "
        f"Based on the question and evidence so far, suggest 3 different "
        f"web search queries that would help narrow down the answer.\n"
        f"Focus on finding specific facts mentioned in the question.\n"
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


def run_foraging(question, api_key, threshold=0.5, max_iterations=5, k=5):
    trace = {"candidates": [], "iterations": [], "final": {}}

    # Phase 0: initial search to ground candidate generation
    # Summarise long questions into a short search query
    initial_query = generate(
        f"Write a 10-word web search query for this question.\n\n"
        f"Question: {question}\n\n"
        f"10-word query:",
        max_new_tokens=64,
        temperature=0.0,
    )
    # Strip thinking tags if present (Qwen3.5 thinking mode)
    if "</think>" in initial_query:
        initial_query = initial_query.split("</think>")[-1]
    initial_query = initial_query.split("\n")[0].strip().strip('"').strip("'")
    # Enforce Brave limits: 400 chars, 50 words
    words = initial_query.split()
    if len(words) > 15:
        initial_query = " ".join(words[:15])
    if len(initial_query) > 400:
        initial_query = initial_query[:400]
    if not initial_query:
        initial_query = " ".join(question.split()[:10])
    initial_results = brave_search(initial_query, api_key, count=10)
    initial_evidence = format_search_results(initial_results)
    trace["initial_search"] = {
        "query": initial_query,
        "num_results": len(initial_results),
        "results": [
            {"title": r["title"], "snippet": r["snippet"][:120]}
            for r in initial_results[:5]
        ],
    }

    # Generate candidates informed by search results
    candidates = generate_candidates(question, k=k, search_context=initial_evidence)
    if not candidates:
        return run_single_search(question, api_key), {"fallback": "no candidates"}

    trace["candidates"] = candidates

    context = f"---\nSearch: {initial_query}\nResults:\n{initial_evidence}"
    searches = [initial_query]

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

        # select action with minimum EFE
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

        # execute real search
        results = brave_search(best_action, api_key, count=10)
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
# Scoring (LLM-based, following BrowseComp's method)
# ---------------------------------------------------------------------------


def grade_answer_ollama(question, predicted, gold, ollama_url="http://localhost:11434", judge_model="qwen2.5:32b"):
    """Grade using a separate LLM via ollama as judge (avoids circular self-grading)."""
    prompt = (
        f"You are grading an answer. Check if the predicted answer is "
        f"essentially the same as the correct answer. Minor differences in "
        f"formatting, capitalization, or phrasing are OK.\n\n"
        f"Question: {question}\n"
        f"Correct answer: {gold}\n"
        f"Predicted answer: {predicted}\n\n"
        f"Is the predicted answer correct? Reply with ONLY 'yes' or 'no'."
    )
    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": judge_model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0, "num_predict": 8}},
            timeout=30,
        )
        return "yes" in resp.json().get("response", "").lower()
    except Exception:
        return False


def normalize(text):
    return text.strip().lower().rstrip(".")


def is_correct(predicted, gold):
    """Check correctness: normalized substring match with minimum length guard."""
    p = normalize(predicted)
    g = normalize(gold)
    if len(p) < 3 or len(g) < 3:
        return p == g
    return g in p or p in g


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global MODEL_NAME

    parser = argparse.ArgumentParser(description="Evaluate foraging on BrowseComp")
    parser.add_argument("--n", type=int, default=20, help="Number of questions")
    parser.add_argument("--offset", type=int, default=0, help="Start index")
    parser.add_argument("--brave-key", type=str, default=None)
    parser.add_argument(
        "--mode",
        choices=["baseline", "single_search", "foraging", "all"],
        default="all",
    )
    parser.add_argument("--model", type=str, default=MODEL_NAME)
    parser.add_argument(
        "--threshold", type=float, default=0.5, help="Entropy threshold"
    )
    parser.add_argument(
        "--max-iter", type=int, default=5, help="Max foraging iterations"
    )
    parser.add_argument("--output", type=str, default="browsecomp_results.jsonl")
    parser.add_argument(
        "--dataset", type=str, default="browse_comp_test_set.csv",
        help="Path to BrowseComp CSV",
    )
    parser.add_argument(
        "--topic", type=str, default=None,
        help="Filter by topic (e.g. 'Sports', 'Science & technology')",
    )
    args = parser.parse_args()

    MODEL_NAME = args.model

    api_key = args.brave_key or os.getenv("BRAVE_API_KEY")
    if not api_key and args.mode in ("single_search", "foraging", "all"):
        print("Error: --brave-key or BRAVE_API_KEY required for search modes")
        sys.exit(1)

    # load dataset
    print("Loading BrowseComp dataset...")
    all_questions = load_browsecomp(args.dataset)
    print(f"Total questions: {len(all_questions)}")

    if args.topic:
        all_questions = [q for q in all_questions if q["topic"] == args.topic]
        print(f"Filtered to topic '{args.topic}': {len(all_questions)}")

    subset = all_questions[args.offset : args.offset + args.n]
    print(f"Evaluating {len(subset)} questions (offset={args.offset})")

    modes = (
        ["baseline", "single_search", "foraging"]
        if args.mode == "all"
        else [args.mode]
    )

    results = {m: {"correct": 0, "total": 0, "details": []} for m in modes}

    for idx, example in enumerate(subset):
        question = example["question"]
        gold = example["answer"]
        topic = example["topic"]
        print(f"\n[{idx+1}/{len(subset)}] [{topic}] Q: {question[:120]}...")
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

            # score with both methods
            correct_str = is_correct(predicted, gold)
            correct_llm = grade_answer_ollama(question, predicted, gold)
            correct = correct_str or correct_llm

            results[mode]["correct"] += int(correct)
            results[mode]["total"] += 1

            detail = {
                "question": question,
                "gold": gold,
                "predicted": predicted,
                "correct": correct,
                "correct_string": correct_str,
                "correct_llm": correct_llm,
                "time": round(elapsed, 2),
                "mode": mode,
                "topic": topic,
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
