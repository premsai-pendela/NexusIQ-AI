"""Regression tests proving SQL formatting/explanation LLM calls are avoided.

These tests guard the token-optimization contract:
- Common SQL result shapes are rendered deterministically (no sql.format_answer call).
- SQL explanations default to deterministic rendering (no sql.explain_query call).
- Every avoided call is recorded in the ledger and on the active trace.
- NEXUSIQ_SQL_FORMAT_MODE / NEXUSIQ_SQL_EXPLAIN_MODE = "llm" restores LLM behavior.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.sql_agent import SQLAgent
from utils.llm_gateway import LLMGateway, llm_call_context


class GatewayStub:
    """Records avoided calls and fails loudly if an LLM invocation happens."""

    def __init__(self, allow_invoke=False):
        self.allow_invoke = allow_invoke
        self.avoided_calls = []
        self.invocations = []

    def record_avoided_call(self, **kwargs):
        self.avoided_calls.append(kwargs)

    def invoke_with_fallback(self, **kwargs):
        if not self.allow_invoke:
            raise AssertionError(f"Unexpected LLM invocation for task {kwargs.get('task')}")
        self.invocations.append(kwargs)
        return {
            "success": True,
            "response": "LLM ANSWER",
            "model_used": "stub-model",
            "models_tried": [
                {"model": "stub-model", "status": "✅ SUCCESS", "error": None, "time": 0.0,
                 "task": kwargs.get("task")}
            ],
        }


def make_agent(gateway):
    agent = SQLAgent.__new__(SQLAgent)
    agent.llm_gateway = gateway
    agent.tracker = MagicMock()
    agent.data_context = MagicMock(sql_table="sales_transactions", label="Live Demo Data")
    return agent


class DeterministicSqlFormattingTest(unittest.TestCase):
    def setUp(self):
        self.gateway = GatewayStub()
        self.agent = make_agent(self.gateway)
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("NEXUSIQ_SQL_FORMAT_MODE", None)

    def tearDown(self):
        self.env.stop()

    def _format(self, results):
        return self.agent._format_answer(
            question="test question",
            query="SELECT 1",
            results=results,
            complexity="simple",
        )

    def test_scalar_money_column_formats_as_dollars_without_llm(self):
        result = self._format([{"total_revenue": 174876543.21}])

        self.assertEqual(result["answer_mode"], "deterministic_sql_format")
        self.assertIn("$174,876,543.21", result["answer"])
        self.assertEqual(result["models_tried"], [])
        self.assertEqual(len(self.gateway.avoided_calls), 1)
        avoided = self.gateway.avoided_calls[0]
        self.assertEqual(avoided["task"], "sql.format_answer")
        self.assertEqual(avoided["reason"], "deterministic_sql_format")
        self.assertTrue(avoided["prompt"])

    def test_scalar_count_column_formats_with_commas_not_dollars(self):
        result = self._format([{"transaction_count": 8612}])

        self.assertIn("8,612", result["answer"])
        self.assertNotIn("$", result["answer"])

    def test_rate_column_formats_as_percentage(self):
        result = self._format([{"return_rate": 12.5}])

        self.assertIn("12.50%", result["answer"])
        self.assertNotIn("$", result["answer"])

    def test_single_row_multiple_columns_renders_key_values(self):
        result = self._format([{"region": "West", "total_revenue": 1500000.0, "order_count": 4210}])

        self.assertEqual(result["answer_mode"], "deterministic_sql_format")
        self.assertIn("Region: **West**", result["answer"])
        self.assertIn("$1,500,000.00", result["answer"])
        self.assertIn("4,210", result["answer"])

    def test_multi_row_results_render_markdown_table_capped_at_ten(self):
        rows = [{"region": f"Region {i}", "total_revenue": 1000.0 * (i + 1)} for i in range(12)]

        result = self._format(rows)

        self.assertIn("| Region | Total revenue |", result["answer"])
        self.assertIn("$1,000.00", result["answer"])
        self.assertIn("Showing first 10 of 12 rows.", result["answer"])

    def test_empty_results_short_circuit_without_llm_or_avoided_event(self):
        result = self._format([])

        self.assertIn("No data found", result["answer"])
        self.assertEqual(self.gateway.avoided_calls, [])

    def test_llm_mode_env_flag_restores_llm_formatting(self):
        self.gateway.allow_invoke = True
        with patch.dict(os.environ, {"NEXUSIQ_SQL_FORMAT_MODE": "llm"}):
            result = self._format([{"total_revenue": 100.0}])

        self.assertEqual(result["answer"], "LLM ANSWER")
        self.assertEqual(result["answer_mode"], "llm_sql_format")
        self.assertEqual(len(self.gateway.invocations), 1)
        self.assertEqual(self.gateway.invocations[0]["task"], "sql.format_answer")
        self.assertEqual(self.gateway.avoided_calls, [])


class DeterministicExplanationTest(unittest.TestCase):
    def setUp(self):
        self.gateway = GatewayStub()
        self.agent = make_agent(self.gateway)
        os.environ.pop("NEXUSIQ_SQL_EXPLAIN_MODE", None)

    def test_explanation_defaults_to_deterministic_without_llm(self):
        result = self.agent._explain_query(
            sql_query="SELECT COUNT(*) FROM sales_transactions WHERE region = 'West'",
            question="How many transactions in the West?",
        )

        self.assertEqual(result["explanation_mode"], "deterministic_explanation")
        self.assertIn("Counting", result["explanation"])
        self.assertEqual(result["models_tried"], [])
        self.assertEqual(len(self.gateway.avoided_calls), 1)
        self.assertEqual(self.gateway.avoided_calls[0]["task"], "sql.explain_query")

    def test_llm_mode_env_flag_restores_llm_explanation(self):
        self.gateway.allow_invoke = True
        with patch.dict(os.environ, {"NEXUSIQ_SQL_EXPLAIN_MODE": "llm"}):
            result = self.agent._explain_query(
                sql_query="SELECT COUNT(*) FROM sales_transactions",
                question="How many transactions?",
            )

        self.assertEqual(result["explanation_mode"], "llm_explanation")
        self.assertEqual(result["explanation"], "LLM ANSWER")
        self.assertEqual(self.gateway.invocations[0]["task"], "sql.explain_query")


class FakeTrace:
    def __init__(self):
        self.events = []

    def record_event(self, name, payload):
        self.events.append((name, payload))


class AvoidedCallLedgerTest(unittest.TestCase):
    def test_record_avoided_call_writes_ledger_row_and_trace_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.jsonl"
            gateway = LLMGateway(ledger_path=ledger_path)
            trace = FakeTrace()

            env_overrides = {"NEXUSIQ_LLM_LEDGER_ENABLED": "1"}
            with patch.dict(os.environ, env_overrides):
                os.environ.pop("NEXUSIQ_LLM_LEDGER_PATH", None)
                with llm_call_context(trace=trace, trace_id="trace-123"):
                    gateway.record_avoided_call(
                        task="sql.format_answer",
                        reason="deterministic_sql_format",
                        prompt="x" * 400,
                        metadata={"agent": "sql"},
                    )

            rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["status"], "avoided")
            self.assertEqual(row["task"], "sql.format_answer")
            self.assertEqual(row["skip_reason"], "deterministic_sql_format")
            self.assertEqual(row["total_tokens_estimate"], 0)
            self.assertEqual(row["tokens_avoided_estimate"], 100)
            self.assertEqual(row["trace_id"], "trace-123")

            skipped_events = [event for event in trace.events if event[0] == "llm.call_skipped"]
            self.assertEqual(len(skipped_events), 1)
            payload = skipped_events[0][1]
            self.assertEqual(payload["task"], "sql.format_answer")
            self.assertEqual(payload["reason"], "deterministic_sql_format")
            self.assertEqual(payload["estimated_tokens_avoided"], 100)


class FusionAvoidedSummaryTest(unittest.TestCase):
    def test_trace_summary_counts_avoided_calls_and_tokens(self):
        from agents.fusion_agent import FusionAgent

        class TraceStub:
            data = {
                "spans": [
                    {
                        "name": "llm.call",
                        "metadata": {
                            "task": "sql.generate_query",
                            "model": "stub",
                            "status": "success",
                            "total_tokens_estimate": 900,
                            "latency_s": 1.2,
                        },
                    },
                    {
                        "name": "llm.call_skipped",
                        "metadata": {
                            "task": "sql.format_answer",
                            "reason": "deterministic_sql_format",
                            "estimated_tokens_avoided": 123,
                        },
                    },
                    {
                        "name": "llm.call_skipped",
                        "metadata": {
                            "task": "sql.explain_query",
                            "reason": "deterministic_explanation_default",
                            "estimated_tokens_avoided": 200,
                        },
                    },
                ]
            }

        summary = FusionAgent._summarize_llm_usage_from_trace(TraceStub())

        self.assertEqual(summary["avoided_calls"], 2)
        self.assertEqual(summary["avoided_estimated_tokens"], 323)
        self.assertEqual(summary["successful_calls"], 1)


if __name__ == "__main__":
    unittest.main()
