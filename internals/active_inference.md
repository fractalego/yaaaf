# Active Inference in YAAAF

A running document exploring epistemic foraging and hierarchical models within this codebase.

---

## Epistemic Foraging

Epistemic foraging is the idea that an agent should actively seek information to reduce its uncertainty, not just execute a fixed plan. Rather than issuing one query and moving on, a foraging agent monitors how much it still doesn't know after each action, and continues probing the environment until its beliefs are sufficiently confident. In active inference terms, the agent selects actions that minimise *expected* free energy — which includes not just "doing the right thing" but also "learning what the right thing is". The practical upshot: search, retrieval, and planning steps become iterative loops that terminate on an epistemic criterion (low uncertainty) rather than a fixed budget.

---

## Hierarchical Models

Hierarchical models in active inference describe a system where beliefs are maintained at multiple levels of abstraction simultaneously, each level predicting the behaviour of the level below and receiving prediction errors back. The top level holds slow-changing, abstract beliefs (e.g. "what kind of task is this?"); lower levels hold fast-changing, concrete beliefs (e.g. "which SQL row is relevant?"). Errors propagate upward; predictions propagate downward. In YAAAF, this maps naturally onto the existing hierarchy: OrchestratorAgent (goal level) → PlannerAgent (workflow level) → individual agents (operation level). Currently these levels communicate only through hard failures and replanning; a hierarchical model would introduce graded, continuous feedback between levels.

---

## Where Does Foraging Live in YAAAF?

The current YAAAF model is feed-forward: goal → plan → execute → (replan only on hard failure). Each agent fires once and produces an artifact. The plan is the only place where "what to do next" is decided, and it is decided upfront.

Epistemic foraging breaks that: an agent should not commit to a result until it has enough information. There are three candidate sites where the foraging loop could live:

**Option 1 — Inside a single agent**: `brave_search` fires, evaluates its own results, decides if it learned enough, and re-queries with refined terms. Self-contained. Does not require changing the planner or workflow executor at all.

**Option 2 — At the workflow level via `loop`**: The existing `loop` construct supports iterative execution with an exit condition. A foraging loop could be: search → assess coverage → exit if covered, else refine and repeat. The exit condition becomes the epistemic criterion. The loop is visible in the YAML and can be constructed by the planner.

**Option 3 — At the planner level**: Before committing to a full plan, the planner issues cheap exploratory steps ("what is in the database?", "does this URL exist?") and revises the plan based on what it finds. The most ambitious option and the most hierarchical.

Open questions before implementing any of these:
- **What is the epistemic criterion?** How does the agent know it has "enough"? Candidates: LLM-as-judge scoring its own results, embedding overlap between successive queries, an explicit coverage checklist.
- **Transparency**: should foraging be hidden inside an agent (Option 1) or explicit in the workflow YAML so the planner can reason about it (Option 2)?

---

## Option 1: Foraging Inside a Single Agent

YAAAF already does a form of foraging: the orchestrator replans on hard failure, agents retry on bad outputs. But this is reactive — it only iterates when something breaks. True epistemic foraging is proactive: the agent has an explicit model of its own uncertainty and acts to reduce it *before* committing to a result.

| | Current YAAAF | Epistemic foraging |
|---|---|---|
| When does it iterate? | After hard failure | Before uncertainty is too high |
| What drives the next action? | Error message / validation feedback | Expected information gain |
| Does the agent know what it doesn't know? | No | Yes — it has a belief state |

The novel contribution is not the loop — it is the **uncertainty representation**.

---

## Formalising Epistemic Foraging with LLM Quantities

### Setup

- `s` — hidden state: the true answer the user is after (latent, never directly observed)
- `o` — observations: search results, page content, anything the agent receives
- `a` — actions: which query to fire, which URL to visit, or stop
- `C` — accumulated context: all observations collected so far

### The belief

The agent's belief is `q(s|C)` — "given what I have seen so far, what is the answer?"

With an LLM, this is literally `p_LLM(answer_tokens | context)`. The logit distribution over answer tokens *is* the belief distribution. There is no separate belief module — the LLM's conditional distribution is the posterior.

### Perception: minimise variational free energy F w.r.t. q

```
F(q) = D_KL[ q(s) || p(s|o) ]
     = D_KL[ q(s) || p(s) ] - E_q[ ln p(o|s) ]
       complexity              accuracy
```

