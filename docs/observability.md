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
