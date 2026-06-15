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

MODEL_NAME = "Qwen/Qwen2.5-14B-Instruct"


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
        # Full bf16 -- no quantization. Small models (e.g. Qwen2.5-3B) fit easily
        # on an 80GB GPU and run faster un-quantized; logprob scoring is also
        # cleaner without 8-bit rounding.
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=torch.bfloat16,
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


def mine_candidates(question, context, k=5, existing=None, answer_type=None):
    """Candidate generation as an action: extract specific entities from the
    accumulated evidence C that could answer the question. Candidates are
    grounded in retrieved text, NOT sampled from parametric priors -- this is
    what lets obscure gold answers enter the state space.

    When answer_type is given, mining is conditioned on it (predictions flowing
    DOWN the hierarchy T -> s): only entities that are an instance of that type.
    """
    existing = existing or []
    avoid = ""
    if existing:
        avoid = (
            "Do NOT repeat any of these already-considered answers:\n"
            + "\n".join(f"- {c}" for c in existing)
            + "\nFind DIFFERENT specific entities.\n\n"
        )
    type_line = (
        f"Each candidate MUST be a {answer_type} (this is the kind of thing the "
        f"answer is).\n"
        if answer_type
        else ""
    )
    kind = answer_type if answer_type else "names, places, dates, titles"
    prompt = (
        f"You are answering a hard trivia question by extracting candidate "
        f"answers from web search evidence.\n"
        f"List up to {k} SPECIFIC entities ({kind}) "
        f"that actually appear in the evidence below and could plausibly be the "
        f"answer to the question.\n"
        f"Rules:\n"
        f"{type_line}"
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


# ---------------------------------------------------------------------------
# Hierarchical type latent  T -> s  (answer type above the answer)
#
# The answer type is a latent variable, not a one-shot extraction. We maintain
# a belief q(T|C) and infer it the same way as the answer: prior from the
# question + evidence fit (model selection). Predictions flow down (mining is
# type-conditioned); prediction-errors flow up (a type whose candidates misfit
# the evidence is down-weighted). See internals/active_inference.md.
# ---------------------------------------------------------------------------


def logsumexp(x):
    x = np.asarray(x, dtype=float)
    m = np.max(x)
    return float(m + np.log(np.sum(np.exp(x - m))))


def entropy_p(p):
    p = np.asarray(p, dtype=float)
    return float(-np.sum(p * np.log(p + 1e-10)))


def generate_types(question, m=3):
    """Sample candidate answer types T_1..T_M from the question."""
    prompt = (
        f"What KIND of thing is the answer to this question? "
        f"List {m} possible answer types as short labels "
        f"(e.g. 'city', \"person's name\", 'date', 'pair of football teams', "
        f"'organization', 'film title').\n"
        f"One per line, numbered 1-{m}. Just the short type label.\n\n"
        f"Question: {question}\n\n"
    )
    raw = generate(prompt, temperature=0.8)
    types = [t for t in _parse_numbered_list(raw) if len(t) < 60][:m]
    return types or ["the answer"]


def type_prior(question, type_label):
    """log p(T | question), length-normalized -- what the question asks for."""
    _, tokenizer = get_model()
    prefix = f"Question: {question}\n\nThe answer to this question is a"
    cand = " " + type_label + "."
    ntok = max(1, len(tokenizer.encode(cand, add_special_tokens=False)))
    return log_likelihood(prefix, cand) / ntok


def infer_type_belief(question, types, ptype, scores, lam=1.0):
    """q(T|C) ∝ p(T|question) · p(C|T).

    scores: length-normalized log q(s_i|C) for every pooled candidate.
    ptype:  the type label of each pooled candidate.
    Returns (qT, H_T, prior, fit).
    """
    prior = np.array([type_prior(question, T) for T in types])
    fit = np.full(len(types), -1e9)
    for i, T in enumerate(types):
        idx = [j for j in range(len(ptype)) if ptype[j] == T]
        if idx:
            fit[i] = logsumexp(scores[idx])
    log_qT = prior + lam * fit
    qT = softmax(log_qT)
    return qT, entropy_p(qT), prior, fit


def marginal_belief(types, ptype, scores, qT):
    """q(s|C) = Σ_T q(T|C) q(s|T,C). Returns per-candidate marginal probs."""
    q = np.zeros(len(ptype))
    for i, T in enumerate(types):
        idx = [j for j in range(len(ptype)) if ptype[j] == T]
        if not idx:
            continue
        w = softmax(scores[idx])
        for local, j in enumerate(idx):
            q[j] = qT[i] * w[local]
    s = q.sum()
    return q / s if s > 0 else q


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


def next_subquestion(question, known_facts, focus_constraint=None):
    """Pick the single most useful intermediate fact to resolve next.

    Used when escape mass stays high after regeneration -- the evidence (not the
    candidate set) is the bottleneck, so we resolve one hop of the chain. When a
    focus_constraint is given (the constraint no current candidate satisfies),
    the sub-question is directed at finding an entity that satisfies it.
    """
    facts = "\n".join(f"- {q} => {a}" for q, a in known_facts) or "(none yet)"
    focus = (
        f"Focus on finding an entity that satisfies THIS specific constraint, "
        f"which no current candidate satisfies:\n  {focus_constraint}\n\n"
        if focus_constraint
        else ""
    )
    prompt = (
        f"You are answering a hard multi-step question by resolving one "
        f"intermediate fact at a time.\n"
        f"Main question: {question}\n\n"
        f"Facts resolved so far:\n{facts}\n\n"
        f"{focus}"
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


# ---------------------------------------------------------------------------
# Constraint-grounded belief
#
# A BrowseComp question is a conjunction of constraints. Instead of scoring a
# candidate by raw answer-string logprob, we score it by how many constraints
# the evidence verifiably supports -- a product of per-constraint satisfaction
# probabilities. This (a) crushes famous-but-wrong entities that fail specific
# constraints, and (b) tells us which constraint no candidate satisfies, so
# foraging can be directed at it.
# ---------------------------------------------------------------------------


def extract_constraints(question, max_constraints=6):
    """Decompose the question into its individual factual constraints."""
    prompt = (
        f"Break this question into its individual factual constraints -- the "
        f"separate conditions the correct answer must satisfy.\n"
        f"List up to {max_constraints}, one per line, numbered. Each should be a "
        f"single checkable condition, phrased as a statement.\n\n"
        f"Question: {question}\n\n"
    )
    raw = generate(prompt, temperature=0.3)
    return _parse_numbered_list(raw)[:max_constraints]


def yes_no_prob(prompt):
    """P(Yes) from a single forward pass -- next-token Yes/No probability."""
    model, tokenizer = get_model()
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    input_ids = torch.tensor([ids], device=model.device)
    with torch.no_grad():
        logits = model(input_ids).logits[0, -1]
    lp = torch.log_softmax(logits, dim=-1)
    yes_id = tokenizer.encode(" Yes", add_special_tokens=False)[0]
    no_id = tokenizer.encode(" No", add_special_tokens=False)[0]
    p = softmax(np.array([lp[no_id].item(), lp[yes_id].item()]))
    return float(p[1])


def candidate_constraint_sat(candidate, context, constraints):
    """Vector of P(constraint_j satisfied | candidate, evidence)."""
    sat = np.zeros(len(constraints))
    for j, c in enumerate(constraints):
        prompt = (
            f"Evidence:\n{context}\n\n"
            f"Candidate answer: {candidate}\n"
            f"Constraint: {c}\n\n"
            f"Based on the evidence, does the candidate answer satisfy this "
            f"constraint? Answer Yes or No.\nAnswer:"
        )
        sat[j] = yes_no_prob(prompt)
    return sat


def constraint_belief(pool, context, constraints):
    """Returns (scores, sat_matrix, escape).

    scores      -- aggregate log-satisfaction Σ_j log p(c_j|s_i) per candidate
    sat_matrix  -- (n_candidates, n_constraints) satisfaction probabilities
    escape      -- 1 - (best candidate's mean satisfaction); high when no
                   candidate satisfies the constraints
    """
    eps = 1e-3
    sat = np.array([candidate_constraint_sat(c, context, constraints) for c in pool])
    scores = np.log(sat + eps).sum(axis=1)
    escape = 1.0 - float(sat.mean(axis=1).max()) if len(pool) else 1.0
    return scores, sat, escape


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


def mine_typed(question, context, types, k_per_type, pool, ptype, only=None):
    """Mine candidates per type (predictions flowing down T -> s) and append the
    new ones to the typed pool. `only` restricts to a subset of types. Returns
    the list of (candidate, type) added."""
    added = []
    for T in only if only is not None else types:
        for c in mine_candidates(
            question, context, k=k_per_type, existing=pool, answer_type=T
        ):
            if c not in pool:
                pool.append(c)
                ptype.append(T)
                added.append((c, T))
    return added


def cap_typed(pool, ptype, context, question, pool_cap):
    """Keep the pool_cap best candidates by length-normalized score, keeping the
    parallel type tags aligned."""
    if len(pool) <= pool_cap:
        return pool, ptype
    rs = score_candidates(pool, context, question)
    keep = sorted(np.argsort(rs)[::-1][:pool_cap])
    return [pool[i] for i in keep], [ptype[i] for i in keep]


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
    n_types=3,
    k_per_type=4,
    type_threshold=0.6,
    type_lam=1.0,
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

    # Hierarchical latent: infer candidate answer TYPES, then mine instances of
    # each type. Candidates are MINED from evidence (not sampled from priors),
    # and conditioned on the type (predictions flowing down T -> s).
    types = generate_types(question, m=n_types)
    trace["types"] = list(types)

    # Constraint decomposition: the conjunction of conditions the answer must
    # satisfy. Drives constraint-grounded scoring, escape, and directed search.
    constraints = extract_constraints(question)
    trace["constraints"] = list(constraints)

    pool, ptype = [], []
    mine_typed(question, context, types, k_per_type, pool, ptype)
    if not pool:
        # typed mining failed -> untyped mining, then prior-based candidates
        for c in mine_candidates(question, context, k=k):
            pool.append(c)
            ptype.append(types[0])
    if not pool:
        for c in generate_candidates(question, k=k, search_context=initial_evidence):
            pool.append(c)
            ptype.append(types[0])
    if not pool:
        return run_single_search(question, api_key), {"fallback": "no candidates"}
    trace["candidates"] = list(pool)

    regenerations = 0
    decompositions = 0
    real_searches = 0
    known_facts = []
    stale_regens = 0          # consecutive regenerations that failed to drop escape
    prev_escape = None
    last_was_regen = False
    step = 0
    max_steps = max_iterations + max_regen + max_decomp + 2

    def belief_state():
        """Recompute the full hierarchical belief over the current typed pool.

        When constraints exist, candidate scores are constraint-grounded
        (Σ_j log p(constraint_j | candidate, evidence)) and escape mass is
        constraint-based; otherwise fall back to answer-string logprob + the
        YES/NO adequacy probe. Returns sat (satisfaction matrix) for directing
        foraging at the weakest constraint.
        """
        if constraints:
            scores, sat, escape = constraint_belief(pool, context, constraints)
        else:
            scores = score_candidates(pool, context, question)
            sat = None
            escape = set_adequacy(pool, context, question)
        qT, H_T, _, _ = infer_type_belief(question, types, ptype, scores, lam=type_lam)
        qs = marginal_belief(types, ptype, scores, qT)
        return scores, escape, qT, H_T, qs, entropy_p(qs), sat

    def weakest_constraint(sat):
        """The constraint least satisfied by ANY candidate -- the one to forage
        for. Returns the constraint string, or None."""
        if sat is None or not constraints or sat.size == 0:
            return None
        return constraints[int(np.argmin(sat.max(axis=0)))]

    while step < max_steps and real_searches < max_iterations:
        step += 1
        scores, escape_mass, qT, H_T, qs, H_s, sat = belief_state()
        map_type = types[int(np.argmax(qT))]

        # Did the previous regeneration actually reduce the meta-belief? If not,
        # re-mining is exhausted -- the EVIDENCE is the bottleneck, not the set.
        if last_was_regen:
            if prev_escape is not None and escape_mass > prev_escape - 0.05:
                stale_regens += 1
            else:
                stale_regens = 0
        last_was_regen = False

        weak_c = weakest_constraint(sat)
        iteration = {
            "step": step,
            "escape_mass": round(escape_mass, 4),
            "H_answer": round(H_s, 4),
            "H_type": round(H_T, 4),
            "map_type": map_type,
            "n_candidates": len(pool),
            "type_belief": {types[i]: round(float(qT[i]), 4) for i in range(len(types))},
            "beliefs": {pool[j]: round(float(qs[j]), 4) for j in range(len(pool))},
        }
        if weak_c is not None:
            iteration["weakest_constraint"] = weak_c
            lead = int(np.argmax(qs))
            iteration["leader_sat"] = {
                constraints[j]: round(float(sat[lead][j]), 3)
                for j in range(len(constraints))
            }

        # --- META GATE: candidate set inadequate (escape mass high) ---
        if escape_mass > tau_regen:
            # (a) cheap first: re-mine current evidence (regenerate, expand-only).
            #     Type-uncertain -> re-mine across ALL types (resolve which type);
            #     type-confident -> re-mine instances of the MAP type only.
            if stale_regens < regen_patience and regenerations < max_regen:
                only = None if H_T > type_threshold else [map_type]
                added = mine_typed(
                    question, context, types, k_per_type, pool, ptype, only=only
                )
                if added:
                    pool[:], ptype[:] = cap_typed(
                        pool, ptype, context, question, pool_cap
                    )
                    regenerations += 1
                    last_was_regen = True
                    prev_escape = escape_mass
                    iteration["action"] = "regenerate"
                    iteration["regen_scope"] = (
                        "all_types" if only is None else f"map:{map_type}"
                    )
                    iteration["new_candidates"] = [c for c, _ in added]
                    trace["iterations"].append(iteration)
                    continue
                stale_regens = regen_patience  # nothing new -> regeneration is stale

            # (b) regeneration stale/exhausted: resolve one intermediate hop
            #     (decompose) to get genuinely NEW evidence
            if decompositions < max_decomp:
                subq = next_subquestion(question, known_facts, focus_constraint=weak_c)
                if subq:
                    ev, res = gather_evidence(subq, api_key, question=question)
                    fact = extract_fact(subq, ev)
                    context += (
                        f"\n\n---\nSub-question: {subq}\nResolved: {fact}\n"
                        f"Evidence:\n{ev}"
                    )
                    if fact and fact.lower() != "unknown":
                        known_facts.append((subq, fact))
                    added = mine_typed(question, context, types, k_per_type, pool, ptype)
                    if added:
                        pool[:], ptype[:] = cap_typed(
                            pool, ptype, context, question, pool_cap
                        )
                    decompositions += 1
                    real_searches += 1
                    stale_regens = 0      # new evidence may make regen useful again
                    prev_escape = None
                    iteration["action"] = "decompose"
                    iteration["subquestion"] = subq
                    iteration["resolved_fact"] = fact
                    iteration["new_candidates"] = [c for c, _ in added]
                    iteration["search_results"] = [
                        {"title": r["title"], "snippet": r["snippet"][:120]}
                        for r in res[:5]
                    ]
                    trace["iterations"].append(iteration)
                    continue
            # both regenerate and decompose exhausted -> fall through

        # --- CONVERGE: answer confident AND type confident AND set adequate ---
        if (
            H_s < threshold
            and H_T < type_threshold
            and escape_mass <= tau_regen
            and real_searches >= 1
        ):
            iteration["action"] = "converged"
            trace["iterations"].append(iteration)
            break

        # --- SEARCH: gather evidence within the current state space ---
        actions = generate_search_queries(question, context)
        if not actions:
            iteration["action"] = "no queries generated"
            trace["iterations"].append(iteration)
            break

        # select action with minimum EFE (ambiguity over the flat pool)
        G_values = [compute_efe(a, pool, context, question) for a in actions]
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

    # final answer -- argmax of the type-marginalized, constraint-grounded belief
    scores, escape_mass, qT, H_T, qs, H_s, sat = belief_state()
    winner_idx = int(np.argmax(qs))
    winner = pool[winner_idx]

    trace["final"] = {
        "H_answer": round(H_s, 4),
        "H_type": round(H_T, 4),
        "escape_mass": round(escape_mass, 4),
        "map_type": types[int(np.argmax(qT))],
        "winner_type": ptype[winner_idx],
        "type_belief": {types[i]: round(float(qT[i]), 4) for i in range(len(types))},
        "beliefs": {pool[j]: round(float(qs[j]), 4) for j in range(len(pool))},
        "winner": winner,
        "num_searches": len(searches),
        "num_regenerations": regenerations,
        "num_decompositions": decompositions,
        "known_facts": [{"q": q, "a": a} for q, a in known_facts],
    }
    if sat is not None and constraints:
        trace["final"]["winner_sat"] = {
            constraints[j]: round(float(sat[winner_idx][j]), 3)
            for j in range(len(constraints))
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
    parser.add_argument(
        "--n-types", type=int, default=3,
        help="Number of candidate answer types (hierarchical latent T)",
    )
    parser.add_argument(
        "--type-threshold", type=float, default=0.6,
        help="Type-entropy H[q(T|C)] below which the answer type is 'confident'",
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
                        n_types=args.n_types,
                        type_threshold=args.type_threshold,
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