With an LLM, this step is effectively free. Appending new observations to the context window and running forward is in-context learning. The key insight: **in-context learning is variational inference**. When the LLM conditions on accumulated observations, its output distribution `p_LLM(s|C)` is already the (approximately) optimised posterior:

```
q*(s) ≈ p_LLM(s | C)
```

No explicit optimisation loop over q is needed — the transformer's forward pass does it.

### Action selection: minimise expected free energy G w.r.t. a

The agent picks `a* = argmin_a G(a)` where:

```
G(a) = E_{q(o|a)} [ H[q(s | o, a)] ]  +  D_KL[ q(o|a) || p~(o) ]
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^         ^^^^^^^^^^^^^^^^^^^^^^^^
       ambiguity                           risk (pragmatic value)
```

Where:
- `H[q(s|o,a)]` — entropy of the posterior *after* updating with observation o from action a. "After I act and observe, how uncertain am I still?"
- `q(o|a)` — predicted observations: "what do I expect to see if I take action a?" The LLM acts as a world model here.
- `p~(o)` — preferred observations: ones that would constitute a complete, confident answer.

### Computing G(a) with an LLM — the full computation

For each candidate action `a_i`:

1. **Predict observations**: use the LLM as a world model to sample or estimate what the action would return.
   ```
   o_predicted ~ q(o|a_i) = p_LLM(observation | C, "if I execute a_i, I would see:")
   ```

2. **Update beliefs**: append predicted observation to context, compute the new posterior.
   ```
   q(s|o_predicted, a_i) = p_LLM(answer | C + o_predicted)
   ```

3. **Measure remaining uncertainty**: compute entropy of the updated posterior from logits.
   ```
   H[q(s|o_predicted, a_i)] = - sum_s q(s|o_predicted, a_i) * ln q(s|o_predicted, a_i)
   ```

4. **Average over predicted observations** to get the ambiguity term.

5. **Compute risk term**: how far predicted observations are from preferred observations.

6. **Sum** to get `G(a_i)`.

Select `a* = argmin_i G(a_i)`.

Cost: at minimum 2 LLM forward passes per candidate action per iteration (one for predicting observations, one for computing posterior entropy). This is expensive but gives actual numerical quantities to reason about.

### Open question: what is s concretely?

The hidden state `s` — the thing the agent has beliefs over — needs a concrete representation to compute entropies from logits. Options:
- **Free-form token sequence**: `s` is the full answer string. Entropy is computed from the token-level logit distribution. High entropy = model is unsure how to phrase the answer = it does not know enough yet.
- **Finite answer candidates**: discretise `s` into a set of candidate answers. Compute `q(s_i|C)` for each candidate using constrained generation. Entropy over this discrete set is clean and interpretable.
- **Binary sufficient/insufficient**: collapse `s` to a single bit. Use logits of YES/NO to compute `H[q(s|C)]`. Cheapest but loses all structure.

We go with **finite answer candidates**.

---

## Finite Candidates: Structure

The hidden state is discretised: `s in {s_1, ..., s_K}`. Each `s_i` is a short candidate answer string, sampled from the LLM at high temperature at the start.

The belief `q(s|C)` is a categorical distribution over K candidates. To score each candidate, we compute log-likelihood of the candidate string under the LLM conditioned on accumulated context:

```
log q(s_i | C) = sum_t log p_LLM(token_t | C, tokens_<t)    for tokens in s_i
```

Then `q(s|C) = softmax(log q(s_1|C), ..., log q(s_K|C))`.

Entropy is trivial: `H = -sum_i q(s_i|C) * ln q(s_i|C)`.

### Regeneration question

If you regenerate candidates mid-loop, the state space changes — old `q(s)` scores become meaningless. Options:
1. **Fixed upfront** — sample K at high temperature, hope truth is covered. Simplest.
2. **Expand only** — add candidates, never remove. Preserves existing beliefs, set grows.
3. **Full regeneration** — regenerate and try to map old beliefs onto new candidates. Messy.

For the first implementation: fixed candidates. **Superseded** — see "Candidate Generation as an Action" below. Fixed candidates proved to be the dominant failure mode on BrowseComp (gold answer in the candidate set 0/10), so we adopted **expand-only** regeneration driven by a meta-belief.

### What is the final output?

The winning candidate `s* = argmax_i q(s_i|C)` after convergence. Not an artifact — just a string. A synthesis step could follow, but the foraging loop itself just picks the best candidate.

