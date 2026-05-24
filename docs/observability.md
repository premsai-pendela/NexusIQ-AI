# NexusIQ-AI Observability Guide

NexusIQ now has lightweight local AI observability. It records what happened during a Fusion Agent query so eval failures and app failures are easier to debug.

This first version does **not** call extra LLMs. It only traces work the app already did.

## What Gets Traced

Each trace records:

- user question
- forced source, if any
- routing decision
- routing model/fallback
- SQL/RAG/Web agent steps
- SQL query text
- SQL row count
- RAG chunk/source summary
- Web category and competitor count
- cross-source validation confidence
- fusion answer generation step
- final answer preview
- errors and timings

By default, traces avoid storing full prompts. This keeps the trace useful without turning it into a secret dump.

Trace files include a small schema marker (`schema_version`) so future trace readers can evolve without guessing the file shape.

For quick terminal checks, each completed trace also appends a compact JSONL row to:

```text
data/query_traces.jsonl
```

That file is only an index. The full trace still lives in `traces/trace-...json`.

## LLM Task Ledger

NexusIQ uses an LLM gateway in `utils/llm_gateway.py`. SQL, RAG, Fusion, and Web Agent model calls now go through this gateway, which writes one lightweight event per model attempt to:

```text
data/llm_task_ledger.jsonl
```

The ledger records:

- task name, such as `sql.generate_query`, `rag.answer`, or `fusion.route`
- model and provider type
- temperature
- success, skipped, or failed status
- latency
- estimated input/output tokens
- prompt hash

It does not store raw prompts. This gives cost and reliability visibility without turning the ledger into a secret dump.

New ledger attempts also include an `invocation_id` for grouping fallback attempts
and a `failure_kind` that distinguishes invalid structured output from provider
failure. Historical rows without these fields remain valid input for reports.

Current task coverage:

| Agent area | Ledger tasks |
|---|---|
| SQL | `sql.generate_query`, `sql.format_answer`, `sql.explain_query` |
| RAG | `rag.answer`, `rag.hyde`, `rag.decompose`, `rag.extract_metrics`, `rag.synthesize_comparison`, `rag.compare_answer` |
| Fusion orchestration | `fusion.route`, `fusion.resolve_question`, `fusion.answer` |
| Web | `web.answer` |

JSON-producing tasks validate their response before accepting it. If a router or RAG decomposition model returns malformed JSON, the gateway records an invalid-response attempt and tries its fallback model without treating the provider as quota-down.

Disable ledger writes with:

```bash
NEXUSIQ_LLM_LEDGER_ENABLED=0 python main.py
```

Or choose a custom ledger path:

```bash
NEXUSIQ_LLM_LEDGER_PATH=/tmp/nexusiq-llm-ledger.jsonl python main.py
```

Summarize task/model token totals, average and p95 latency, invalid responses,
grouped fallbacks, and the highest-cost attempts:

```bash
python -m observability.inspect_llm_usage
python -m observability.inspect_llm_usage --json
```

The usage report counts cache hits recorded in `data/query_traces.jsonl`.
It deliberately does not claim token savings yet: cached traces currently do
not link to the original ledger invocation needed for a defensible estimate.

Web pricing answer generation passes only answer-relevant evidence to the LLM:
competitor names and each product's name, current price, comparison price, and
source, plus freshness status when disclosure is required. Scraper diagnostics,
SKUs, image URLs, and product URLs remain available in raw result data but are
omitted from model context.

Exact Web price lists, ranges, extremes, counts, and discount calculations do
not call `web.answer`; they are calculated from product evidence. When a live
refresh fails, cached Web evidence is labeled `cached_stale`, carries its
capture time in traces, and must be disclosed in the answer. Optional sample
fallback is disabled by default and never counts as successful live evidence;
enable it only for a deliberate demo with `WEB_ALLOW_SAMPLE_FALLBACK=true`.

## Cache Trust Controls

NexusIQ treats repeated questions as a product decision, not only a speed optimization.

For exact same-session repeats, the UI asks whether to show the previous answer or check again. Choosing "Check again" bypasses the Fusion cache once.

Fusion final-answer caching is quality gated:

- SQL + RAG answers cache only after high-confidence validation.
- Degraded answers such as `sql_failed` are not cached.
- Low-confidence validation, missing answers, and agent errors are rejected from the cache.

Trace events include cache bypass and cache admission decisions so repeated-answer behavior can be debugged alongside LLM and agent spans.

## Where Traces Are Saved

Traces are written to:

```text
traces/
```

This folder is ignored by git.

Each trace file is named like:

```text
trace-YYYY-MM-DD_HH-MM-SS-<trace_id>.json
```

Fusion Agent responses include:

- `trace_id`
- `trace_path`

## Commands

List recent traces:

```bash
python -m observability.inspect_traces --list
```

Tail the compact trace index:

```bash
tail -n 30 data/query_traces.jsonl
```

Inspect the newest trace:

```bash
python -m observability.inspect_traces --latest
```

The inspector marks spans over 3 seconds as slow and shows the slowest span at the top. This is useful for spotting whether latency came from routing, SQL, RAG, Web, validation, or final answer generation.

Inspect a specific trace:

```bash
python -m observability.inspect_traces --file traces/trace-YYYY-MM-DD_HH-MM-SS-id.json
```

Print raw trace JSON:

```bash
python -m observability.inspect_traces --latest --json
```

## Disable Tracing

Tracing is enabled by default. Disable it with:

```bash
NEXUSIQ_TRACE_ENABLED=0 python main.py
```

Or choose a custom trace directory:

```bash
NEXUSIQ_TRACE_DIR=/tmp/nexusiq-traces python main.py
```

Disable answer/source previews inside traces:

```bash
NEXUSIQ_TRACE_INCLUDE_PREVIEWS=0 python main.py
```

Limit how many local trace files are retained:

```bash
NEXUSIQ_TRACE_MAX_FILES=100 python main.py
```

## How To Use With Evals

Run a small golden eval:

```bash
python -m evals.golden_eval --limit 3 --delay 10
```

Then inspect the latest trace:

```bash
python -m observability.inspect_traces --latest
```

If an eval fails, use the trace to identify the failure layer:

- wrong route: inspect `routing`
- SQL failure: inspect `agent.sql`
- RAG retrieval issue: inspect `agent.rag`
- Web issue: inspect `agent.web`
- validation mismatch: inspect `validation.cross_source`
- answer synthesis issue: inspect `fusion.answer_generation`

Golden eval JSON results include each response's `trace_id` and `trace_path` when tracing is enabled. Non-passing Markdown report sections also include the trace path, so failures can be debugged from the exact run rather than guessed from the final answer alone.

For non-passing golden eval cases, the Markdown report also summarizes slow/error trace spans when the trace file is available.

## Relationship To Evals

Evals answer:

```text
Did NexusIQ produce the expected behavior?
```

Observability answers:

```text
What happened inside NexusIQ while producing that behavior?
```

Context engineering comes after this. Once traces show where failures happen, prompts, source context, retrieval rules, or schemas can be improved with evidence.
