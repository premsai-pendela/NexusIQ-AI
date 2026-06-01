import unittest
from contextlib import contextmanager
from unittest.mock import patch

from agents.fusion_graph import FusionGraph


class FakeTrace:
    def __init__(self):
        self.events = []
        self.spans = []

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

    def __init__(self, route="sql_only", cached=None):
        self.route = route
        self.cached = cached
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
        return {"success": True, "answer": "SQL answer", "results": [{"revenue": 1000}]}

    def _run_rag_query(self, question):
        return {"success": True, "answer": "RAG answer", "sources": [{"filename": "report.pdf"}]}

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

    def _finalize_trace(self, trace, result, cached=False):
        self.finalize_calls += 1
        finalized = dict(result)
        finalized["trace_id"] = "fake-trace"
        finalized["_finalized_cached"] = cached
        return finalized


class FusionGraphTests(unittest.TestCase):
    def _query(self, agent, question="What was revenue?"):
        tracer = FakeTracer()
        with patch("agents.fusion_graph.get_tracer", return_value=tracer):
            result = FusionGraph(agent).query(question)
        return result, tracer.trace

    def test_sql_only_route_runs_only_sql_node(self):
        agent = FakeFusionAgent(route="sql_only")

        result, trace = self._query(agent)

        self.assertEqual(result["source_type"], "sql_only")
        self.assertEqual(result["answer"], "SQL answer")
        self.assertIn(("sql", "What was revenue?"), agent.calls)
        self.assertNotIn(("rag", "What was revenue?"), agent.calls)
        self.assertNotIn(("web", "What was revenue?"), agent.calls)
        self.assertEqual(result["orchestrator"], "langgraph")
        self.assertEqual(agent.finalize_calls, 1)
        self.assertTrue(any(span["name"] == "langgraph.route" for span in trace.spans))

    def test_sql_rag_route_runs_validation_and_fused_answer(self):
        agent = FakeFusionAgent(route="sql_rag")

        result, _trace = self._query(agent)

        self.assertEqual(result["source_type"], "sql_rag")
        self.assertEqual(result["answer"], "Fused answer")
        self.assertEqual(result["validation"]["confidence"], "HIGH")
        self.assertIn(("parallel", True, True, False), agent.calls)
        self.assertIn(("validate",), agent.calls)
        self.assertIn(("answer", True, True, False, True), agent.calls)

    def test_web_only_route_passes_selected_category(self):
        agent = FakeFusionAgent(route="web_only")
        tracer = FakeTracer()
        with patch("agents.fusion_graph.get_tracer", return_value=tracer):
            result = FusionGraph(agent).query("Show prices", web_category="clothing")

        self.assertEqual(result["source_type"], "web_only")
        self.assertEqual(result["web_result"]["category"], "clothing")
        self.assertEqual(result["answer"], "Web answer")

    def test_cache_hit_finalizes_without_routing(self):
        cached = {"answer": "Cached answer", "source_type": "sql_only"}
        agent = FakeFusionAgent(route="sql_only", cached=cached)

        result, trace = self._query(agent)

        self.assertEqual(result["answer"], "Cached answer")
        self.assertTrue(result["_finalized_cached"])
        self.assertEqual(agent.finalize_calls, 1)
        self.assertNotIn(("route", "What was revenue?"), agent.calls)
        self.assertTrue(any(event["name"] == "cache.hit" for event in trace.events))

    def test_external_trace_records_langgraph_spans_without_finalizing(self):
        agent = FakeFusionAgent(route="sql_rag")
        trace = FakeTrace()

        result = FusionGraph(agent).query("What was revenue?", trace=trace)

        self.assertEqual(result["orchestrator"], "langgraph")
        self.assertNotIn("trace_id", result)
        self.assertEqual(agent.finalize_calls, 0)
        self.assertTrue(any(span["name"] == "langgraph.route" for span in trace.spans))


if __name__ == "__main__":
    unittest.main()