### Implementation

Minimal loop in `scripts/active_learning_agent/forage.py`. Scoring uses actual token-level log-likelihoods via a local model (`google/gemma-3-4b-it`). The model is loaded via transformers and used both for generation (candidates, actions, predicted observations) and for scoring (forward pass + logprob extraction).

### How web search fits into the loop

Web search is NOT a tool call. The LLM does not "decide" to search. The loop structure is fixed:

```
generate K candidate answers (once)
loop:
    score candidates via logprobs → q(s|C)
    if H[q] < threshold → stop, return best candidate
    LLM generates 3 candidate search queries (text strings)
    for each query:
        LLM predicts what results would look like → q(o|a)
        score candidates against predicted results → H[q(s|o,a)]
        G(a) = H[q(s|o,a)]   (ambiguity only, risk omitted)
    pick query with lowest G(a)
    call Brave Search API with that query → real observation
    append results to context C
    go to top of loop
```

The search is always executed — one per iteration. The only decision is WHICH query to run (minimising EFE). The stopping criterion is the entropy check at the top.

**Simplifications vs full active inference:**
- Action space is "which search query" only. Does not include "stop" as an explicit action with its own G(a) — stopping is handled by the threshold.
- Does not include "visit a URL" or "reformulate question" as actions.
- Single sample approximation for E_{q(o|a)} — we predict one observation, not a distribution.
- Risk term D_KL[q(o|a) || p~(o)] is omitted. Only the ambiguity term is computed.
- Candidates are fixed upfront — no expansion or regeneration.

---

## Candidate Generation as an Action (Structure Learning)

The fixed-candidate loop above has a structural ceiling: the answer is
`s* = argmax_i q(s_i|C)` over a set fixed before evidence arrives. If the gold
answer is not in `{s_1...s_K}`, accuracy is bounded at 0 no matter how good the
search. On BrowseComp this is the dominant failure — gold is in the set 0/10,
because the answers are deliberately obscure and the model's priors generate
plausible-but-wrong famous entities (see the experiment log).

The fix is to give the agent uncertainty not just *within* the generative model
(which `s_i`) but *about* the model itself (whether the candidate set is even
adequate). In active-inference terms this is **structure learning / Bayesian
model expansion**: some actions change the hypothesis space, not just the belief
over a fixed one. Concretely, **candidate generation becomes an action** the
agent can select, alongside search.

### The meta-belief: escape mass q(s₀|C)

Add a catch-all sentinel candidate to the set:

```
s_0 = "None of the above; the answer is not present in this list."
```

`s_0` is scored with the *same* token-level logprob machinery as any real
candidate — it is just one extra row in the softmax:

```
q(s_i | C) = softmax(log p_LLM(s_0|C), log p_LLM(s_1|C), ..., log p_LLM(s_K|C))
escape_mass = q(s_0 | C)
```

`escape_mass` is a direct, cheap readout of the meta-belief that the candidate
set is inadequate. Because softmax is a competition, `q(s_0|C)` is large only
when the sentinel's likelihood is competitive with every real candidate — i.e.
when the evidence `C` matches none of them. Once a real candidate genuinely fits
the evidence, its logprob dominates and `q(s_0|C)` collapses toward 0.

**Key property: escape mass is commensurable across state spaces.** This is what
makes it the right control signal and resolves the "regenerating breaks old
q(s) scores" problem. It is normalized, and adding candidates can only pull mass
*off* `s_0` — so a falling escape mass cleanly means "the set is getting
better". Raw entropy `H` lacks this property: a larger set can have higher `H`
while being strictly better, so entropy can only be trusted for the
*within-set* decision (which query to search), never for the *which-set*
decision (regenerate or not).

**Implementation caveat — do not score `s_0` as a string.** The first
implementation scored `s_0 = "None of the above..."` as a literal candidate in
the softmax. This fails: token-level log-likelihood is length-biased (summed
logprob, or even mean logprob, penalises a ~12-token sentence against 1–3 token
candidates like "Italy"), so `q(s_0|C)` was pinned at ~0 and the gate never
fired (see log, fifth run). The fix is to read the meta-belief from a
**single-token YES/NO probe** instead: prompt the model with the candidate list
and "is the correct answer present among these? YES/NO", and set
`escape_mass = P(NO) / (P(NO) + P(YES))` from one next-token distribution. Same
quantity, no length bias. (Candidate scoring for the *within-set* belief is
separately length-normalised to mean per-token logprob.)

