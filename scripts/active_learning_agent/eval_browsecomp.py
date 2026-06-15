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
import re
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
    # Brave rejects queries over ~50 words / 400 chars (HTTP 422). Guard here so
    # every call site is safe, not just the initial-query summarizer.
    words = query.split()
    if len(words) > 45:
        query = " ".join(words[:45])
    if len(query) > 380:
        query = query[:380]
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
# Page-body fetching + passage extraction
#
# BrowseComp answers live in page bodies, not 120-char snippets. We fetch the
# top result URLs, strip HTML, and keep only the passages whose keywords overlap
# the question -- so the answer-bearing region survives the context budget.
# ---------------------------------------------------------------------------

_page_cache = {}
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
N_FETCH = 3  # number of top result pages to fetch per search (0 = snippets only)


def fetch_page(url, timeout=10, max_chars=20000):
    if url in _page_cache:
        return _page_cache[url]
    text = ""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": _UA})
        ctype = resp.headers.get("content-type", "")
        if resp.ok and ("html" in ctype or "text" in ctype or not ctype):
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(
                ["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]
            ):
                tag.decompose()
            text = " ".join(soup.get_text(separator=" ", strip=True).split())[:max_chars]
    except Exception:
        text = ""
    _page_cache[url] = text
    return text


def extract_passages(text, query, max_passages=2, window=500):
    """Keep the highest keyword-overlap windows of a page."""
    if not text:
        return ""
    kws = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3}
    if not kws:
        return text[:window]
    chunks = [text[i : i + window] for i in range(0, len(text), window)]
    scored = []
    for ch in chunks:
        low = ch.lower()
        score = sum(1 for kw in kws if kw in low)
        if score:
            scored.append((score, ch))
    scored.sort(key=lambda x: -x[0])
    return " … ".join(ch for _, ch in scored[:max_passages])


def gather_evidence(query, api_key, question=None, count=10, n_fetch=None):
    """Search + fetch top page bodies. Returns (evidence_text, raw_results)."""
    if n_fetch is None:
        n_fetch = N_FETCH
    results = brave_search(query, api_key, count=count)
    parts = [format_search_results(results)]
    target = question or query
    for r in results[:n_fetch]:
        passages = extract_passages(fetch_page(r["url"]), target)
        if passages:
            parts.append(f"[{r['title']}] {passages}")
    return "\n".join(parts), results


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
    evidence, results = gather_evidence(question, api_key, question=question)

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


# ---------------------------------------------------------------------------
# Sentinel + evidence-mined candidates (structure learning)
# ---------------------------------------------------------------------------

# s_0: the catch-all hypothesis "the answer is not in this list". Scored with
# the same logprob machinery as any real candidate; its posterior mass
# q(s_0|C) is the meta-belief that the candidate set needs to be regenerated.
SENTINEL = "None of the above; the answer is not present in this list."

# Refusal-type strings must never be real candidates -- they are exactly what
# the sentinel is for. If the model emits one anyway, drop it.
_REFUSAL_MARKERS = (
    "not found", "not in", "unavailable", "no such", "cannot determine",
    "insufficient", "missing", "not provided", "not mentioned", "does not exist",
    "no match", "not identified", "unknown", "incomplete", "not listed",
    "no answer", "fictional", "data not", "results mismatch", "not enough",
)


def is_refusal(text):
    t = text.strip().lower()
    return any(m in t for m in _REFUSAL_MARKERS)


def _parse_numbered_list(raw):
    items = []
    for line in raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            text = line.split(".", 1)[-1].strip() if "." in line[:3] else line
            text = text.split(")", 1)[-1].strip() if ")" in text[:3] else text
            if text:
                items.append(text)
    return items


