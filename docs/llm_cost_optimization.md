# LLM Cost Optimization — Measured Before/After

Date: June 9, 2026

## Approach: measure first, optimize second, prove the difference

NexusIQ routes every model call through a single LLM gateway (`utils/llm_gateway.py`)
that writes an append-only JSONL ledger (`data/llm_task_ledger.jsonl`) with task name,
model, latency, estimated tokens, actual provider tokens when available, prompt hash,
and the active trace/harness task IDs. Each ledger row carries a **measurement
profile** (`NEXUSIQ_MEASUREMENT_PROFILE`) so before/after runs can be compared from
the same data, not from guesses.

With measurement in place, three call sites were replaced with deterministic logic:

| Task | Before | After |
|------|--------|-------|
| `fusion.route` | LLM router on every query | Rule-based routing for obvious SQL/Web/validation questions; LLM router only for ambiguous ones |
| `sql.format_answer` | LLM formats every SQL result | Deterministic renderer for common result shapes (scalar aggregates, key-value rows, markdown tables) with column-aware money/count/percent formatting; LLM only for unusual shapes |
| `sql.explain_query` | LLM explains every generated query | Deterministic structural explanation by default; LLM explanation behind `NEXUSIQ_SQL_EXPLAIN_MODE=llm` |

LLM synthesis is retained where it earns its cost: conflict explanation,
ambiguity, and narrative interpretation (`fusion.answer` on LOW-confidence paths,
`rag.answer`, interpretive web questions).

## Avoided-call accounting

Every skipped call is recorded, not silently dropped:

- **Ledger**: a row with `status: "avoided"`, the reason, and
  `tokens_avoided_estimate` — the prompt tokens that were never sent.
  Accounting is conservative: the unsent completion is not estimated.
- **Trace**: an `llm.call_skipped` span event, so the per-query
  "How NexusIQ Ran This Answer" panel shows avoided calls and tokens.
- **Reports**: `python -m observability.inspect_llm_usage` aggregates avoided
  calls and avoided tokens alongside per-task/per-model/per-profile usage.

A `contextvars` propagation fix ensures ledger rows from agents running in
parallel worker threads (`ThreadPoolExecutor`) still attach to the active query
trace — previously multi-source routes lost trace attribution.

## Measured results

Same queries, same production path (harness + LangGraph), fresh (cache-bypassed),
profiles `foundation_before_call_disabling` vs `after_sql_call_reduction`:

| Query | Route | LLM calls | Est. tokens | Wall time |
|-------|-------|-----------|-------------|-----------|
| "How many transactions happened in October 2024?" (before) | sql_only | 4 | 2,036 | 5.8s |
| same (after) | sql_only | **1** (−75%) | **939** (−54%) | **1.0s** |
| "What was Q4 2024 total revenue? Validate it against the internal financial reports." (before) | sql_rag | 7 | 5,132 | 11.3s |
| same (after) | sql_rag | **2** (−71%) | **2,478** (−52%) | **6.9s** |

After-run avoided calls (from the trace summary):
`fusion.route` (rule-based routing), `sql.format_answer` (deterministic format,
~144-163 prompt tokens not sent), `sql.explain_query` (deterministic explanation,
~273-288 prompt tokens not sent).

## Correctness was not traded away

- Cross-source validation reads **structured SQL result rows**, not formatted
  answer text, so deterministic formatting cannot change validation outcomes.
  The SQL+RAG validation query above still returns **HIGH confidence (0.07%
  SQL/PDF delta)** with a `deterministic_validated` answer.
- Deterministic formatting falls back to the LLM for unusual result shapes.
- 145 unit + contract tests pass, including `tests/test_sql_call_reduction.py`,
  which asserts that the deterministic paths render correctly, that no LLM
  invocation happens on those paths, and that every avoided call is logged to
  the ledger and trace with a reason.
- Offline evals pass 7/7 with no provider calls.

## Reverting / A-B comparison

```bash
# Restore LLM rendering for comparison
export NEXUSIQ_SQL_FORMAT_MODE=llm
export NEXUSIQ_SQL_EXPLAIN_MODE=llm

# Compare profiles in the ledger report
python -m observability.inspect_llm_usage
```