Entropy was also the wrong stopping gauge in the fixed-candidate loop: a
confidently-wrong set converges at low `H` (e.g. q=0.9999 on a wrong famous
name). Low `H` means "confident which candidate", not "the truth is in the set".
Escape mass is precisely the signal `H` was missing.

### Evidence-mined candidates

The regeneration action does not sample candidates from priors — it **mines them
from the accumulated evidence `C`**: "list specific entities (names, dates,
titles) that actually appear in the evidence and could answer the question". The
state space is thus *defined by what has been retrieved*. Obscure gold like
`Amr Zaki` is never sampled from a 4B/27B prior but does appear verbatim in
search snippets once the question's constraints are searched. Refusal-type
strings are filtered out — that role belongs exclusively to `s_0`.

### The hierarchical gate

The loop becomes a two-level controller. Each step scores candidates ∪ {s₀},
then gates on the meta-belief before acting within the model:

```
score candidates ∪ {s_0} against C  →  real_scores, escape_mass, H
if escape_mass > τ_regen:            # meta-level: set is inadequate
    regenerate(C)                    # mine new candidates from evidence (expand-only)
elif H < threshold and escape_mass ≤ τ_regen and real_searches ≥ 1:
    converge → argmax over REAL candidates (never s_0)
else:
    search(argmin_a G(a))            # base-level: existing EFE query selection
```

Regeneration is **expand-only**: new candidates are appended, the pool is capped
by likelihood, and `s_0` persists to re-measure adequacy each round. The loop is
self-terminating — once a fitting candidate lands, escape mass drops and control
flows to search/converge. The `real_searches ≥ 1` and escape-mass conditions on
convergence eliminate the premature t=0 confident-wrong exits.

Two argmaxes, kept distinct:
- **Action selection** — `argmin_a G(a)` over candidate *search queries* (unchanged).
- **Final answer** — `argmax_i q(s_i|C)` over *real* candidates only (excludes `s_0`).

### Relation to expected free energy

This is the simple-controller form: regeneration is a *gate* triggered by the
meta-belief, not scored in the same `argmin` as search. The principled unified
version would put both action types in one EFE, using a currency comparable
across state spaces — expected best-candidate log-evidence
`G(a) = − E_{q(o|a)}[ max_i log p(s_i | C') ] + cost(a)` — where a search action
changes `C` (set fixed) and a regenerate action changes the set (`C` fixed). The
`max_i log p` (or `logsumexp_i`) is unnormalized, hence commensurable, whereas
the entropy used in the base loop is not. Deferred; the gate is the first
implementation.

### Implementation

Implemented in `scripts/active_learning_agent/eval_browsecomp.py`:
`SENTINEL`, `score_with_sentinel()`, `mine_candidates()`, `is_refusal()`, and the
rewritten `run_foraging` controller. Knobs: `--tau-regen` (default 0.4),
`--max-regen` (default 3). See the experiment log for results.

## Decomposition: when the Evidence (not the Model) is the Bottleneck

Regeneration changes the hypothesis space using *existing* evidence. But on
multi-hop questions the answer is not in the evidence at all — no amount of
re-mining surfaces it. The empirical signature (sixth run) is sharp: **escape
mass stays high across multiple regenerations and never falls**. The agent has
expanded its model and the model still cannot explain the evidence, because the
evidence lacks the answer.

This gives a clean control signal. Two distinct uncertainties drive two distinct
actions:

- **Model-inadequacy that re-mining can fix** → `escape_mass` high, but *falling*
  after regeneration → keep regenerating.
- **Model-inadequacy that re-mining cannot fix** → `escape_mass` high and *not
  falling* after regeneration → the evidence is the bottleneck → **gather
  different observations** (decompose).

In active-inference terms: when model expansion stops reducing expected free
energy, the EFE-minimising action switches from changing the generative model to
sampling new observations. Decomposition is that observation-gathering action,
specialised for multi-hop: resolve one intermediate latent at a time.

### The decomposition action

A multi-hop question is a chain of latents
`question → e_1 → e_2 → ... → answer` (referee → their matches → the match with
four yellow cards → the teams). Searching the literal question is single-hop and
retrieves nothing. Instead, resolve the chain link by link:

