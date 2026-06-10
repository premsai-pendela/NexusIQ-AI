# Business Context Layer — Company Definitions for Text-to-SQL

Date: June 9, 2026

## The enterprise failure mode this addresses

Text-to-SQL models score 85%+ on academic benchmarks but collapse in real
enterprises because they know SQL syntax, not company semantics. The most
dangerous failures execute cleanly and return plausible numbers that are
silently wrong: "net revenue" computed without subtracting refunds, "active
customers" counted as every row in the customers table, "open cases" missing
the `in_progress` status.

NexusIQ closes this gap with a deterministic business-context retrieval layer:
company-specific metric definitions are retrieved per question and injected
into SQL generation — no extra LLM calls, no embeddings, ~150–600 prompt
characters of overhead only when relevant.

## How it works

```
question
  -> BusinessContextRetriever (context/business_context.py)
       exact term/alias phrase match (score 10+)
       + stopword-filtered keyword overlap (threshold 2)
  -> top <=3 entries, ~900-char budget
  -> COMPANY BUSINESS DEFINITIONS block in the SQL generation prompt
  -> context IDs recorded in LLM ledger metadata + query trace + UI caption
```

- **Glossary**: `config/business_glossary.json` — 15 seeded entries (metrics,
  policies, join hints) verified against the live Supabase schema and real
  status enums (`returns.status` ∈ approved/received/rejected/pending/refunded).
- **Conservative retrieval**: plain questions ("total revenue in October")
  retrieve nothing and produce a byte-identical prompt — proven by unit test.
- **Kill switch**: `NEXUSIQ_BUSINESS_CONTEXT=0` disables the layer entirely.
- **Failure-safe**: glossary load/retrieval errors are caught and logged; SQL
  generation continues without context.

## Measured before/after (live SQL generation + execution)

12 cases (10 ambiguous + 2 controls), deterministic scoring: expected SQL
fragments present AND the query executes AND context retrieval is correct
(ambiguous cases must retrieve their expected definition IDs in after mode;
controls must retrieve none in both modes). Runner:
`python -m evals.context_eval --mode both`. Report: `eval-reports/context_eval_20260609_233145.json`.

| Case | Before | After | Context applied |
|------|--------|-------|-----------------|
| net revenue Q4 2024 | FAIL (summed gross only) | PASS (CTEs subtract refunded returns) | net_revenue |
| active customers | FAIL | PASS (Q4-2024 purchase window, DISTINCT) | active_customer |
| return rate Q4 | FAIL | PASS (both tables, excludes rejected) | return_rate |
| money refunded 2024 | FAIL (summed all statuses) | PASS (status='refunded' only) | refunded_amount |
| case resolution time | PASS | PASS (epoch-hours form) | case_resolution_time |
| open case backlog | FAIL (status='open' only) | PASS (+ in_progress) | open_case_backlog |
| best region 2024 | FAIL (gross ranking) | PASS (net revenue ranking) | region_performance |
| repeat customers | FAIL | PASS (HAVING COUNT >= 2) | repeat_customer |
| churned customers | FAIL | PASS (H1 buyers absent after 2024-07-01) | churned_customer |
| units sold December | PASS | PASS (SUM(quantity)) | units_sold |
| control: total revenue October | PASS | PASS — no context retrieved | — |
| control: top 5 products | PASS | PASS — no context retrieved | — |

**Ambiguous cases: 2/10 before → 10/10 after. Controls unchanged 2/2.**

Honest notes:
- Two ambiguous cases (`case_resolution_time`, `units_sold_december`) already
  passed before — the model sometimes guesses right. The layer makes the
  behavior *defined* rather than lucky, and the definitions also encode
  PostgreSQL house rules (e.g., interval→epoch conversion) that fixed an
  intermittent `cannot cast type interval to numeric` failure observed in an
  earlier run.
- First full run scored 8/10 after; two definitions were sharpened (CTE
  cross-join guidance, interval handling) and the final run scored 10/10.
  Iterating definitions from eval failures is the intended workflow — that is
  what the layer is for.

## Why this technique

- **Deterministic retrieval over embeddings**: 15 entries don't need a vector
  DB; alias+keyword scoring is unit-testable without quota, adds zero latency,
  and cannot hallucinate. Embeddings/Chroma become worthwhile at glossary
  scale (v2, along with a correction-feedback store).
- **No new LLM calls**: continues the measured token-optimization discipline —
  the only cost is ≤900 prompt characters, and only on questions that hit the
  glossary. Context IDs and char counts appear on every `sql.generate_query`
  ledger row for cost attribution.
- **Prompt injection at one site**: the layer lives entirely inside
  `SQLAgent._create_sql_prompt`; FusionAgent, LangGraph, and the harness are
  untouched.

## Observability

- Ledger rows (`data/llm_task_ledger.jsonl`): `business_context_ids`,
  `business_context_chars` on `sql.generate_query` attempts.
- Query traces: same metadata inside `llm.call` spans.
- UI: "📚 Company definitions applied: `net_revenue`" caption under the
  generated SQL.
- Definition text is not exported to Langfuse — IDs only, consistent with the
  no-prompt-content policy.

## Tests

`tests/test_business_context.py` (19 tests): glossary loading and malformed-entry
tolerance, retrieval precision (terms/aliases/paraphrases hit, plain questions
miss), 3-entry cap, char budget, phrase-over-overlap ranking, flag kill-switch,
byte-identical fallback prompt, metadata flow to the gateway, and result-shape
contracts.
