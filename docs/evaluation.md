# NexusIQ-AI Evaluation Guide

NexusIQ-AI now has three complementary validation layers:

- `tests/test_validation_contracts.py` is the fast unit suite for routing helpers, input validation, and SQL/RAG/Web answer contracts.
- `evals/offline_eval.py` is a deterministic offline evaluation harness that proves answer validation behavior without calling LLMs, scrapers, ChromaDB, or the live SQL database.
- `evals/golden_eval.py` is the production-style golden eval runner. It runs real NexusIQ questions through the real Fusion Agent, scores objective behavior with rule-based metrics, and can optionally add an LLM judge quality score.
- `run_tests.py` remains the live end-to-end query runner for exercising the full multi-agent stack against `test_queries.txt`.

## Fast Verification

Run the deterministic suite before changing routing, validation, or result-shaping code:

```bash
python -m unittest discover -s tests -v
```

Run the offline evaluation harness:

```bash
python -m evals.offline_eval
```

List the golden eval cases without running live agents:

```bash
python -m evals.golden_eval --dry-run
```

To save reports locally:

```bash
python -m evals.offline_eval --output eval-reports
```

`eval-reports/` is ignored by git, so generated reports stay out of commits.

## What The Offline Harness Proves

The harness uses fixed result fixtures and checks these contracts:

| Area | Contract |
|------|----------|
| SQL | Successful SQL answers include non-empty answer text and coherent row evidence. |
| RAG | Successful document answers include retrieved chunks and source citations. |
| Web | Successful web answers include recognized-category product prices, reject sample data as live evidence, and disclose stale cached prices after refresh failure. |
| SQL + RAG | Matching revenue facts produce high confidence validation. |
| SQL + RAG | Material revenue mismatches produce low confidence with discrepancies. |
| SQL + RAG | Helper metadata such as `transactions_analyzed` does not validate or contradict PDF revenue. |

The offline harness intentionally bypasses `FusionAgent.__init__` so it never initializes live agents. It only reuses pure validation methods such as `_cross_validate`.

## Golden Eval System

The golden eval system is the main production-minded eval layer.

```bash
# List the 12 golden cases
python -m evals.golden_eval --dry-run

# Run a small smoke subset through the real Fusion Agent
python -m evals.golden_eval --ids q4_electronics_revenue,refund_policy

# Run the first three cases
python -m evals.golden_eval --limit 3

# Run slower and retry transient provider failures
python -m evals.golden_eval --delay 8 --retries 1 --retry-delay 60

# Rescore the latest saved responses without calling the app agents
python -m evals.golden_eval --replay latest

# Evaluate answer quality while skipping routing calls
python -m evals.golden_eval --answer-only --delay 8 --retries 1

# Add optional LLM-as-judge quality scoring
python -m evals.golden_eval --limit 3 --with-judge
```

The runner saves Markdown and JSON reports to `eval-reports/`.

Each JSON report stores the raw per-case agent response. That makes the report a response cache: if you change scoring rules, tolerances, required terms, or report formatting, run `--replay latest` to rescore the saved answers without spending provider quota on the app agents again. Use a specific path when needed:

```bash
python -m evals.golden_eval --replay eval-reports/golden-eval-YYYY-MM-DD_HH-MM-SS.json
```

Reports generated before response caching was added cannot be replayed because they do not contain the raw agent response. After one new live golden eval run, `--replay latest` will use the newest replayable report automatically.

If you add `--with-judge` during replay, the app answer is reused but the judge may still call an LLM. Leave `--with-judge` off when you want a fully no-provider replay.

Every run also appends a summary row to `eval-reports/trend.csv`. This gives you a simple score history for demos and interviews, for example showing whether prompt or retrieval changes improved the average score over time.

If the production database changes, refresh the numeric truth from the same `DATABASE_URL` used by the app:

```bash
# Preview values from the configured database
python -m evals.refresh_golden_truth --dry-run

# Update evals/golden_cases.json
python -m evals.refresh_golden_truth
```

Use this after regenerating data, switching databases, or changing `.env`.

Golden eval scoring uses a 100-point structure:

| Metric | Points | What it checks |
|--------|--------|----------------|
| Route | 15 | The Fusion Agent chose the expected route, such as `sql_rag` or `web_only`. |
| Numbers | 20 | The answer or source results contain expected business numbers within tolerance. |
| Confidence | 15 | Cross-source validation returned the expected confidence when specified. |
| Evidence | 15 | Required SQL/RAG/Web results, terms, and source signals are present. |
| Safety | 5 | Forbidden terms and unsafe unavailable-data claims are absent. |
| LLM judge | 30 | Optional quality score for correctness, completeness, groundedness, and clarity. |

When the judge is not enabled, cases are scored on the 70 rule-based points and normalized to 100. This keeps the eval useful without API calls.

`--answer-only` is useful when provider quotas are tight. It forces the expected route for each case, skips route scoring, and evaluates whether the real SQL/RAG/Web answer path still returns the correct evidence and numbers. Use normal mode when you want to evaluate routing too.

## Live Evaluation

Use the existing live runner when you want to test the complete app path:

```bash
python run_tests.py --phase 1
python run_tests.py --phase 2
python run_tests.py --ids 46,85,91
python run_tests.py
```

Live runs can touch runtime cache files such as `data/quota_tracker.json`, `data/web_cache.json`, and ChromaDB files. Keep those out of commits unless you intentionally refreshed the committed data baseline.

## Adding New Eval Cases

Add deterministic cases to `OFFLINE_EVAL_CASES` in `evals/offline_eval.py` when a new behavior should remain stable across API availability and local data state.

Prefer offline evals for:

- Cross-source numeric validation rules.
- Result-shape contracts.
- Regression coverage for known false positives.
- Web result evidence checks.
- Web freshness and sample-data trust checks.

Prefer `run_tests.py` for:

- Full routing behavior with real LLM classification.
- SQL generation and execution.
- RAG retrieval quality.
- Real scraper and cache behavior.

Prefer golden evals for:

- Regression tracking across real NexusIQ answers.
- Comparing route, numeric, confidence, and evidence quality after code or prompt changes.
- Building a stable baseline before adding pairwise comparisons or deeper RAG metrics.
