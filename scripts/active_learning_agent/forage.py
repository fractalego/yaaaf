"""
Epistemic foraging agent -- minimal implementation with real logprobs.

Implements the active inference loop over finite answer candidates:

    generate candidates -> score (logprobs) -> select action -> observe -> update

Quantities:
    s        hidden state (candidate answers)
    q(s|C)   belief = softmax of log-likelihoods of each candidate given context
    H[q]     entropy of belief
    G(a)     expected free energy of action a
    a*       argmin_a G(a)

Stops when H[q(s|C)] < threshold.
"""

import sys
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "google/gemma-3-4b-it"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def load_model(model_name):
    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.float16,
        device_map="auto",
    )
    model.eval()
    print("Model loaded.")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Core: token-level log-likelihood
# ---------------------------------------------------------------------------


def log_likelihood(model, tokenizer, context, candidate):
    """Compute log p(candidate | context) from actual token logprobs.

    Returns the sum of log-probabilities of each candidate token
    conditioned on the context + all preceding candidate tokens.
    """
    context_ids = tokenizer.encode(context, add_special_tokens=False)
    full_ids = tokenizer.encode(context + candidate, add_special_tokens=False)
    candidate_start = len(context_ids)

    if candidate_start >= len(full_ids):
        return -1e6  # candidate added no tokens

    input_ids = torch.tensor([full_ids], device=model.device)

    with torch.no_grad():
        logits = model(input_ids).logits  # (1, seq_len, vocab)

    log_probs = torch.log_softmax(logits[0], dim=-1)

    total = 0.0
    for i in range(candidate_start, len(full_ids)):
        token_id = full_ids[i]
        total += log_probs[i - 1, token_id].item()

    return total


# ---------------------------------------------------------------------------
# Generation helper
# ---------------------------------------------------------------------------


def generate(model, tokenizer, prompt, max_new_tokens=256, temperature=0.7):
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
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Belief state
# ---------------------------------------------------------------------------


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def entropy(log_scores):
    p = softmax(log_scores)
    return -np.sum(p * np.log(p + 1e-10))


# ---------------------------------------------------------------------------
# Step 1: generate candidate answers  s_1 ... s_K
# ---------------------------------------------------------------------------


def generate_candidates(model, tokenizer, query, k=5):
    prompt = (
        f"Given this question, generate {k} diverse possible answers.\n"
        f"Each answer should be a short, direct response (1-2 sentences).\n"
        f"Output one per line, numbered 1-{k}.\n\n"
        f"Question: {query}\n\n"
    )
    raw = generate(model, tokenizer, prompt, temperature=0.9)
    candidates = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            text = line.split(".", 1)[-1].strip() if "." in line[:3] else line
            if text:
                candidates.append(text)
    return candidates[:k]


# ---------------------------------------------------------------------------
# Step 2: score candidates  log q(s_i | C)   (real logprobs)
# ---------------------------------------------------------------------------


def score_candidates(model, tokenizer, candidates, context, query):
    """Compute log p(s_i | C) for each candidate using token-level logprobs."""
    prompt_prefix = f"Question: {query}\n\nEvidence:\n{context}\n\nAnswer:"

    scores = np.zeros(len(candidates))
    for i, c in enumerate(candidates):
        scores[i] = log_likelihood(model, tokenizer, prompt_prefix, " " + c)

    return scores


# ---------------------------------------------------------------------------
# Step 3: generate candidate actions
# ---------------------------------------------------------------------------


def generate_actions(model, tokenizer, query, context):
    prompt = (
        f"Given this question and evidence so far, suggest 3 different "
        f"web search queries that would help find the answer.\n"
        f"One per line, numbered 1-3.\n\n"
        f"Question: {query}\n"
        f"Evidence: {context if context else '(none yet)'}\n\n"
    )
    raw = generate(model, tokenizer, prompt, temperature=0.7)
    actions = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            text = line.split(".", 1)[-1].strip() if "." in line[:3] else line
            if text:
                actions.append(text)
    return actions[:3]


# ---------------------------------------------------------------------------
# Step 4: expected free energy  G(a)
#
# G(a) = E_{q(o|a)} [ H[q(s|o,a)] ]  +  D_KL[ q(o|a) || p~(o) ]
#         ambiguity                        risk (omitted for now)
#
# Single-sample approximation for E_{q(o|a)}.
# ---------------------------------------------------------------------------


def predict_observation(model, tokenizer, action, context):
    """q(o|a) -- LLM as world model: predict what action would return."""
    prompt = (
        f'If I search for: "{action}"\n\n'
        f"Summarise the expected results in 2-3 sentences.\n\n"
    )
    return generate(model, tokenizer, prompt, max_new_tokens=128, temperature=0.5)


def compute_efe(model, tokenizer, action, candidates, context, query):
    """G(a) for a single candidate action."""
    o_predicted = predict_observation(model, tokenizer, action, context)

    updated_context = f"{context}\n\n{o_predicted}" if context else o_predicted
    updated_scores = score_candidates(
        model, tokenizer, candidates, updated_context, query
    )

    ambiguity = entropy(updated_scores)
    return ambiguity


# ---------------------------------------------------------------------------
# Step 5: execute action (simulated)
# ---------------------------------------------------------------------------


def execute_action(model, tokenizer, action):
    """Simulate search. Swap this for brave_search in real use."""
    prompt = (
        f'Simulate realistic search results for: "{action}"\n'
        f"Provide 3-5 items with titles and short snippets.\n\n"
    )
    return generate(model, tokenizer, prompt, max_new_tokens=256, temperature=0.3)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def forage(model, tokenizer, query, threshold=0.5, max_iterations=5, k=5):
    candidates = generate_candidates(model, tokenizer, query, k=k)
    print(f"\nCandidates:")
    for i, c in enumerate(candidates):
        print(f"  s_{i}: {c}")

    context = ""

    for t in range(max_iterations):
        scores = score_candidates(model, tokenizer, candidates, context, query)
        H = entropy(scores)
        p = softmax(scores)

        print(f"\n--- t={t}  H={H:.3f} ---")
        for i, c in enumerate(candidates):
            print(f"  q(s_{i}|C) = {p[i]:.3f}  [{scores[i]:.1f}]  {c[:60]}")

        if H < threshold:
            winner = candidates[np.argmax(scores)]
            print(f"\nConverged (H={H:.3f} < {threshold}). Answer: {winner}")
            return winner

        actions = generate_actions(model, tokenizer, query, context)
        print(f"Candidate actions: {actions}")

        G_values = []
        for a in actions:
            G = compute_efe(model, tokenizer, a, candidates, context, query)
            G_values.append(G)
            print(f"  G({a[:50]}) = {G:.3f}")

        best_a = actions[np.argmin(G_values)]
        print(f"Selected: {best_a}")

        observation = execute_action(model, tokenizer, best_a)
        context += f"\n\n---\nSearch: {best_a}\nResult: {observation}"

    scores = score_candidates(model, tokenizer, candidates, context, query)
    winner = candidates[np.argmax(scores)]
    print(f"\nMax iterations. H={entropy(scores):.3f}. Answer: {winner}")
    return winner


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    model, tokenizer = load_model(MODEL_NAME)

    query = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "What is the most energy-efficient programming language?"
    )

    print(f"Query: {query}")
    answer = forage(model, tokenizer, query)
    print(f"\nFinal answer: {answer}")