```
next_subquestion(question, known_facts)  -- pick the single most useful next latent e_i
gather_evidence(subquestion)             -- search + fetch page bodies for e_i
extract_fact(subquestion, evidence)      -- resolve e_i to a short entity
known_facts += (subquestion, e_i)        -- substitute into subsequent hops
mine_candidates(question, enriched C)    -- candidates now informed by resolved chain
```

`known_facts` is the scratchpad of resolved latents; each resolution conditions
the next sub-question, so the chain narrows toward the answer.

### The escalating control law

On a high escape mass, the controller tries actions in increasing cost, gated by
a **staleness** test (did the previous regeneration actually lower escape mass?):

```
if escape_mass > τ_regen:
    if regeneration not yet stale and budget left:   regenerate   (cheap: re-mine current C)
    elif decompose budget left:                      decompose    (costly: resolve a new latent)
else if H low and escape low and searched:           converge
else:                                                search (EFE) (fall-through)
```

After a decompose, the staleness counter resets — fresh evidence may make
re-mining productive again — so the loop alternates regenerate ↔ decompose until
either budget is spent. Knobs: `--max-decomp` (default 3), `--regen-patience`
(default 1, i.e. one stale regeneration before switching to decompose).

This is a three-level hierarchy of action by what each one changes:
**belief** (search, within a fixed model) ⊂ **model structure** (regenerate, new
candidates from same evidence) ⊂ **evidence** (decompose, new observations of
new latents) — each invoked only when the cheaper level stops reducing free
energy.

## Answer Type as a Hierarchical Latent

Decomposition fixed multi-hop *retrieval*, but a new failure appeared (seventh
run): the agent resolves the chain yet returns the wrong *kind* of thing. Q10's
gold "St. Louis" was in the evidence, but the winner was "American Poolplayers
Association" — an intermediate entity that fit the evidence better than the city
the question actually asked for. The flat `argmax_i q(s_i|C)` has no notion of
what kind of answer is wanted.

The fix is the **hierarchical model** this document opened with: introduce the
answer *type* `T` as a slow latent above the answer `s`:

```
T   answer type   (city, person, date, team-pair, organization, …)
↓
s   the answer    (an instance of T)
↓
o   evidence
```

Type is **not** extracted in one shot — it is a latent inferred through the same
free-energy machinery as the answer, with its own belief and entropy.

### The type belief

```
q(T, s | C) = q(T|C) · q(s|T,C)
q(s|C)      = Σ_T q(T|C) · q(s|T,C)        answer belief = mixture over types
q(T|C)      ∝ p(T | question) · p(C | T)
```

Both factors reuse the logprob scorer:

- **Prior from the question** `p(T|question)` — length-normalized logprob of
  "The answer to this question is a {T}." This is what the question *asks for*
  (Q10: "city" scores high because the question says "what city"). Predictions
  flow **down**: `mine_candidates` is conditioned on `T`, so candidates are
  instances of the type.
- **Evidence fit** `p(C|T) ≈ logsumexp_i log q(s_i^T | C)` over the candidates of
  type `T` — Bayesian model selection over type-sub-models, the same
  unnormalized, cross-space-commensurable quantity used for escape mass.
  Prediction-errors flow **up**: a type whose instances misfit the evidence is
  down-weighted.

The final answer is `argmax_s Σ_T q(T|C) q(s|T,C)` — the type-marginalized
belief, so the answer integrates type uncertainty rather than committing to the
single best-fitting string. (Verified: when an organization fits the evidence
better than a city but the question asks for a city, the flat argmax returns the
organization while the marginalized belief returns the city.)

### Type selected through active inference

The type is not just inferred (perception) — its uncertainty drives action. The
type entropy `H[q(T|C)]` is a distinct source of expected free energy: a high
value means "I don't even know what kind of answer I'm hunting." It enters the
control law on a high escape mass:

- `H[q(T|C)]` high → re-mine across **all** types (resolve *which type*).
- `H[q(T|C)]` low  → re-mine instances of the **MAP type** only.

and convergence requires the type entropy low as well as the answer entropy and
escape mass. So type discovery is itself an EFE-reducing action, not a
preprocessing step.

This adds the top tier to the hierarchy of actions by what each changes:
**belief** (search) ⊂ **structure** (regenerate within a type) ⊂ **type**
(re-mine across types) ⊂ **evidence** (decompose). Implemented in
`eval_browsecomp.py`: `generate_types()`, `type_prior()`, `mine_typed()`,
`infer_type_belief()`, `marginal_belief()`. Knobs: `--n-types` (3),
`--type-threshold` (0.6).

