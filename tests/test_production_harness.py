import unittest
from contextlib import contextmanager
from unittest.mock import patch

from agents.production_harness import (
    HarnessConfig,
    HarnessStepLimitExceeded,
    InMemoryHarnessStateStore,
    ProductionAgentHarness,
)


class FakeTrace:
    def __init__(self):
        self.events = []
        self.spans = []
        self.trace_id = "fake-trace"

    @contextmanager
    def span(self, name, metadata=None):
        span = {"name": name, "metadata": metadata or {}, "status": "ok", "error": None}
        self.spans.append(span)
        yield span

    def record_event(self, name, metadata=None):
        self.events.append({"name": name, "metadata": metadata or {}})


class FakeTracer:
    def __init__(self):
        self.trace = FakeTrace()

    def start_trace(self, question, metadata=None):
        self.trace.question = question
        self.trace.metadata = metadata or {}
        return self.trace


class FakeFusionAgent:
    WEB_CATEGORIES = ("electronics", "clothing", "home", "food", "sports")

    def __init__(self, route="sql_only", cached=None, fail_sql_once=False):
        self.route = route
        self.cached = cached
        self.fail_sql_once = fail_sql_once
        self.sql_attempts = 0
        self.calls = []
        self._last_routing_model = None
        self._last_routing_fallback = False
        self._no_data_reason = None
        self._last_answer_generation = {}
        self.finalize_calls = 0

    def _cache_get(self, question):
        self.calls.append(("cache_get", question))
        return self.cached

    def _rule_based_web_route(self, question):
        return None

    def _classify_query_source_llm(self, question):
        self.calls.append(("route", question))
        self._last_routing_model = "fake-router"
        return self.route

    def _classify_query_source(self, question):
        return self.route

    def _resolve_question(self, question):
        self.calls.append(("resolve", question))
        return question

    def _run_agent_with_trace(self, trace, key, runner, question):
        self.calls.append((key, question))
        return runner(question)

    def _run_sql_query(self, question):
        self.sql_attempts += 1
        if self.fail_sql_once and self.sql_attempts == 1:
            raise RuntimeError("transient sql failure")
        return {"success": True, "answer": "SQL answer", "results": [{"revenue": 1000}]}

    def _run_rag_query(self, question):
        return {
            "success": True,
            "answer": "RAG answer",
            "sources": [{"filename": "report.pdf"}],
            "chunks_retrieved": 1,
        }

    def _run_web_query(self, question, selected_category=None):
        return {"success": True, "answer": "Web answer", "category": selected_category or "electronics"}

    def _run_agents_parallel(self, question, run_sql, run_rag, run_web, progress_cb=None, trace=None):
        self.calls.append(("parallel", run_sql, run_rag, run_web))
        sql = self._run_sql_query(question) if run_sql else None
        rag = self._run_rag_query(question) if run_rag else None
        web = self._run_web_query(question) if run_web else None
        return sql, rag, web

    def _cross_validate(self, sql_result, rag_result):
        self.calls.append(("validate",))
        return {
            "validated": True,
            "confidence": "HIGH",
            "confidence_reason": "fake validation",
            "matches": [{"sql_value": 1000, "rag_value": 1000}],
            "discrepancies": [],
        }

    def _degraded_source_type(self, source_type, sql_result, rag_result, web_result):
        return source_type

    def _generate_fused_answer(self, question, sql_result=None, rag_result=None, web_result=None, validation=None):
        self.calls.append(("answer", bool(sql_result), bool(rag_result), bool(web_result), bool(validation)))
        self._last_answer_generation = {
            "mode": "deterministic_test",
            "reason": "test",
            "model_used": None,
        }
        return "Fused answer"

    def _should_cache_result(self, source_type, result):
        self.calls.append(("cache_admission", source_type))
        return False, "test_no_cache"

    def _cache_set(self, question, result):
        self.calls.append(("cache_set", question))

    def _collect_answer_models(self, result):
        return "n/a"

    def _finalize_trace(self, trace, result, cached=False):
        self.finalize_calls += 1
        finalized = dict(result)
        finalized["trace_id"] = trace.trace_id
        finalized["_finalized_cached"] = cached
        return finalized


