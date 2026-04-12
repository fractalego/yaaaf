# Progressive Complexity Orchestration

## Motivation

The current orchestrator generates a single plan and replans only on *failure*. This is wasteful for simple queries: a question like "who is the prime minister of Italy?" doesn't need five web searches and a multi-source aggregation — a single `answerer` call suffices.

The idea is to run a sequence of DAGs of increasing complexity. If the first plan produces a sufficient answer, stop. Otherwise escalate to the next level.

```
Easy   → sufficient? → done
Moderate → sufficient? → done
Hard   → sufficient? → done
...
```

This separates two concerns that are currently conflated in the replan loop:

- **Failure recovery**: replan because execution broke
- **Complexity escalation**: replan because the answer was too shallow

Both can coexist. Within each intensity level, the existing failure/retry loop still applies.

---

## The IntensityScheduler

A new class `IntensityScheduler` sits *above* the existing `OrchestratorAgent` and exposes the same `query()` interface, making it a drop-in replacement from the server's perspective.

```
IntensityScheduler.query()
  for level in active_levels:          # only levels with ≥1 configured agent
    plan = planner(level.palette, level.directive, prior_context)
    result = orchestrator.execute(plan) # inner retry loop unchanged
    if sufficient(result, goal): return result
    prior_context = (result, insufficiency_reason)
  return best_result_so_far
```

The `OrchestratorAgent` never knows about levels. It runs one plan reliably and returns.

**Responsibility split:**

| Component | Responsibility |
|---|---|
| `IntensityScheduler` | **New.** Owns level definitions, escalation loop, sufficiency judging, context carry-over |
| `OrchestratorAgent` | Unchanged. Executes a single plan with failure/retry |
| `PlannerAgent` | Small change: accepts `agent_palette_override` + `intensity_directive` at call time |
| `ValidationAgent` | Small change: new sufficiency prompt variant alongside existing validation |
| `OrchestratorBuilder` | Wraps orchestrator in scheduler; defines active levels from config |

---

## Intensity Level Definitions

Each level defines a canonical agent palette and a planning directive. **The active palette for a level is always the intersection of the level's ideal set and the agents explicitly listed in the user's config.** An agent not present in the config is never activated, regardless of level. A level whose active palette is empty after filtering is silently skipped.

`user_input` is excluded from all levels — it pauses execution and breaks the automatic escalation loop.

---

### Easy
**Ideal palette:** `[answerer]`
**DAG shape:** single asset
**Directive:**
> Use only your internal knowledge. Generate a single-step plan with just the answerer.

**Handles:** math, reasoning, general knowledge, summarising provided context — anything the model already knows without external lookup.

---

### Moderate
**Ideal palette:** `[brave_search, websearch, answerer]`
**DAG shape:** 1–2 searches → answerer (2–3 assets)
**Directive:**
> Perform one or two web searches to gather up-to-date information, then synthesise a direct answer.

**Handles:** current events, recent facts, simple lookups where a single search suffices.

---

### Hard
**Ideal palette:** `[brave_search, websearch, url, url_reviewer, answerer]`
**DAG shape:** multiple searches + URL fetches → answerer (3–5 assets)
**Directive:**
> Use multiple searches across different angles and fetch specific URLs for detail. Do not rely on internal knowledge.

**Handles:** research questions where search snippets are not enough and full page content needs reading.

---

### Expert
**Ideal palette:** `[brave_search, websearch, url, url_reviewer, sql, document_retriever, reviewer, answerer]`
**DAG shape:** parallel information gathering (web + structured data + documents) → synthesis (4–7 assets)
**Directive:**
> Cross-reference multiple information sources: web search, local documents, and structured databases. Use a reviewer to validate intermediate results before synthesising.

**Handles:** questions that span both live web data and local structured/document knowledge.

---