---

## Evaluation Plan

Benchmarks, in order of difficulty. The goal is to measure whether the foraging loop (iterative search with EFE-driven action selection) improves over a single-shot baseline on factual web retrieval tasks.

### 1. SimpleQA (OpenAI, 2024)

Short factual questions with definitive answers. Clean signal — easy to score (exact match or close). Good first test because: if foraging doesn't help on simple factual lookups, it won't help on anything. Baseline: single search + answer. Foraging: the full loop. Compare accuracy.

### 2. GAIA (Meta, 2023)

General AI assistant benchmark. Multi-level difficulty, many tasks require web retrieval + multi-step reasoning. This is where foraging should start to show gains — Level 2 and 3 tasks genuinely need chaining evidence from multiple sources. Leaderboard on HuggingFace.

### 3. BrowseComp (OpenAI, 2025) -- PRIMARY BENCHMARK

This is the right benchmark for epistemic foraging. 1,266 questions that require persistent, multi-step web browsing. Single search gets almost nothing (GPT-4o: 0.6%, GPT-4o + browsing: 1.9%). Deep Research: 51.5%. Humans with 2hr limit: 29.2%.

Questions are deliberately hard-to-find, entangled across multiple web sources. E.g. "Between 1990 and 1994, what teams played in a soccer match with a Brazilian referee that had four yellow cards..." -- requires cross-referencing multiple facts across multiple searches.

Topics: TV/movies (205), Other (197), Science/tech (173), Art (127), History (125), Sports (123), Music (116), Video games (71), Geography (70), Politics (59).

Dataset: encrypted CSV, decrypted with XOR + SHA256 from canary field. Downloaded to `scripts/active_learning_agent/browse_comp_test_set.csv`.

Scoring: LLM-as-judge (semantic equivalence) + substring match fallback.

### BrowseComp leaderboard (full agent systems with browsing)

These are full agent systems, not bare models. Each has its own search/browsing infrastructure.

| Model | Params | Score | Runnable locally? |
|---|---|---|---|
| GPT-5.5 Pro | proprietary | 90.1% | no |
| Claude Mythos Preview | proprietary | 86.9% | no |
| DeepSeek-V4-Pro-Max | huge MoE | 83.4% | no |
| DeepSeek-V4-Flash-Max | huge MoE | 73.2% | no |
| Qwen3.5-397B-A17B | 397B MoE (17B active) | 69.0% | maybe |
| Qwen3.5-122B-A10B | 122B MoE (10B active) | 63.8% | maybe |
| **Qwen3.5-27B** | **27B** | **61.0%** | **yes** |
| **Qwen3.5-35B-A3B** | **35B MoE (3B active)** | **61.0%** | **yes** |
| MiMo-V2-Flash | Xiaomi | 58.3% | ? |
| DeepSeek-V3.2 | huge MoE | 51.4% | no |
| Mistral Medium 3.5 | ? | 48.6% | ? |
| **Sarvam-30B** | **30B** | **35.5%** | **yes** |
| **Nemotron 3 Super** | **120B MoE (12B active)** | **31.3%** | **yes** |
| DeepSeek-R1-0528 | huge | 8.9% | no |

**Caveat**: we cannot directly compare "Gemma 3 4B + our foraging loop" against these. They use different models AND different search orchestration. Our comparison is internal: same model, same search API, different strategies (no search vs single search vs foraging).

Gemma 3 4B is not on this leaderboard -- too small. Any score above 0% is meaningful.

### Experiment plan

1. Start with **Gemma 3 4B** -- fast iteration, clean slate
2. Scale to **Phi 4 (14B)**, **Gemma 3 27B** -- see if foraging gains hold with model size
3. Compare internally: baseline vs single_search vs foraging (same model, same Brave API)
4. Track: accuracy, number of searches per question, wall time

### Baseline vs Foraging

For each benchmark, compare:
- **Baseline**: generate answer directly (no search), or single search + answer
- **Foraging (1 iteration)**: search once, score candidates, return best — equivalent to RAG
- **Foraging (full loop)**: the complete epistemic foraging loop with EFE action selection

The key metric is whether additional iterations (driven by entropy/EFE) actually improve accuracy, and at what cost (number of LLM calls, wall time).

### SimpleQA dataset details