class ProductionHarnessTests(unittest.TestCase):
    def _query(self, agent, **kwargs):
        store = InMemoryHarnessStateStore()
        harness = ProductionAgentHarness(
            agent,
            state_store=store,
            config=HarnessConfig(max_steps=12, max_attempts_per_step=2),
        )
        tracer = FakeTracer()
        with patch.dict("os.environ", {"NEXUSIQ_USE_LANGGRAPH": "false"}, clear=False), \
             patch("agents.production_harness.get_tracer", return_value=tracer):
            result = harness.query("What was revenue?", **kwargs)
        state = next(iter(store.states.values()))
        return result, state, tracer.trace

    def test_harness_runs_sql_rag_with_state_and_validation(self):
        agent = FakeFusionAgent(route="sql_rag")

        result, state, trace = self._query(agent)

        self.assertEqual(result["orchestrator"], "production_harness")
        self.assertEqual(result["source_type"], "sql_rag")
        self.assertEqual(result["answer"], "Fused answer")
        self.assertEqual(result["validation"]["confidence"], "HIGH")
        self.assertIn("run_multi_source", result["harness_completed_steps"])
        self.assertIn("generate_fused_answer", result["harness_completed_steps"])
        self.assertEqual(state.status, "completed")
        self.assertTrue(any(span["name"] == "harness.route_question" for span in trace.spans))

    def test_harness_retries_transient_single_source_failure(self):
        agent = FakeFusionAgent(route="sql_only", fail_sql_once=True)

        result, state, _trace = self._query(agent)

        self.assertEqual(result["answer"], "SQL answer")
        self.assertEqual(agent.sql_attempts, 2)
        run_sql_steps = [step for step in state.steps if step.name == "run_sql"]
        self.assertEqual(run_sql_steps[0].attempts, 2)
        self.assertEqual(run_sql_steps[0].status, "completed")

    def test_harness_cache_hit_skips_routing(self):
        agent = FakeFusionAgent(route="sql_only", cached={"answer": "Cached", "source_type": "sql_only"})

        result, state, trace = self._query(agent)

        self.assertEqual(result["answer"], "Cached")
        self.assertTrue(result["_finalized_cached"])
        self.assertNotIn(("route", "What was revenue?"), agent.calls)
        self.assertEqual(state.completed_steps, ["cache_lookup"])
        self.assertTrue(any(event["name"] == "cache.hit" for event in trace.events))

    def test_harness_enforces_step_limit(self):
        agent = FakeFusionAgent(route="sql_rag")
        store = InMemoryHarnessStateStore()
        harness = ProductionAgentHarness(
            agent,
            state_store=store,
            config=HarnessConfig(max_steps=2, max_attempts_per_step=1),
        )
        tracer = FakeTracer()

        with patch.dict("os.environ", {"NEXUSIQ_USE_LANGGRAPH": "false"}, clear=False), \
             patch("agents.production_harness.get_tracer", return_value=tracer):
            result = harness.query("What was revenue?")

        self.assertEqual(result["source_type"], "error")
        self.assertIn("step limit", result["answer"].lower())
        state = next(iter(store.states.values()))
        self.assertEqual(state.status, "failed")

    def test_harness_uses_langgraph_as_primary_engine(self):
        agent = FakeFusionAgent(route="sql_rag")
        store = InMemoryHarnessStateStore()
        harness = ProductionAgentHarness(agent, state_store=store)
        tracer = FakeTracer()

        with patch.dict("os.environ", {"NEXUSIQ_USE_LANGGRAPH": "true"}, clear=False), \
             patch("agents.production_harness.get_tracer", return_value=tracer):
            result = harness.query("What was revenue?")

        self.assertEqual(result["orchestrator"], "production_harness")
        self.assertEqual(result["harness_engine"], "langgraph")
        self.assertEqual(result["workflow_orchestrator"], "langgraph")
        self.assertIn("run_langgraph_workflow", result["harness_completed_steps"])
        self.assertEqual(agent.finalize_calls, 1)
        self.assertTrue(any(span["name"] == "langgraph.route" for span in tracer.trace.spans))

    def test_harness_falls_back_to_native_flow_when_langgraph_fails(self):
        agent = FakeFusionAgent(route="sql_rag")
        store = InMemoryHarnessStateStore()
        harness = ProductionAgentHarness(agent, state_store=store)
        tracer = FakeTracer()

        with patch.dict("os.environ", {"NEXUSIQ_USE_LANGGRAPH": "true"}, clear=False), \
             patch("agents.production_harness.get_tracer", return_value=tracer), \
             patch("agents.production_harness.ProductionAgentHarness._run_langgraph_workflow", side_effect=RuntimeError("graph down")):
            result = harness.query("What was revenue?")

        self.assertEqual(result["orchestrator"], "production_harness")
        self.assertEqual(result["source_type"], "sql_rag")
        self.assertEqual(result["answer"], "Fused answer")
        self.assertIn("run_langgraph_workflow", result["harness_failed_steps"])
        self.assertIn("run_multi_source", result["harness_completed_steps"])
        self.assertTrue(any(event["name"] == "harness.langgraph_fallback" for event in tracer.trace.events))


if __name__ == "__main__":
    unittest.main()