def mine_candidates(question, context, k=5, existing=None):
    """Candidate generation as an action: extract specific entities from the
    accumulated evidence C that could answer the question. Candidates are
    grounded in retrieved text, NOT sampled from parametric priors -- this is
    what lets obscure gold answers enter the state space.
    """
    existing = existing or []
    avoid = ""
    if existing:
        avoid = (
            "Do NOT repeat any of these already-considered answers:\n"
            + "\n".join(f"- {c}" for c in existing)
            + "\nFind DIFFERENT specific entities.\n\n"
        )
    prompt = (
        f"You are answering a hard trivia question by extracting candidate "
        f"answers from web search evidence.\n"
        f"List up to {k} SPECIFIC entities (exact names, places, dates, titles) "
        f"that actually appear in the evidence below and could plausibly be the "
        f"answer to the question.\n"
        f"Rules:\n"
        f"- Only list things actually mentioned in the evidence.\n"
        f"- Be specific and exact (full names, exact titles/dates).\n"
        f"- Do NOT invent answers. Do NOT write 'not found' or similar.\n"
        f"- One per line, numbered 1-{k}. Just the entity, no explanation.\n\n"
        f"{avoid}"
        f"Question: {question}\n\n"
        f"Evidence:\n{context}\n\n"
    )
    raw = generate(prompt, temperature=0.7)
    candidates = [c for c in _parse_numbered_list(raw) if not is_refusal(c)]
    return candidates[:k]


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
    """Length-normalized log-likelihood (mean per-token logprob).

    Summed logprob is length-biased: a 1-token candidate ("Italy") always beats
    a multi-token one regardless of fit. Dividing by token count makes candidates
    of different lengths comparable in the softmax.
    """
    _, tokenizer = get_model()
    prefix = f"Question: {question}\n\nEvidence:\n{context}\n\nAnswer:"
    scores = np.zeros(len(candidates))
    for i, c in enumerate(candidates):
        ntok = max(1, len(tokenizer.encode(" " + c, add_special_tokens=False)))
        scores[i] = log_likelihood(prefix, " " + c) / ntok
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
    actions = _parse_numbered_list(raw)[:3]
    if not actions:
        # parse failure -> don't kill the question; fall back to a keyword query
        actions = [" ".join(question.split()[:12])]
    return actions


def next_subquestion(question, known_facts):
    """Pick the single most useful intermediate fact to resolve next.

    Used when escape mass stays high after regeneration -- the evidence (not the
    candidate set) is the bottleneck, so we resolve one hop of the chain.
    """
    facts = "\n".join(f"- {q} => {a}" for q, a in known_facts) or "(none yet)"
    prompt = (
        f"You are answering a hard multi-step question by resolving one "
        f"intermediate fact at a time.\n"
        f"Main question: {question}\n\n"
        f"Facts resolved so far:\n{facts}\n\n"
        f"What is the SINGLE most useful next intermediate fact to look up that "
        f"moves toward the final answer? Phrase it as one specific, searchable "
        f"sub-question. Output only the sub-question, nothing else.\n\n"
    )
    raw = generate(prompt, max_new_tokens=48, temperature=0.5)
    if "</think>" in raw:
        raw = raw.split("</think>")[-1]
    subq = raw.strip().split("\n")[0].strip().strip('"').strip("'")
    return subq


def extract_fact(subquestion, evidence):
    """Resolve a sub-question from evidence to a short entity, or 'unknown'."""
    prompt = (
        f"Based ONLY on the evidence, answer the sub-question with a short, "
        f"specific answer (a name, date, or short phrase). If the evidence does "
        f"not answer it, reply exactly 'unknown'.\n\n"
        f"Sub-question: {subquestion}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Answer:"
    )
    return generate(prompt, max_new_tokens=32, temperature=0.0).strip()


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


def set_adequacy(candidates, context, question):
    """Meta-belief escape_mass = P(answer NOT among candidates | evidence).

    A single-token YES/NO probe instead of scoring the s_0 sentinel *string*.
    A sentinel answer-string is ~12 tokens and, under summed (or even averaged)
    logprob, cannot compete with 1-3 token candidates -- so q(s_0|C) was pinned
    at 0 and the gate never fired. The YES/NO probe reads the meta-belief
    directly from a single next-token distribution, free of length bias.
    """
    cand_list = "\n".join(f"- {c}" for c in candidates)
    prompt = (
        f"Question: {question}\n\n"
        f"Evidence:\n{context}\n\n"
        f"Candidate answers:\n{cand_list}\n\n"
        f"Based ONLY on the evidence above, is the correct answer present among "
        f"the candidate answers? Answer YES or NO.\nAnswer:"
    )
    ll_yes = log_likelihood(prompt, " YES")
    ll_no = log_likelihood(prompt, " NO")
    p = softmax(np.array([ll_no, ll_yes]))
    return float(p[0])  # escape mass = P(NO)


