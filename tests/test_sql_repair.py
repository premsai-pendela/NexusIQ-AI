"""Bounded SQL repair loop contracts.

Generate -> validate -> execute -> (on semantic DB failure) repair ONCE ->
re-validate with the same AST safety gate -> execute -> continue or fail
honestly. Proofs:

1. Execution failure triggers exactly one repair attempt.
2. Repaired SQL passes the safety gate before execution.
3. Unsafe repaired SQL is rejected and never executed.
4. Successful repair returns SQL success with repair metadata.
5. Failed repair stays an honest failure with the original error.
6. Business context is available in the repair prompt for metric questions.
7. Happy path never calls repair.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from agents.sql_agent import SQLAgent

GROUPING_ERROR = (
    '(psycopg2.errors.GroupingError) column "s.total" must appear in the '
    "GROUP BY clause or be used in an aggregate function"
)
CONNECTION_ERROR = "could not connect to server: Connection refused"


class RepairGateway:
    """Stub gateway returning a fixed repaired SQL once."""

    def __init__(self, repaired_sql="SELECT SUM(total_amount) AS net_revenue FROM sales_transactions"):
        self.repaired_sql = repaired_sql
        self.calls = []

    def invoke_with_fallback(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "response": self.repaired_sql,
            "model_used": "stub-repair-model",
            "models_tried": [{"model": "stub", "status": "✅ SUCCESS", "error": None,
                              "time": 0.1, "task": kwargs.get("task")}],
        }


def make_agent(gateway, executions):
    """Agent with stubbed generation/execution. `executions` = sequence of
    execute_query results consumed in order."""
    agent = SQLAgent.__new__(SQLAgent)
    agent.llm_gateway = gateway
    agent.tracker = MagicMock()
    agent.schema_context = "SCHEMA: sales_transactions(total_amount, ...)"
    agent.data_context = MagicMock(sql_table="sales_transactions", available_years=[2024])
    agent._last_business_context = {"block": "", "ids": [], "chars": 0}

    agent.generate_query = lambda _q: {
        "success": True,
        "query": "SELECT bad_sql",
        "complexity": "simple",
        "model_used": "gen-model",
        "models_tried": [],
        "business_context": None,
    }
    execution_iter = iter(executions)
    agent.execute_query = MagicMock(side_effect=lambda _sql: next(execution_iter))
    agent._format_answer = lambda **_kw: {"success": True, "answer": "ok", "models_tried": []}
    agent._explain_query = lambda **_kw: {"success": True, "explanation": "e", "models_tried": []}
    return agent


def ask(agent, question="What was net revenue in Q4 2024?"):
    with patch("agents.sql_agent.validate_question", return_value={"valid": True}):
        return SQLAgent.ask.__wrapped__(agent, question)


class SqlRepairLoopTest(unittest.TestCase):
    def test_execution_failure_triggers_single_successful_repair(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": False, "error": GROUPING_ERROR, "results": None},
            {"success": True, "results": [{"net_revenue": 100.0}], "row_count": 1, "columns": ["net_revenue"]},
        ])

        result = ask(agent)

        self.assertTrue(result["success"])
        repair_calls = [c for c in gateway.calls if c.get("task") == "sql.repair_query"]
        self.assertEqual(len(repair_calls), 1)
        self.assertTrue(result["sql_repair"]["attempted"])
        self.assertTrue(result["sql_repair"]["succeeded"])
        self.assertIn("GroupingError", result["sql_repair"]["original_error"])
        self.assertEqual(result["query"], gateway.repaired_sql)
        self.assertEqual(result["sql_repair"]["repair_model"], "stub-repair-model")

    def test_repair_prompt_contains_error_sql_schema(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": False, "error": GROUPING_ERROR, "results": None},
            {"success": True, "results": [{"x": 1}], "row_count": 1, "columns": ["x"]},
        ])

        ask(agent)

        prompt = gateway.calls[0]["prompt"]
        self.assertIn("GroupingError", prompt)
        self.assertIn("SELECT bad_sql", prompt)
        self.assertIn("SCHEMA: sales_transactions", prompt)
        self.assertEqual(gateway.calls[0]["metadata"]["repair"], True)

    def test_business_context_included_in_repair_for_metric_question(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": False, "error": GROUPING_ERROR, "results": None},
            {"success": True, "results": [{"x": 1}], "row_count": 1, "columns": ["x"]},
        ])
        agent._last_business_context = {
            "block": "COMPANY BUSINESS DEFINITIONS:\n- net revenue: subtract refunded returns",
            "ids": ["net_revenue"],
            "chars": 60,
        }

        ask(agent)

        prompt = gateway.calls[0]["prompt"]
        self.assertIn("COMPANY BUSINESS DEFINITIONS", prompt)
        self.assertIn("subtract refunded returns", prompt)
        self.assertEqual(gateway.calls[0]["metadata"]["business_context_ids"], ["net_revenue"])

    def test_unsafe_repaired_sql_rejected_before_execution(self):
        gateway = RepairGateway(repaired_sql="DROP TABLE sales_transactions")
        agent = make_agent(gateway, [
            {"success": False, "error": GROUPING_ERROR, "results": None},
        ])

        result = ask(agent)

        self.assertFalse(result["success"])
        self.assertEqual(result["sql_repair"]["reason"], "repaired_sql_rejected_by_safety_gate")
        self.assertFalse(result["sql_repair"]["succeeded"])
        # execute_query called exactly once (original attempt); repaired DROP never executed
        self.assertEqual(agent.execute_query.call_count, 1)
        self.assertIn("GroupingError", result["error"])

    def test_failed_repair_keeps_honest_original_error(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": False, "error": GROUPING_ERROR, "results": None},
            {"success": False, "error": "still broken", "results": None},
        ])

        result = ask(agent)

        self.assertFalse(result["success"])
        self.assertIn("GroupingError", result["error"])
        self.assertTrue(result["sql_repair"]["attempted"])
        self.assertFalse(result["sql_repair"]["succeeded"])
        self.assertEqual(result["sql_repair"]["reason"], "repaired_sql_execution_failed")
        self.assertIn("still broken", result["sql_repair"]["repair_error"])
        # exactly one repair LLM call — no loop
        repair_calls = [c for c in gateway.calls if c.get("task") == "sql.repair_query"]
        self.assertEqual(len(repair_calls), 1)

    def test_connection_error_not_repaired(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": False, "error": CONNECTION_ERROR, "results": None},
        ])

        result = ask(agent)

        self.assertFalse(result["success"])
        self.assertEqual(gateway.calls, [])
        self.assertFalse(result["sql_repair"]["attempted"])
        self.assertEqual(result["sql_repair"]["reason"], "error_not_repairable_by_sql_rewrite")

    def test_happy_path_never_calls_repair(self):
        gateway = RepairGateway()
        agent = make_agent(gateway, [
            {"success": True, "results": [{"x": 1}], "row_count": 1, "columns": ["x"]},
        ])

        result = ask(agent)

        self.assertTrue(result["success"])
        self.assertEqual(gateway.calls, [])
        self.assertIsNone(result["sql_repair"])


if __name__ == "__main__":
    unittest.main()