### Elite
**Ideal palette:** `[brave_search, websearch, url, url_reviewer, sql, document_retriever, reviewer, numerical_sequences, visualization, answerer]`
**DAG shape:** multi-branch parallel DAG with quantitative processing (5–10 assets)
**Directive:**
> Build a multi-branch DAG with parallel information-gathering paths. Include quantitative analysis or visualisation where relevant. All branches must converge into a final synthesised answer.

**Handles:** analytical questions combining live data, structured data, and numerical reasoning — e.g. "compare GDP trends across three countries".

---

### Master
**Ideal palette:** full agent set (`brave_search`, `websearch`, `url`, `url_reviewer`, `sql`, `document_retriever`, `reviewer`, `numerical_sequences`, `visualization`, `bash`, `mle`, `code_edit`, `tool`, `answerer`)
**DAG shape:** unconstrained, iterative refinement allowed
**Directive:**
> Use any combination of agents. Computation, code generation, machine learning, and external tool calls are all available. Build the most thorough plan possible.

**Handles:** tasks requiring code execution, data science, file system operations, or MCP tool calls.

---

## Level Ordering and Palette Inheritance

Levels are strictly additive — each level's ideal palette is a superset of the one below. This guarantees monotonic escalation: a higher level can never do *less* than a lower one.

```
Easy     ⊂ Moderate ⊂ Hard ⊂ Expert ⊂ Elite ⊂ Master
```

After config filtering, the active sequence may be shorter. For example, a config with only `[answerer, brave_search]` produces:

```
Easy (answerer) → Moderate (brave_search + answerer)
# Hard–Master are all filtered to the same two agents → skipped as duplicates
```

---

## Config Filtering Rule

> **An agent is available at a level if and only if it appears explicitly in the user's config.**

This is enforced at `IntensityScheduler` construction time. For each level, the builder computes:

```python
active_palette = level.ideal_palette ∩ configured_agents
```

If `active_palette == active_palette_of_previous_level`, the level is a duplicate and is skipped. This prevents redundant identical plans at consecutive levels.

---

## Sufficiency Judge

The existing `ValidationAgent` is reused with a different prompt variant. The shift is from "is this correct?" to "does this *fully answer* the original question, or does it need more information?".

Returns one of:
- `SUFFICIENT` — answer addresses the goal; stop escalating
- `INSUFFICIENT: <reason>` — escalate, passing the reason as context to the next level

The judge call should be cheap: short prompt, same model, called once per level.

---

## Carrying Context Across Levels

At Moderate and above, the planning prompt includes what the previous level produced and why it was insufficient:

```
[INTENSITY: Hard — escalated from Moderate]
Prior answer: "..."
Judged insufficient because: "answer was outdated and lacked source detail"

You MUST use multiple searches across different angles and fetch specific URLs for detail.
Do not rely on internal knowledge.
```

This mirrors the existing `plan_continuation()` mechanism used for failure recovery, but the signal is *insufficiency* rather than *error*.

---

## Key Design Decisions

1. **Level 1 (Easy) can skip the planner entirely** — the plan is always a single `answerer` asset with no inputs. Hardcoding this avoids an LLM call for the simplest case.

2. **The sufficiency check adds latency** — one judge call per level. Acceptable if Easy and Moderate catch the majority of queries early.

3. **The inner failure-retry loop is orthogonal** — complexity escalation wraps around it. A level can still retry on execution failure before declaring insufficiency.

4. **Config filtering is enforced at construction time, not at runtime** — the active level sequence is computed once when the scheduler is built. No runtime surprises.

5. **Duplicate levels are skipped** — if config filtering causes two consecutive levels to have the same active palette, the duplicate is dropped silently. The escalation sequence only contains levels that add at least one new agent.

### Future: BM25 retrieval biased by complexity

The planner uses RAG to inject examples from `planner_dataset.csv`. If examples were tagged with a complexity score (number of assets / agents used), the retriever could filter to examples with complexity ≥ current level — steering the planner implicitly through format imitation rather than explicit instruction. Natural future enhancement once the dataset has complexity metadata.
