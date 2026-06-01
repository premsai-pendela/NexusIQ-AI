"""
Production harness for NexusIQ FusionAgent.

The harness owns task control: bounded steps, state snapshots, retry/recovery,
and explicit orchestration metadata. It deliberately reuses FusionAgent's
existing routing, agent execution, validation, cache, and answer generation.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from observability.tracer import TraceSession, get_tracer

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class HarnessStep:
    name: str
    status: str
    attempts: int = 0
    started_at: str = field(default_factory=_utc_now)
    ended_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessTaskState:
    task_id: str
    question: str
    status: str = "running"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    steps: List[HarnessStep] = field(default_factory=list)
    result_summary: Dict[str, Any] = field(default_factory=dict)

    def mark_updated(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HarnessStateStore:
    def save(self, state: HarnessTaskState) -> None:
        raise NotImplementedError


class InMemoryHarnessStateStore(HarnessStateStore):
    def __init__(self) -> None:
        self.states: Dict[str, HarnessTaskState] = {}

    def save(self, state: HarnessTaskState) -> None:
        self.states[state.task_id] = state


class JsonlHarnessStateStore(HarnessStateStore):
    """Append-only task state store for local production debugging."""

    def __init__(self, path: Optional[Path] = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "data" / "harness_tasks.jsonl"
        self.path = Path(os.getenv("NEXUSIQ_HARNESS_STATE_PATH", str(path or default_path)))

    def save(self, state: HarnessTaskState) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(state.to_dict(), default=str) + "\n")
        except OSError as exc:
            logger.warning("Harness state save failed: %s", exc)


@dataclass
class HarnessConfig:
    max_steps: int = 12
    max_attempts_per_step: int = 2
    retry_backoff_s: float = 0.0


class HarnessStepLimitExceeded(RuntimeError):
    pass


class ProductionAgentHarness:
    """Controlled orchestration wrapper for FusionAgent."""

    def __init__(
        self,
        fusion_agent: Any,
        *,
        state_store: Optional[HarnessStateStore] = None,
        config: Optional[HarnessConfig] = None,
    ) -> None:
        self.fusion_agent = fusion_agent
        self.state_store = state_store or JsonlHarnessStateStore()
        self.config = config or HarnessConfig()

    def query(
        self,
        question: str,
        force_source: Optional[str] = None,
        progress_cb: Optional[Callable[[str, Dict], None]] = None,
        bypass_cache: bool = False,
        web_category: Optional[str] = None,
    ) -> Dict:
        trace = get_tracer().start_trace(
            question,
            {
                "force_source": force_source,
                "bypass_cache": bypass_cache,
                "environment": getattr(settings, "environment", "unknown"),
                "orchestrator": "production_harness",
                "max_steps": self.config.max_steps,
                "max_attempts_per_step": self.config.max_attempts_per_step,
            },
        )
        task = HarnessTaskState(task_id=uuid.uuid4().hex[:16], question=question)
        self._save(task)
        start_time = datetime.now()

        try:
            result = self._execute(
                task,
                trace,
                question=question,
                force_source=force_source,
                progress_cb=progress_cb,
                bypass_cache=bypass_cache,
                web_category=web_category,
                start_time=start_time,
            )
            task.status = "completed"
        except HarnessStepLimitExceeded as exc:
            result = {
                "answer": (
                    "NexusIQ stopped this task before it could waste more tokens. "
                    "The production harness step limit was reached."
                ),
                "source_type": "error",
                "error": str(exc),
                "query_time": (datetime.now() - start_time).total_seconds(),
            }
            task.status = "failed"
        except Exception as exc:
            logger.exception("Production harness failed")
            result = {
                "answer": "NexusIQ could not complete this request safely.",
                "source_type": "error",
                "error": str(exc),
                "query_time": (datetime.now() - start_time).total_seconds(),
            }
            task.status = "failed"

        result["orchestrator"] = "production_harness"
        result["harness_task_id"] = task.task_id
        result["harness_steps"] = [step.name for step in task.steps]
        result["harness_completed_steps"] = list(task.completed_steps)
        result["harness_failed_steps"] = list(task.failed_steps)

        task.result_summary = {
            "source_type": result.get("source_type"),
            "answer_present": bool(result.get("answer")),
            "error": result.get("error"),
            "trace_id": result.get("trace_id"),
        }
        task.mark_updated()
        self._save(task)
        return self.fusion_agent._finalize_trace(trace, result, cached=bool(result.get("_from_cache")))

    def _execute(
        self,
        task: HarnessTaskState,
        trace: TraceSession,
        *,
        question: str,
        force_source: Optional[str],
        progress_cb: Optional[Callable[[str, Dict], None]],
        bypass_cache: bool,
        web_category: Optional[str],
        start_time: datetime,
    ) -> Dict:
        agent = self.fusion_agent

        if self._use_langgraph_primary():
            try:
                result = self._run_step(
                    task,
                    trace,
                    "run_langgraph_workflow",
                    lambda: self._run_langgraph_workflow(
                        question=question,
                        force_source=force_source,
                        progress_cb=progress_cb,
                        bypass_cache=bypass_cache,
                        web_category=web_category,
                    ),
                    retryable=True,
                )
                if result.get("source_type") != "error":
                    result["harness_engine"] = "langgraph"
                    result["workflow_orchestrator"] = result.get("orchestrator", "langgraph")
                    return result
                trace.record_event(
                    "harness.langgraph_fallback",
                    {
                        "reason": "langgraph_returned_error",
                        "error": result.get("error"),
                    },
                )
            except Exception as exc:
                trace.record_event(
                    "harness.langgraph_fallback",
                    {
                        "reason": "langgraph_exception",
                        "error": str(exc)[:500],
                    },
                )

        cached = self._run_step(
            task,
            trace,
            "cache_lookup",
            lambda: self._cache_lookup(trace, question, force_source, bypass_cache),
            retryable=False,
        )
        if cached:
            cached["query_time"] = 0
            return cached

        source_type = self._run_step(
            task,
            trace,
            "route_question",
            lambda: self._route_question(trace, question, force_source),
            retryable=True,
        )
        resolved_question = self._run_step(
            task,
            trace,
            "resolve_question",
            lambda: self._resolve_question(trace, question),
            retryable=True,
        )

        if source_type == "no_data":
            return self._build_no_data(start_time, source_type)

        if source_type == "sql_only":
            sql_result = self._run_step(
                task,
                trace,
                "run_sql",
                lambda: agent._run_agent_with_trace(
                    trace, "sql", agent._run_sql_query, resolved_question
                ),
                retryable=True,
            )
            return self._single_source_result(
                start_time, source_type, sql_result=sql_result
            )

        if source_type == "rag_only":
            rag_result = self._run_step(
                task,
                trace,
                "run_rag",
                lambda: agent._run_agent_with_trace(
                    trace, "rag", agent._run_rag_query, resolved_question
                ),
                retryable=True,
            )
            return self._single_source_result(
                start_time, source_type, rag_result=rag_result
            )

        if source_type == "web_only":
            web_runner = lambda query: agent._run_web_query(query, selected_category=web_category)
            web_result = self._run_step(
                task,
                trace,
                "run_web",
                lambda: agent._run_agent_with_trace(trace, "web", web_runner, resolved_question),
                retryable=True,
            )
            return self._single_source_result(
                start_time, source_type, web_result=web_result
            )

        if source_type == "comparison":
            rag_result = self._run_step(
                task,
                trace,
                "run_rag_comparison",
                lambda: agent._run_agent_with_trace(
                    trace, "rag", agent._run_rag_query, resolved_question
                ),
                retryable=True,
            )
            return self._single_source_result(
                start_time, source_type, rag_result=rag_result
            )

        sql_result, rag_result, web_result = self._run_step(
            task,
            trace,
            "run_multi_source",
            lambda: self._run_multi_source(
                trace, resolved_question, source_type, progress_cb=progress_cb
            ),
            retryable=False,
        )
        validation = self._run_step(
            task,
            trace,
            "validate_sources",
            lambda: self._validate_sources(trace, sql_result, rag_result),
            retryable=False,
        )
        answer_result = self._run_step(
            task,
            trace,
            "generate_fused_answer",
            lambda: self._generate_fused_answer(
                trace,
                question,
                source_type,
                sql_result,
                rag_result,
                web_result,
                validation,
                start_time,
            ),
            retryable=True,
        )
        self._run_step(
            task,
            trace,
            "cache_admission",
            lambda: self._cache_admission(trace, question, force_source, answer_result),
            retryable=False,
        )
        return answer_result

    def _use_langgraph_primary(self) -> bool:
        if os.getenv("NEXUSIQ_HARNESS_ENGINE", "").strip().lower() in {"legacy", "native"}:
            return False
        return os.getenv("NEXUSIQ_USE_LANGGRAPH", "true").strip().lower() in {"1", "true", "yes", "on"}

    def _run_langgraph_workflow(
        self,
        *,
        question: str,
        force_source: Optional[str],
        progress_cb: Optional[Callable[[str, Dict], None]],
        bypass_cache: bool,
        web_category: Optional[str],
    ) -> Dict:
        from agents.fusion_graph import FusionGraph

        if not hasattr(self.fusion_agent, "_fusion_graph"):
            self.fusion_agent._fusion_graph = FusionGraph(self.fusion_agent)
        return self.fusion_agent._fusion_graph.query(
            question,
            force_source=force_source,
            progress_cb=progress_cb,
            bypass_cache=bypass_cache,
            web_category=web_category,
        )

    def _run_step(
        self,
        task: HarnessTaskState,
        trace: TraceSession,
        name: str,
        func: Callable[[], Any],
        *,
        retryable: bool,
    ) -> Any:
        if len(task.steps) >= self.config.max_steps:
            raise HarnessStepLimitExceeded(
                f"max_steps={self.config.max_steps} reached before {name}"
            )

        step = HarnessStep(name=name, status="running")
        task.current_step = name
        task.steps.append(step)
        task.mark_updated()
        self._save(task)

        attempts = self.config.max_attempts_per_step if retryable else 1
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            step.attempts = attempt
            with trace.span(
                f"harness.{name}",
                {"attempt": attempt, "max_attempts": attempts},
            ) as span:
                try:
                    result = func()
                    step.status = "completed"
                    step.ended_at = _utc_now()
                    step.error = None
                    task.completed_steps.append(name)
                    task.current_step = None
                    task.mark_updated()
                    self._save(task)
                    span["metadata"]["status"] = "completed"
                    return result
                except Exception as exc:
                    last_error = exc
                    step.error = str(exc)[:500]
                    span["status"] = "error"
                    span["error"] = str(exc)[:500]
                    span["metadata"]["will_retry"] = attempt < attempts
                    if attempt < attempts and self.config.retry_backoff_s > 0:
                        time.sleep(self.config.retry_backoff_s)

        step.status = "failed"
        step.ended_at = _utc_now()
        task.failed_steps.append(name)
        task.current_step = None
        task.mark_updated()
        self._save(task)
        raise last_error or RuntimeError(f"Harness step failed: {name}")

    def _save(self, task: HarnessTaskState) -> None:
        self.state_store.save(task)

    def _cache_lookup(
        self,
        trace: TraceSession,
        question: str,
        force_source: Optional[str],
        bypass_cache: bool,
    ) -> Optional[Dict]:
        if bypass_cache:
            trace.record_event("cache.bypass", {"reason": "user_requested_fresh_answer"})
            return None
        if force_source:
            return None
        cached = self.fusion_agent._cache_get(question)
        if cached:
            cached = dict(cached, _from_cache=True)
            trace.record_event(
                "cache.hit",
                {
                    "source_type": cached.get("source_type"),
                    "previous_trace_id": cached.get("trace_id"),
                    "orchestrator": "production_harness",
                },
            )
        return cached

    def _route_question(
        self,
        trace: TraceSession,
        question: str,
        force_source: Optional[str],
    ) -> str:
        agent = self.fusion_agent
        agent._last_routing_model = None
        agent._last_routing_fallback = False
        agent._no_data_reason = None

        if force_source:
            source_type = force_source
        else:
            source_type = agent._rule_based_web_route(question)
            if source_type:
                agent._last_routing_model = agent._last_routing_model or "Rules-based Web routing"
            else:
                source_type = agent._classify_query_source_llm(question)
                if not source_type:
                    source_type = agent._classify_query_source(question)
                    agent._last_routing_model = "keyword fallback"
                    agent._last_routing_fallback = True

        trace.record_event(
            "harness.route.selected",
            {
                "source_type": source_type,
                "routing_model": agent._last_routing_model,
                "routing_fallback": agent._last_routing_fallback,
                "no_data_reason": agent._no_data_reason,
            },
        )
        return source_type

    def _resolve_question(self, trace: TraceSession, question: str) -> str:
        resolved = self.fusion_agent._resolve_question(question)
        trace.record_event(
            "harness.question.resolved",
            {"changed": resolved != question},
        )
        return resolved

    def _run_multi_source(
        self,
        trace: TraceSession,
        question: str,
        source_type: str,
        *,
        progress_cb: Optional[Callable[[str, Dict], None]],
    ) -> tuple:
        run_all_sources = source_type == "all"
        return self.fusion_agent._run_agents_parallel(
            question,
            run_sql=run_all_sources or "sql" in source_type,
            run_rag=run_all_sources or "rag" in source_type,
            run_web=(run_all_sources or "web" in source_type) and settings.ENABLE_WEB_AGENT,
            progress_cb=progress_cb,
            trace=trace,
        )

    def _validate_sources(
        self,
        trace: TraceSession,
        sql_result: Optional[Dict],
        rag_result: Optional[Dict],
    ) -> Optional[Dict]:
        if sql_result and rag_result and sql_result.get("success") and rag_result.get("success"):
            validation = self.fusion_agent._cross_validate(sql_result, rag_result)
            trace.record_event(
                "harness.validation.completed",
                {
                    "confidence": validation.get("confidence"),
                    "matches": len(validation.get("matches", [])),
                    "discrepancies": len(validation.get("discrepancies", [])),
                },
            )
            return validation
        return None

    def _generate_fused_answer(
        self,
        trace: TraceSession,
        question: str,
        source_type: str,
        sql_result: Optional[Dict],
        rag_result: Optional[Dict],
        web_result: Optional[Dict],
        validation: Optional[Dict],
        start_time: datetime,
    ) -> Dict:
        agent = self.fusion_agent
        final_source_type = agent._degraded_source_type(source_type, sql_result, rag_result, web_result)
        agent._last_answer_generation = {}
        answer = agent._generate_fused_answer(
            question,
            sql_result,
            rag_result,
            web_result,
            validation,
        )
        trace.record_event(
            "harness.answer.generated",
            {
                "source_type": final_source_type,
                "mode": agent._last_answer_generation.get("mode"),
            },
        )
        return {
            "answer": answer,
            "source_type": final_source_type,
            "sql_result": sql_result,
            "rag_result": rag_result,
            "web_result": web_result,
            "validation": validation,
            "sources": rag_result.get("sources", []) if rag_result else [],
            "routing_model": agent._last_routing_model,
            "routing_fallback": agent._last_routing_fallback,
            "answer_generation_mode": agent._last_answer_generation.get("mode"),
            "answer_generation_reason": agent._last_answer_generation.get("reason"),
            "fusion_model_used": agent._last_answer_generation.get("model_used"),
            "query_time": (datetime.now() - start_time).total_seconds(),
        }

    def _cache_admission(
        self,
        trace: TraceSession,
        question: str,
        force_source: Optional[str],
        result: Dict,
    ) -> None:
        if force_source:
            return
        should_cache, cache_reason = self.fusion_agent._should_cache_result(
            result.get("source_type", ""), result
        )
        trace.record_event(
            "cache.admission",
            {
                "accepted": should_cache,
                "reason": cache_reason,
                "source_type": result.get("source_type"),
                "orchestrator": "production_harness",
            },
        )
        if should_cache:
            self.fusion_agent._cache_set(question, result)

    def _build_no_data(self, start_time: datetime, source_type: str) -> Dict:
        reason = self.fusion_agent._no_data_reason or "No available data source covers this query."
        return {
            "answer": (
                "I don't have data to answer this question.\n\n"
                f"**Reason:** {reason}\n\n"
                "Available data covers: SQL transactions (2024 only), internal PDF documents, "
                "and live competitor pricing."
            ),
            "source_type": source_type,
            "sql_result": None,
            "rag_result": None,
            "web_result": None,
            "validation": None,
            "routing_model": self.fusion_agent._last_routing_model,
            "routing_fallback": self.fusion_agent._last_routing_fallback,
            "query_time": (datetime.now() - start_time).total_seconds(),
        }

    def _single_source_result(
        self,
        start_time: datetime,
        source_type: str,
        *,
        sql_result: Optional[Dict] = None,
        rag_result: Optional[Dict] = None,
        web_result: Optional[Dict] = None,
    ) -> Dict:
        source_result = sql_result or rag_result or web_result or {}
        return {
            "answer": source_result.get("answer", "No answer generated"),
            "source_type": source_type,
            "sql_result": sql_result,
            "rag_result": rag_result,
            "web_result": web_result,
            "validation": None,
            "sources": rag_result.get("sources", []) if rag_result else [],
            "routing_model": self.fusion_agent._last_routing_model,
            "routing_fallback": self.fusion_agent._last_routing_fallback,
            "query_time": (datetime.now() - start_time).total_seconds(),
        }
