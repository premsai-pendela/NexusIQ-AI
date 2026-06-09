"""
Optional LangGraph orchestration for NexusIQ FusionAgent.

This module keeps SQLAgent, RAGAgent, WebAgent, validation, and answer
generation unchanged. LangGraph owns only the workflow shape.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from config.settings import settings
from observability.tracer import TraceSession, get_tracer

logger = logging.getLogger(__name__)


class NexusIQGraphState(TypedDict, total=False):
    question: str
    resolved_question: str
    force_source: Optional[str]
    progress_cb: Optional[Callable[[str, Dict], None]]
    bypass_cache: bool
    web_category: Optional[str]
    trace: TraceSession
    start_time: datetime
    source_type: str
    sql_result: Optional[Dict]
    rag_result: Optional[Dict]
    web_result: Optional[Dict]
    validation: Optional[Dict]
    answer: Optional[str]
    result: Optional[Dict]
    cached: bool
    finalize_trace: bool


class FusionGraph:
    """LangGraph wrapper around the existing FusionAgent implementation."""

    def __init__(self, fusion_agent: Any):
        self.fusion_agent = fusion_agent
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(NexusIQGraphState)

        workflow.add_node("cache_lookup", self._cache_lookup)
        workflow.add_node("route_question", self._route_question)
        workflow.add_node("resolve_question", self._resolve_question)
        workflow.add_node("build_no_data", self._build_no_data)
        workflow.add_node("run_sql_only", self._run_sql_only)
        workflow.add_node("run_rag_only", self._run_rag_only)
        workflow.add_node("run_web_only", self._run_web_only)
        workflow.add_node("run_comparison", self._run_comparison)
        workflow.add_node("run_multi_source", self._run_multi_source)
        workflow.add_node("validate_sources", self._validate_sources)
        workflow.add_node("generate_fused_answer", self._generate_fused_answer)
        workflow.add_node("cache_admission", self._cache_admission)
        workflow.add_node("finalize", self._finalize)

        workflow.add_edge(START, "cache_lookup")
        workflow.add_conditional_edges(
            "cache_lookup",
            self._after_cache_lookup,
            {
                "finalize": "finalize",
                "route_question": "route_question",
            },
        )
        workflow.add_edge("route_question", "resolve_question")
        workflow.add_conditional_edges(
            "resolve_question",
            self._route_to_execution,
            {
                "no_data": "build_no_data",
                "sql_only": "run_sql_only",
                "rag_only": "run_rag_only",
                "web_only": "run_web_only",
                "comparison": "run_comparison",
                "multi_source": "run_multi_source",
            },
        )
        workflow.add_edge("build_no_data", "finalize")
        workflow.add_edge("run_sql_only", "finalize")
        workflow.add_edge("run_rag_only", "finalize")
        workflow.add_edge("run_web_only", "finalize")
        workflow.add_edge("run_comparison", "finalize")
        workflow.add_edge("run_multi_source", "validate_sources")
        workflow.add_edge("validate_sources", "generate_fused_answer")
        workflow.add_edge("generate_fused_answer", "cache_admission")
        workflow.add_edge("cache_admission", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def query(
        self,
        question: str,
        force_source: Optional[str] = None,
        progress_cb: Optional[Callable[[str, Dict], None]] = None,
        bypass_cache: bool = False,
        web_category: Optional[str] = None,
        trace: Optional[TraceSession] = None,
    ) -> Dict:
        owns_trace = trace is None
        if owns_trace:
            trace = get_tracer().start_trace(
                question,
                {
                    "force_source": force_source,
                    "bypass_cache": bypass_cache,
                    "environment": getattr(settings, "environment", "unknown"),
                    "orchestrator": "langgraph",
                },
            )
        initial_state: NexusIQGraphState = {
            "question": question,
            "force_source": force_source,
            "progress_cb": progress_cb,
            "bypass_cache": bypass_cache,
            "web_category": web_category,
            "trace": trace,
            "start_time": datetime.now(),
            "cached": False,
            "finalize_trace": owns_trace,
        }
        final_state = self.graph.invoke(initial_state)
        result = final_state.get("result") or {
            "answer": "NexusIQ could not produce an answer.",
            "source_type": "error",
            "query_time": 0,
        }
        return result

    def _cache_lookup(self, state: NexusIQGraphState) -> Dict:
        trace = state["trace"]
        question = state["question"]
        if state.get("bypass_cache"):
            trace.record_event("cache.bypass", {"reason": "user_requested_fresh_answer"})
            return {}
        if not state.get("force_source"):
            cached = self.fusion_agent._cache_get(question)
            if cached:
                llm_usage = cached.get("llm_usage") or {}
                trace.record_event(
                    "cache.hit",
                    {
                        "source_type": cached.get("source_type"),
                        "previous_trace_id": cached.get("trace_id"),
                        "orchestrator": "langgraph",
                        "saved_successful_calls": llm_usage.get("successful_calls", 0),
                        "saved_estimated_tokens": llm_usage.get("successful_estimated_tokens", 0),
                        "saved_actual_tokens": llm_usage.get("actual_tokens", 0),
                    },
                )
                trace.record_event(
                    "llm.call_skipped",
                    {
                        "task": "query_execution",
                        "reason": "cache_hit_reused_previous_answer",
                        "orchestrator": "langgraph",
                        "saved_successful_calls": llm_usage.get("successful_calls", 0),
                        "saved_estimated_tokens": llm_usage.get("successful_estimated_tokens", 0),
                        "saved_actual_tokens": llm_usage.get("actual_tokens", 0),
                    },
                )
                cached["query_time"] = 0
                return {"result": cached, "cached": True}
        return {}

    @staticmethod
    def _after_cache_lookup(state: NexusIQGraphState) -> str:
        return "finalize" if state.get("result") else "route_question"

    def _route_question(self, state: NexusIQGraphState) -> Dict:
        agent = self.fusion_agent
        question = state["question"]
        force_source = state.get("force_source")
        trace = state["trace"]

        agent._last_routing_model = None
        agent._last_routing_fallback = False
        agent._no_data_reason = None

        with trace.span("langgraph.route", {"forced": bool(force_source)}) as span:
            if force_source:
                source_type = force_source
                logger.info("LangGraph routing forced to %s", source_type)
            else:
                rule_router = getattr(agent, "_rule_based_source_route", agent._rule_based_web_route)
                source_type = rule_router(question)
                if source_type:
                    logger.info("LangGraph rule-based routing selected %s", source_type)
                    trace.record_event(
                        "llm.call_skipped",
                        {
                            "task": "fusion.route",
                            "reason": "rule_based_routing_selected_source",
                            "source_type": source_type,
                            "routing_model": agent._last_routing_model,
                            "orchestrator": "langgraph",
                        },
                    )
                else:
                    source_type = agent._classify_query_source_llm(question)
                    if not source_type:
                        source_type = agent._classify_query_source(question)
                        agent._last_routing_model = "keyword fallback"
                        agent._last_routing_fallback = True

            span["metadata"].update(
                {
                    "source_type": source_type,
                    "routing_model": agent._last_routing_model,
                    "routing_fallback": agent._last_routing_fallback,
                    "no_data_reason": agent._no_data_reason,
                }
            )
        return {"source_type": source_type}

    def _resolve_question(self, state: NexusIQGraphState) -> Dict:
        question = state["question"]
        with state["trace"].span("langgraph.resolve_question") as span:
            resolved = self.fusion_agent._resolve_question(question)
            span["metadata"]["original"] = question
            span["metadata"]["resolved"] = resolved
            span["metadata"]["changed"] = resolved != question
        return {"resolved_question": resolved}

    @staticmethod
    def _route_to_execution(state: NexusIQGraphState) -> str:
        source_type = state.get("source_type", "sql_only")
        if source_type in {"no_data", "sql_only", "rag_only", "web_only", "comparison"}:
            return source_type
        return "multi_source"

    def _elapsed(self, state: NexusIQGraphState) -> float:
        return (datetime.now() - state["start_time"]).total_seconds()

    def _base_result(self, state: NexusIQGraphState, **overrides) -> Dict:
        result = {
            "source_type": state.get("source_type"),
            "routing_model": self.fusion_agent._last_routing_model,
            "routing_fallback": self.fusion_agent._last_routing_fallback,
            "query_time": self._elapsed(state),
        }
        result.update(overrides)
        return result

    def _build_no_data(self, state: NexusIQGraphState) -> Dict:
        reason = self.fusion_agent._no_data_reason or "No available data source covers this query."
        result = self._base_result(
            state,
            answer=(
                "I don't have data to answer this question.\n\n"
                f"**Reason:** {reason}\n\n"
                "Available data covers: SQL transactions (2024 only), internal PDF documents, "
                "and live competitor pricing."
            ),
            sql_result=None,
            rag_result=None,
            web_result=None,
            validation=None,
        )
        return {"result": result}

    def _run_sql_only(self, state: NexusIQGraphState) -> Dict:
        sql_result = self.fusion_agent._run_agent_with_trace(
            state["trace"], "sql", self.fusion_agent._run_sql_query, state["resolved_question"]
        )
        result = self._base_result(
            state,
            answer=sql_result.get("answer", "No answer generated"),
            sql_result=sql_result,
            rag_result=None,
            web_result=None,
            validation=None,
        )
        return {"sql_result": sql_result, "result": result}

    def _run_rag_only(self, state: NexusIQGraphState) -> Dict:
        rag_result = self.fusion_agent._run_agent_with_trace(
            state["trace"], "rag", self.fusion_agent._run_rag_query, state["resolved_question"]
        )
        result = self._base_result(
            state,
            answer=rag_result.get("answer", "No answer generated"),
            sql_result=None,
            rag_result=rag_result,
            web_result=None,
            validation=None,
            sources=rag_result.get("sources", []),
        )
        return {"rag_result": rag_result, "result": result}

    def _run_web_only(self, state: NexusIQGraphState) -> Dict:
        web_runner = lambda query: self.fusion_agent._run_web_query(
            query, selected_category=state.get("web_category")
        )
        web_result = self.fusion_agent._run_agent_with_trace(
            state["trace"], "web", web_runner, state["resolved_question"]
        )
        result = self._base_result(
            state,
            answer=web_result.get("answer", "No answer generated"),
            sql_result=None,
            rag_result=None,
            web_result=web_result,
            validation=None,
        )
        return {"web_result": web_result, "result": result}

    def _run_comparison(self, state: NexusIQGraphState) -> Dict:
        rag_result = self.fusion_agent._run_agent_with_trace(
            state["trace"], "rag", self.fusion_agent._run_rag_query, state["resolved_question"]
        )
        result = self._base_result(
            state,
            answer=rag_result.get("answer", "No answer generated"),
            sql_result=None,
            rag_result=rag_result,
            web_result=None,
            validation=None,
            sources=rag_result.get("sources", []),
        )
        return {"rag_result": rag_result, "result": result}

    def _run_multi_source(self, state: NexusIQGraphState) -> Dict:
        source_type = state["source_type"]
        run_all_sources = source_type == "all"
        with state["trace"].span("langgraph.run_multi_source", {"source_type": source_type}):
            sql_result, rag_result, web_result = self.fusion_agent._run_agents_parallel(
                state["resolved_question"],
                run_sql=run_all_sources or "sql" in source_type,
                run_rag=run_all_sources or "rag" in source_type,
                run_web=(run_all_sources or "web" in source_type) and settings.ENABLE_WEB_AGENT,
                progress_cb=state.get("progress_cb"),
                trace=state["trace"],
            )
        return {
            "sql_result": sql_result,
            "rag_result": rag_result,
            "web_result": web_result,
        }

    def _validate_sources(self, state: NexusIQGraphState) -> Dict:
        sql_result = state.get("sql_result")
        rag_result = state.get("rag_result")
        if sql_result and rag_result and sql_result.get("success") and rag_result.get("success"):
            with state["trace"].span("langgraph.validation") as span:
                validation = self.fusion_agent._cross_validate(sql_result, rag_result)
                span["metadata"]["confidence"] = validation.get("confidence")
                span["metadata"]["confidence_reason"] = validation.get("confidence_reason")
                span["metadata"]["matches"] = len(validation.get("matches", []))
                span["metadata"]["discrepancies"] = len(validation.get("discrepancies", []))
            return {"validation": validation}
        return {"validation": None}

    def _generate_fused_answer(self, state: NexusIQGraphState) -> Dict:
        source_type = self.fusion_agent._degraded_source_type(
            state["source_type"],
            state.get("sql_result"),
            state.get("rag_result"),
            state.get("web_result"),
        )
        with state["trace"].span("langgraph.answer_generation") as span:
            self.fusion_agent._last_answer_generation = {}
            answer = self.fusion_agent._generate_fused_answer(
                state["question"],
                state.get("sql_result"),
                state.get("rag_result"),
                state.get("web_result"),
                state.get("validation"),
            )
            span["metadata"]["answer_preview"] = str(answer or "")[:500]
            span["metadata"].update(self.fusion_agent._last_answer_generation)

        result = self._base_result(
            state,
            source_type=source_type,
            answer=answer,
            sql_result=state.get("sql_result"),
            rag_result=state.get("rag_result"),
            web_result=state.get("web_result"),
            validation=state.get("validation"),
            sources=(state.get("rag_result") or {}).get("sources", []),
            answer_generation_mode=self.fusion_agent._last_answer_generation.get("mode"),
            answer_generation_reason=self.fusion_agent._last_answer_generation.get("reason"),
            fusion_model_used=self.fusion_agent._last_answer_generation.get("model_used"),
        )
        return {"source_type": source_type, "answer": answer, "result": result}

    def _cache_admission(self, state: NexusIQGraphState) -> Dict:
        result = state.get("result") or {}
        if state.get("force_source"):
            return {}
        should_cache, cache_reason = self.fusion_agent._should_cache_result(
            result.get("source_type", state.get("source_type", "")),
            result,
        )
        state["trace"].record_event(
            "cache.admission",
            {
                "accepted": should_cache,
                "reason": cache_reason,
                "source_type": result.get("source_type"),
                "orchestrator": "langgraph",
            },
        )
        if should_cache:
            self.fusion_agent._cache_set(state["question"], result)
        return {}

    def _finalize(self, state: NexusIQGraphState) -> Dict:
        result = state.get("result") or {}
        result["orchestrator"] = "langgraph"
        if not state.get("finalize_trace", True):
            return {"result": result}
        finalized = self.fusion_agent._finalize_trace(
            state["trace"],
            result,
            cached=bool(state.get("cached")),
        )
        return {"result": finalized}