def cap_pool(candidates, context, question, pool_cap):
    """Keep the pool_cap most-believed candidates (by length-normalized score)."""
    if len(candidates) <= pool_cap:
        return candidates
    rs = score_candidates(candidates, context, question)
    keep = np.argsort(rs)[::-1][:pool_cap]
    return [candidates[i] for i in sorted(keep)]


def score_with_sentinel(candidates, context, question):
    """Returns (real_scores, escape_mass, H).

    real_scores  -- length-normalized log p(s_i|C) for the real candidates
    escape_mass  -- P(answer not in set | C), the meta-belief gating regeneration
    H            -- entropy of the belief over real candidates only
    """
    real_scores = score_candidates(candidates, context, question)
    escape_mass = set_adequacy(candidates, context, question)
    H = float(entropy(real_scores))
    return real_scores, escape_mass, H


def run_foraging(
    question,
    api_key,
    threshold=0.5,
    max_iterations=5,
    k=5,
    tau_regen=0.4,
    max_regen=3,
    max_decomp=3,
    regen_patience=1,
    pool_cap=12,
):
    trace = {"candidates": [], "iterations": [], "final": {}}

    # Phase 0: initial search to seed the evidence corpus.
    # Summarise long questions into a short search query.
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
    initial_evidence, initial_results = gather_evidence(
        initial_query, api_key, question=question
    )
    trace["initial_search"] = {
        "query": initial_query,
        "num_results": len(initial_results),
        "results": [
            {"title": r["title"], "snippet": r["snippet"][:120]}
            for r in initial_results[:5]
        ],
    }

    context = f"---\nSearch: {initial_query}\nResults:\n{initial_evidence}"
    searches = [initial_query]

    # Candidates are MINED from the evidence, not sampled from priors.
    candidates = mine_candidates(question, context, k=k)
    if not candidates:
        # mining parse failed -> keep the loop alive with prior-based candidates
        # (the regeneration gate will replace them once evidence improves)
        candidates = generate_candidates(question, k=k, search_context=initial_evidence)
    if not candidates:
        return run_single_search(question, api_key), {"fallback": "no candidates"}
    trace["candidates"] = list(candidates)

    regenerations = 0
    decompositions = 0
    real_searches = 0
    known_facts = []
    stale_regens = 0          # consecutive regenerations that failed to drop escape
    prev_escape = None
    last_was_regen = False
    step = 0
    max_steps = max_iterations + max_regen + max_decomp + 2

    while step < max_steps and real_searches < max_iterations:
        step += 1
        real_scores, escape_mass, H = score_with_sentinel(
            candidates, context, question
        )
        p = softmax(real_scores)

        # Did the previous regeneration actually reduce the meta-belief? If not,
        # re-mining is exhausted -- the EVIDENCE is the bottleneck, not the set.
        if last_was_regen:
            if prev_escape is not None and escape_mass > prev_escape - 0.05:
                stale_regens += 1
            else:
                stale_regens = 0
        last_was_regen = False

        iteration = {
            "step": step,
            "escape_mass": round(escape_mass, 4),
            "entropy": round(H, 4),
            "n_candidates": len(candidates),
            "beliefs": {c: round(float(p[i]), 4) for i, c in enumerate(candidates)},
            "log_scores": {
                c: round(float(real_scores[i]), 2) for i, c in enumerate(candidates)
            },
        }

        # --- META GATE: candidate set inadequate (escape mass high) ---
        if escape_mass > tau_regen:
            # (a) cheap first: re-mine current evidence (regenerate, expand-only)
            if stale_regens < regen_patience and regenerations < max_regen:
                new = [
                    c
                    for c in mine_candidates(question, context, k=k, existing=candidates)
                    if c not in candidates
                ]
                if new:
                    candidates = cap_pool(
                        candidates + new, context, question, pool_cap
                    )
                    regenerations += 1
                    last_was_regen = True
                    prev_escape = escape_mass
                    iteration["action"] = "regenerate"
                    iteration["new_candidates"] = new
                    trace["iterations"].append(iteration)
                    continue
                stale_regens = regen_patience  # nothing new -> regeneration is stale

            # (b) regeneration stale/exhausted: resolve one intermediate hop
            #     (decompose) to get genuinely NEW evidence
            if decompositions < max_decomp:
                subq = next_subquestion(question, known_facts)
                if subq:
                    ev, res = gather_evidence(subq, api_key, question=question)
                    fact = extract_fact(subq, ev)
                    context += (
                        f"\n\n---\nSub-question: {subq}\nResolved: {fact}\n"
                        f"Evidence:\n{ev}"
                    )
                    if fact and fact.lower() != "unknown":
                        known_facts.append((subq, fact))
                    new = [
                        c
                        for c in mine_candidates(
                            question, context, k=k, existing=candidates
                        )
                        if c not in candidates
                    ]
                    if new:
                        candidates = cap_pool(
                            candidates + new, context, question, pool_cap
                        )
                    decompositions += 1
                    real_searches += 1
                    stale_regens = 0      # new evidence may make regen useful again
                    prev_escape = None
                    iteration["action"] = "decompose"
                    iteration["subquestion"] = subq
                    iteration["resolved_fact"] = fact
                    iteration["new_candidates"] = new
                    iteration["search_results"] = [
                        {"title": r["title"], "snippet": r["snippet"][:120]}
                        for r in res[:5]
                    ]
                    trace["iterations"].append(iteration)
                    continue
            # both regenerate and decompose exhausted -> fall through

        # --- CONVERGE: set adequate, confident, and we actually foraged ---
        if H < threshold and escape_mass <= tau_regen and real_searches >= 1:
            iteration["action"] = "converged"
            trace["iterations"].append(iteration)
            break

        # --- SEARCH: gather evidence within the current state space ---
        actions = generate_search_queries(question, context)
        if not actions:
            iteration["action"] = "no queries generated"
            trace["iterations"].append(iteration)
            break

        # select action with minimum EFE (ambiguity over real candidates)
        G_values = [compute_efe(a, candidates, context, question) for a in actions]
        best_idx = int(np.argmin(G_values))
        best_action = actions[best_idx]
        searches.append(best_action)

        iteration["action"] = "search"
        iteration["candidate_queries"] = [
            {"query": a, "G": round(float(G_values[i]), 4)}
            for i, a in enumerate(actions)
        ]
        iteration["selected_query"] = best_action
        iteration["selected_G"] = round(float(G_values[best_idx]), 4)

        evidence, results = gather_evidence(best_action, api_key, question=question)
        context += f"\n\n---\nSearch: {best_action}\nResults:\n{evidence}"
        real_searches += 1

        iteration["search_results"] = [
            {"title": r["title"], "snippet": r["snippet"][:120]}
            for r in results[:5]
        ]
        iteration["num_results"] = len(results)
        trace["iterations"].append(iteration)

    # final scoring -- argmax over REAL candidates only (never the sentinel)
    real_scores, escape_mass, H = score_with_sentinel(candidates, context, question)
    p = softmax(real_scores)
    winner_idx = int(np.argmax(real_scores))
    winner = candidates[winner_idx]

    trace["final"] = {
        "entropy": round(H, 4),
        "escape_mass": round(escape_mass, 4),
        "beliefs": {c: round(float(p[i]), 4) for i, c in enumerate(candidates)},
        "log_scores": {
            c: round(float(real_scores[i]), 2) for i, c in enumerate(candidates)
        },
        "winner": winner,
        "num_searches": len(searches),
        "num_regenerations": regenerations,
        "num_decompositions": decompositions,
        "known_facts": [{"q": q, "a": a} for q, a in known_facts],
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
        "--max-iter", type=int, default=5, help="Max foraging (search) iterations"
    )
    parser.add_argument(
        "--tau-regen", type=float, default=0.4,
        help="Escape-mass threshold q(s_0|C) above which candidates are regenerated",
    )
    parser.add_argument(
        "--max-regen", type=int, default=3,
        help="Max candidate-regeneration actions per question",
    )
    parser.add_argument(
        "--n-fetch", type=int, default=3,
        help="Page bodies to fetch per search (0 = snippets only)",
    )
    parser.add_argument(
        "--max-decomp", type=int, default=3,
        help="Max multi-hop decomposition steps per question",
    )
    parser.add_argument(
        "--regen-patience", type=int, default=1,
        help="Regenerations to try before switching to decomposition",
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

    global N_FETCH
    N_FETCH = args.n_fetch

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
                        tau_regen=args.tau_regen,
                        max_regen=args.max_regen,
                        max_decomp=args.max_decomp,
                        regen_patience=args.regen_patience,
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
