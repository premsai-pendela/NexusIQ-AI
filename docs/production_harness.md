# NexusIQ Production Agent Harness

The production harness is a controlled orchestration layer around the existing
Fusion Agent. It does not replace SQL, RAG, Web, validation, or answer
generation. It manages how those pieces run.

## Why It Exists

Demo agents often fail because nothing controls the work around the model. They
can repeat tool calls, lose progress after failures, retry blindly, or spend
quota on messy context.

The NexusIQ harness adds:

- bounded step execution
- per-step state snapshots
- retry attempts for retryable steps
- graceful step-limit failure
- explicit orchestration metadata in traces
- a local append-only task state log

## Default Production Path

The production harness is now the default execution path. Inside the harness,
LangGraph is the primary workflow engine. If LangGraph fails, the harness falls
back to its native controlled workflow. If the whole production layer fails,
`FusionAgent.query()` falls back to the legacy direct FusionAgent flow.

```bash
python main.py
```

For Streamlit:

```bash
streamlit run main.py
```

Opt out only for debugging:

```bash
# Bypass the production harness and use the legacy direct FusionAgent flow.
NEXUSIQ_USE_PRODUCTION_HARNESS=false streamlit run main.py

# Keep the harness, but force its native workflow instead of LangGraph.
NEXUSIQ_USE_LANGGRAPH=false streamlit run main.py

# Equivalent native-harness override.
NEXUSIQ_HARNESS_ENGINE=native streamlit run main.py
```

## What Gets Tracked

Each harness task gets a `harness_task_id` and step list:

- `cache_lookup`
- `run_langgraph_workflow` for the default LangGraph-backed workflow
- `route_question`
- `resolve_question`
- `run_sql`, `run_rag`, `run_web`, or `run_multi_source`
- `validate_sources`
- `generate_fused_answer`
- `cache_admission`

Responses include:

- `orchestrator: production_harness`
- `harness_engine: langgraph` when the default LangGraph workflow succeeds
- `workflow_orchestrator: langgraph`
- `harness_task_id`
- `harness_steps`
- `harness_completed_steps`
- `harness_failed_steps`

Local task snapshots are appended to:

```text
data/harness_tasks.jsonl
```

That file is ignored by git.

## Safety And Quota Benefits

The harness does not make the LLM smarter. It makes LLM usage more controlled.

It helps by:

- stopping work after `max_steps`
- retrying transient step failures only within a fixed budget
- avoiding repeated route/tool loops
- using the existing Fusion cache before routing
- preserving task progress for debugging
- making failures visible in traces instead of silent

## Current Scope

This first version is intentionally conservative:

- It is production-first, with explicit opt-out flags for debugging.
- It reuses existing Fusion Agent behavior.
- It stores local task state for observability, not full user-facing resume yet.
- It retries single-step failures, but does not yet resume a task after process restart.

## Next Improvements

- Add Postgres-backed task state for real multi-instance production.
- Add resume-from-step support for long-running ingestion or analysis jobs.
- Add per-step retry policies, such as different retry counts for SQL, RAG, Web,
  and answer generation.
- Add a context manager that selects only relevant history and evidence per step.
- Add planner mode for complex analysis questions that need named subtasks.

## Interview Wording

Built a production agent harness for NexusIQ that decomposes agent execution into
bounded, traceable steps, records task state, retries transient failures,
prevents runaway tool loops, and returns metadata for debugging multi-agent SQL,
RAG, and Web workflows.
