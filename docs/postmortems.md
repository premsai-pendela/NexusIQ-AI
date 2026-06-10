# Engineering Post-Mortems

Real defects found and fixed while building and operating NexusIQ. Each entry
links the fixing commit and the regression tests that now guard it. This is a
solo project; "detection" describes how the bug actually surfaced — several
were caught by local verification or eval runs before reaching production,
which is the point of having those layers.

---

## PM-1: One user query produced two root traces

**Date:** June 1, 2026 · **Area:** Observability · **Caught:** production deploy verification

**Impact.** After enabling the production harness with LangGraph as its
workflow engine, every query produced two root traces — one from the harness,
one from LangGraph. Trace counts doubled, Langfuse showed phantom queries, and
per-query LLM cost attribution split across two unrelated trace IDs, making
the cost ledger unusable for exactly the analysis it was built for.

**Root cause.** Both orchestration layers called `start_trace()`. LangGraph
ran *inside* the harness but did not know a trace session already existed —
trace-session ownership was implicit, so wrapping one orchestrator in another
silently created a second root.

**Fix.** [`2f7a0070`](https://github.com/premsai-pendela/NexusIQ-AI/commit/2f7a0070) — the harness owns the root
trace; the LangGraph workflow records its node spans into the existing
session instead of starting its own.

**Regression guard.** `tests/test_langfuse_observability.py`
(trace-summary and gateway-event attachment contracts),
`tests/test_fusion_graph.py` orchestration tests.

**Lesson.** When one orchestrator wraps another, observability-session
ownership must be an explicit contract, not a side effect of "whoever calls
start first."

---

## PM-2: SQL safety guardrail blocked legitimate queries

**Date:** late May – June 1, 2026 · **Area:** SQL guardrails · **Caught:** demo testing

**Impact.** The original guardrail rejected safe `SELECT` statements because
it matched forbidden keywords as substrings of raw SQL text: `created_at`
contains `CREATE`, `updated_at` contains `UPDATE`, `dropoff_rate` contains
`DROP`. Support-case questions filtered on `created_at` failed outright — a
security control acting as an availability bug.

**Root cause.** String-level keyword scanning cannot distinguish an
identifier from a statement. Security validation was applied to text, not
structure.

**Fix.** [`758ec373`](https://github.com/premsai-pendela/NexusIQ-AI/commit/758ec373) — guardrails rebuilt on
`sqlglot` AST parsing: the parse tree is walked for forbidden statement
*types* (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`,
`TRUNCATE`), exactly one statement is allowed, and the statement must be a
read-only expression (`SELECT`/`WITH`/set operations). Identifiers can
contain anything.

**Regression guard.** `tests/test_sql_safety.py` — 12 safe identifiers
containing forbidden stems must pass; 7 real forbidden statement types must
block; multi-statement injection (`SELECT 1; CREATE TABLE …`) must block;
forbidden words inside string literals must pass.

**Lesson.** Validate SQL on the parse tree, never on substrings. A guardrail
with false positives doesn't just annoy users — it trains people to disable
it.

---

## PM-3: Cross-validation missed facts wrapped in markdown

**Date:** May 2026 · **Area:** Cross-source validation · **Caught:** golden eval run

**Impact.** The SQL↔PDF validator extracts numeric facts from answer text.
LLM-formatted answers emphasize numbers with markdown (`**331** returns`),
and the count-extraction regex required the digit to be adjacent to its
context word — so bolded counts were invisible. Facts that agreed across
sources failed to match, producing wrong confidence levels on count
validation questions.

**Root cause.** The validator consumed LLM-rendered presentation text as if
it were plain prose. Markup broke token adjacency assumptions.

**Fix.** [`2890fbab`](https://github.com/premsai-pendela/NexusIQ-AI/commit/2890fbab) — strip markdown emphasis
before applying the count pattern. Verified 3/3 count matches at 0% diff
after the fix.

**Regression guard.** Count-fact contracts in
`tests/test_validation_contracts.py` (transaction-count metadata and
confidence tests).

**Lesson.** Anything that parses LLM output must normalize presentation
markup first. The validator's input is not text — it's *formatted* text.

---

## PM-4: Parallel agents silently lost trace attribution

**Date:** June 9, 2026 · **Area:** Observability / concurrency · **Caught:** token-optimization verification, pre-push

**Impact.** Multi-source routes run SQL/RAG/Web agents in a
`ThreadPoolExecutor`. The trace session and harness task ID travel through a
`contextvars.ContextVar`, which does **not** propagate into pool worker
threads — every LLM ledger row from a parallel route was written with
`trace_id: None`. Per-query usage summaries reported `successful_calls: 0`
on queries that made multiple real model calls. Single-source routes (run
inline) looked fine, which masked the gap: the observability system was
blind precisely on the most expensive queries.

**Root cause.** Worker threads start with an empty contextvars context.
Context propagation across the thread pool was assumed, never verified
end-to-end.

**Fix.** [`4ab16801`](https://github.com/premsai-pendela/NexusIQ-AI/commit/4ab16801) — agent tasks are submitted via
`contextvars.copy_context().run(...)`, so each worker executes inside a copy
of the caller's context and ledger rows inherit the live trace and harness
task IDs.

**Regression guard.** Gateway-metadata flow assertions in
`tests/test_business_context.py` (`MetadataFlowTest`) and trace-attachment
contracts in `tests/test_langfuse_observability.py`; verified live — a
`sql_rag` query now reports its 2 successful calls, 3 avoided calls, and
token totals on one trace.

**Lesson.** Observability must be verified end-to-end per execution path,
not per component. A tracing system that works inline and silently drops
attribution under concurrency is worse than no tracing — it produces
confident, wrong numbers.