- 4326 factual questions with short, definitive answers
- Columns: `problem` (question), `answer` (gold), `metadata` (topic, answer_type, urls)
- Topics: Music, Sports, Geography, Art, Politics, Science, etc.
- On HuggingFace: `basicv8vc/SimpleQA`
- Scoring: substring match (gold in predicted or predicted in gold), case-insensitive

### Open-source models from the leaderboard (no search baselines)

| Model | Params | SimpleQA | HuggingFace ID |
|---|---|---|---|
| Gemma 3 4B | 4B | 4.0% | `google/gemma-3-4b-it` |
| Gemma 3 12B | 12B | 6.3% | `google/gemma-3-12b-it` |
| Gemma 3 27B | 27B | 10.0% | `google/gemma-3-27b-it` |
| Phi 4 | 14B | 3.0% | `microsoft/phi-4` |
| Mistral Small 3.1 24B | 24B | 10.4% | `mistralai/Mistral-Small-3.1-24B-Instruct-2503` |
| Qwen3 235B (A22B MoE) | 235B | 54.3% | `Qwen/Qwen3-235B-A22B` |
| DeepSeek-V3 (MoE) | 671B | 24.9% | `deepseek-ai/DeepSeek-V3` |

These are all without search — pure parametric recall. Low baselines are good for us: lots of room for search (and foraging) to close the gap.

Starting with **Gemma 3 4B** (4.0% baseline). Small enough to iterate fast, low enough baseline to clearly see if foraging helps.

### Eval script

`scripts/active_learning_agent/eval_simpleqa.py`

Three modes:
1. **baseline** — model answers directly, no search
2. **single_search** — one Brave search with the question as query, then answer
3. **foraging** — full epistemic foraging loop: generate candidates, score with logprobs, select search query via EFE, execute real Brave search, repeat until entropy < threshold

Uses real Brave Search API (needs `BRAVE_API_KEY`). Model is local via transformers (default `Qwen/Qwen2.5-3B`).

```bash
# quick test: 50 questions, all 3 modes
python eval_simpleqa.py --n 50 --brave-key $BRAVE_API_KEY --mode all

# just foraging with tuned params
python eval_simpleqa.py --n 200 --brave-key $BRAVE_API_KEY --mode foraging --threshold 0.3 --max-iter 5
```

Results saved to `simpleqa_results.jsonl` (one JSON object per question per mode).

### BrowseComp eval script

`scripts/active_learning_agent/eval_browsecomp.py`

Same three modes (baseline, single_search, foraging), now using BrowseComp questions with real Brave Search. This is the primary eval.

```bash
# quick test: 10 questions, all 3 modes
python eval_browsecomp.py --n 10 --brave-key $BRAVE_API_KEY --mode all

# foraging only, filter by topic
python eval_browsecomp.py --n 50 --brave-key $BRAVE_API_KEY --mode foraging --topic Sports

# full run
python eval_browsecomp.py --n 200 --brave-key $BRAVE_API_KEY --mode all --max-iter 5
```

Results saved to `browsecomp_results.jsonl`.

*(discussion continues)*


# Appendix (to be used)
### In-context learning as variational inference

    1. "In-context Learning and Induction Heads" (Olsson et al., 2022, Anthropic) — not directly about variational inference but establishes the mechanistic basis for how transformers do in-context learning via
    induction heads.
    2. "An Explanation of In-context Learning as Implicit Bayesian Inference" (Xie et al., 2022) — this is probably the closest to the claim. They show that in-context learning can be understood as the
    transformer implicitly performing Bayesian inference over a latent concept variable, which is essentially the variational inference framing.
    3. "Transformers as Algorithms: Generalization and Stability in In-context Learning" (Li et al., 2023) — formalises transformers as implementing learning algorithms, connecting to the inference view.
    4. "The Bayesian Learning Rule" (Khan & Rue, 2023) — broader paper connecting many learning algorithms to variational inference, relevant as a theoretical backbone.

    The Xie et al. paper is the one I'd start with — it directly argues that in-context learning is implicit Bayesian inference over a latent variable (their "concept" variable maps directly to our hidden state
    s). The connection to variational inference specifically is that the transformer's forward pass approximates the true posterior without explicit optimisation — which is exactly what a variational
    approximation does.

    That said, "in-context learning IS variational inference" is still somewhat of a strong claim. The papers show it behaves like Bayesian/variational inference under certain data-generating assumptions.
    Whether it's doing it mechanistically or just converging to similar behaviour is still debated.
