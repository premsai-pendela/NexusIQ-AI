"""Tests for the business context layer.

Contracts:
- Retrieval is deterministic and conservative: business terms hit, plain
  questions miss.
- Prompt injection happens only when context is retrieved and the flag is on;
  otherwise the SQL prompt is byte-identical to the pre-layer prompt.
- Retrieved context IDs flow into LLM gateway metadata and agent results.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from agents.sql_agent import SQLAgent
from context.business_context import (
    BusinessContextEntry,
    BusinessContextRetriever,
    build_context_block,
    business_context_enabled,
    load_glossary,
    reset_default_retriever,
)


def make_sql_agent(gateway=None):
    agent = SQLAgent.__new__(SQLAgent)
    agent.llm_gateway = gateway or MagicMock()
    agent.tracker = MagicMock()
    agent.schema_context = "SCHEMA CONTEXT"
    agent.data_context = MagicMock(sql_table="sales_transactions")
    return agent


class GlossaryLoadTest(unittest.TestCase):
    def test_seed_glossary_loads_all_entries(self):
        entries = load_glossary()
        ids = {entry.id for entry in entries}
        self.assertGreaterEqual(len(entries), 12)
        self.assertIn("net_revenue", ids)
        self.assertIn("active_customer", ids)
        self.assertIn("return_rate", ids)

    def test_malformed_entry_skipped_not_fatal(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "glossary.json"
            path.write_text(json.dumps({
                "entries": [
                    {"id": "ok", "term": "net revenue", "definition": "d"},
                    {"term": "missing id and definition"},
                ]
            }))
            with patch.dict(os.environ, {"NEXUSIQ_BUSINESS_GLOSSARY_PATH": str(path)}):
                entries = load_glossary()
            self.assertEqual([entry.id for entry in entries], ["ok"])


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.retriever = BusinessContextRetriever()

    def _ids(self, question):
        return [entry.id for _score, entry in self.retriever.retrieve(question)]

    def test_exact_term_hits(self):
        self.assertIn("net_revenue", self._ids("What was net revenue in Q4 2024?"))

    def test_alias_hits(self):
        self.assertIn("average_order_value", self._ids("What is our AOV this year?"))

    def test_keyword_overlap_hits_paraphrase(self):
        self.assertIn("active_customer", self._ids("How many active customers do we have?"))

    def test_plain_revenue_question_misses(self):
        ids = self._ids("What was total revenue in October 2024?")
        self.assertNotIn("net_revenue", ids)
        self.assertEqual(ids, [])

    def test_plain_ranking_question_misses(self):
        self.assertEqual(self._ids("Top 5 products by revenue in 2024?"), [])

    def test_max_three_entries(self):
        hits = self.retriever.retrieve(
            "net revenue, return rate, active customers, and churned customers by region"
        )
        self.assertLessEqual(len(hits), 3)

    def test_phrase_match_outranks_keyword_overlap(self):
        entries = [
            BusinessContextEntry(id="phrase", term="net revenue", definition="d"),
            BusinessContextEntry(id="overlap", term="revenue net thing", definition="d"),
        ]
        retriever = BusinessContextRetriever(entries)
        hits = retriever.retrieve("what was net revenue last year")
        self.assertEqual(hits[0][1].id, "phrase")


class ContextBlockTest(unittest.TestCase):
    def test_block_contains_definition_and_ids(self):
        result = build_context_block("What was net revenue in Q4 2024?")
        self.assertIn("COMPANY BUSINESS DEFINITIONS", result["block"])
        self.assertIn("refund_amount", result["block"])
        self.assertIn("net_revenue", result["ids"])
        self.assertGreater(result["chars"], 0)

    def test_empty_for_plain_question(self):
        result = build_context_block("What was total revenue in October 2024?")
        self.assertEqual(result, {"block": "", "ids": [], "chars": 0})

    def test_char_budget_enforced(self):
        entries = [
            BusinessContextEntry(id=f"entry_{i}", term="net revenue", definition="x" * 500)
            for i in range(3)
        ]
        retriever = BusinessContextRetriever(entries)
        result = build_context_block("net revenue?", retriever=retriever)
        self.assertLessEqual(result["chars"], 1000)
        self.assertLess(len(result["ids"]), 3)

    def test_retriever_failure_returns_empty_not_raise(self):
        broken = MagicMock()
        broken.retrieve.side_effect = RuntimeError("boom")
        result = build_context_block("net revenue?", retriever=broken)
        self.assertEqual(result["ids"], [])


class PromptInjectionTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("NEXUSIQ_BUSINESS_CONTEXT", None)
        reset_default_retriever()
        self.agent = make_sql_agent()

    def test_business_question_injects_definitions(self):
        prompt = self.agent._create_sql_prompt("What was net revenue in Q4 2024?")
        self.assertIn("COMPANY BUSINESS DEFINITIONS", prompt)
        self.assertIn("net revenue", prompt)
        self.assertIn("net_revenue", self.agent._last_business_context["ids"])

    def test_plain_question_prompt_unchanged(self):
        prompt = self.agent._create_sql_prompt("What was total revenue in October 2024?")
        self.assertNotIn("COMPANY BUSINESS DEFINITIONS", prompt)
        self.assertIn("SCHEMA CONTEXT\n\nUSER QUESTION:", prompt)

    def test_flag_off_disables_injection(self):
        with patch.dict(os.environ, {"NEXUSIQ_BUSINESS_CONTEXT": "0"}):
            self.assertFalse(business_context_enabled())
            prompt = self.agent._create_sql_prompt("What was net revenue in Q4 2024?")
        self.assertNotIn("COMPANY BUSINESS DEFINITIONS", prompt)
        self.assertEqual(self.agent._last_business_context["ids"], [])

    def test_flag_off_and_on_prompts_differ_only_by_block(self):
        with patch.dict(os.environ, {"NEXUSIQ_BUSINESS_CONTEXT": "0"}):
            prompt_off = self.agent._create_sql_prompt("What was net revenue in Q4 2024?")
        prompt_on = self.agent._create_sql_prompt("What was net revenue in Q4 2024?")
        block = self.agent._last_business_context["block"]
        self.assertEqual(prompt_on.replace(f"\n{block}\n", "", 1), prompt_off)


class MetadataFlowTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("NEXUSIQ_BUSINESS_CONTEXT", None)
        reset_default_retriever()

    def _run_generate(self, question):
        gateway = MagicMock()
        gateway.invoke_with_fallback.return_value = {
            "success": True,
            "response": "SELECT 1",
            "model_used": "stub",
            "models_tried": [],
        }
        agent = make_sql_agent(gateway)
        agent._detect_query_complexity = lambda _q: "simple"
        agent._validate_query = lambda _q: (True, "")
        result = agent.generate_query(question)
        return result, gateway.invoke_with_fallback.call_args.kwargs

    def test_context_ids_reach_gateway_metadata(self):
        result, kwargs = self._run_generate("What was net revenue in Q4 2024?")
        self.assertIn("net_revenue", kwargs["metadata"]["business_context_ids"])
        self.assertGreater(kwargs["metadata"]["business_context_chars"], 0)
        self.assertIn("net_revenue", result["business_context"]["ids"])

    def test_plain_question_has_no_context_metadata(self):
        result, kwargs = self._run_generate("What was total revenue in October 2024?")
        self.assertNotIn("business_context_ids", kwargs["metadata"])
        self.assertIsNone(result["business_context"])


class GlossaryRecipeContractTest(unittest.TestCase):
    """Guard SQL-shape guidance that prevents known PostgreSQL failures.

    net_revenue previously collided with SQL prompt rule 8 ("include COUNT(*)
    AS transactions_analyzed"): models appended a bare COUNT(*) to the final
    SELECT of the CTE subtraction and hit a GroupingError. The definition now
    carries the count inside the sales CTE and says so explicitly. If someone
    rewords the glossary and drops these guards, this test fails first.
    """

    def test_net_revenue_recipe_keeps_grouping_safe_template(self):
        entries = {entry.id: entry for entry in load_glossary()}
        definition = entries["net_revenue"].definition
        self.assertIn("transactions_analyzed", definition)
        self.assertIn("COALESCE", definition)
        self.assertIn("never add a bare COUNT(*)", definition)

    def test_case_resolution_recipe_keeps_interval_guard(self):
        entries = {entry.id: entry for entry in load_glossary()}
        definition = entries["case_resolution_time"].definition
        self.assertIn("EXTRACT(EPOCH", definition)
        self.assertIn("Never cast an interval directly to numeric", definition)


class DegradedMetricGuardTest(unittest.TestCase):
    """SQL failure on a company-defined metric must not yield a misleading
    document-only answer presented as complete."""

    FAILED_SQL = {"success": False, "error": "GroupingError: ...", "answer": ""}
    GROSS_RAG = {
        "success": True,
        "answer": "Q4 2024 revenue was **$58,900,000** per the financial report.",
    }

    def _fusion(self):
        from agents.fusion_agent import FusionAgent

        return FusionAgent.__new__(FusionAgent)

    def test_net_revenue_sql_failure_warns_instead_of_gross_answer(self):
        agent = self._fusion()
        answer = agent._format_degraded_multi_source_answer(
            sql_result=self.FAILED_SQL,
            rag_result=self.GROSS_RAG,
            web_result=None,
            question="What was net revenue in Q4 2024?",
        )

        self.assertIsNotNone(answer)
        self.assertIn("cannot be fully answered", answer)
        self.assertIn("net_revenue", answer)
        self.assertIn("needs SQL verification", answer)
        self.assertIn("Unverified supporting context", answer)
        self.assertTrue(answer.startswith("⚠️"))
        self.assertEqual(agent._last_degraded_metric_ids, ["net_revenue"])

    def test_non_metric_question_keeps_standard_degraded_note(self):
        agent = self._fusion()
        answer = agent._format_degraded_multi_source_answer(
            sql_result=self.FAILED_SQL,
            rag_result=self.GROSS_RAG,
            web_result=None,
            question="What was total revenue in October 2024? Validate against reports.",
        )

        self.assertIsNotNone(answer)
        self.assertNotIn("needs SQL verification", answer)
        self.assertIn("Availability note", answer)
        self.assertEqual(agent._last_degraded_metric_ids, [])

    def test_sql_survivor_on_metric_question_gets_no_warning(self):
        agent = self._fusion()
        answer = agent._format_degraded_multi_source_answer(
            sql_result={"success": True, "answer": "Net revenue: **$58,253,039.89**"},
            rag_result={"success": False, "error": "no chunks", "answer": ""},
            web_result=None,
            question="What was net revenue in Q4 2024?",
        )

        self.assertIsNotNone(answer)
        self.assertNotIn("needs SQL verification", answer)
        self.assertIn("SQL Database", answer)

    def test_single_source_attempt_not_degraded_formatted(self):
        agent = self._fusion()
        answer = agent._format_degraded_multi_source_answer(
            sql_result=None,
            rag_result=self.GROSS_RAG,
            web_result=None,
            question="What was net revenue in Q4 2024?",
        )
        self.assertIsNone(answer)

    def test_generate_fused_answer_records_metric_reason(self):
        agent = self._fusion()
        agent._format_validated_sql_rag_answer = lambda **_kwargs: None
        answer = agent._generate_fused_answer(
            question="What was net revenue in Q4 2024?",
            sql_result=self.FAILED_SQL,
            rag_result=self.GROSS_RAG,
            web_result=None,
            validation=None,
        )

        self.assertIn("needs SQL verification", answer)
        self.assertEqual(
            agent._last_answer_generation["reason"], "metric_requires_sql_verification"
        )
        self.assertEqual(
            agent._last_answer_generation["business_context_expected"], ["net_revenue"]
        )


class EvalScoringTest(unittest.TestCase):
    """score_case must gate the final pass on context correctness."""

    AMBIGUOUS = {
        "id": "net_revenue_q4",
        "expected_fragments": ["refund_amount"],
        "expect_context_ids": ["net_revenue"],
        "control": False,
    }
    CONTROL = {
        "id": "control_total_revenue",
        "expected_fragments": ["total_amount"],
        "expect_context_ids": [],
        "control": True,
    }

    def test_control_fails_if_context_retrieved(self):
        from evals.context_eval import score_case

        for mode in ("before", "after"):
            result = score_case(
                self.CONTROL, "SELECT SUM(total_amount)", True, ["net_revenue"], mode=mode
            )
            self.assertFalse(result["context_pass"])
            self.assertFalse(result["pass"])

    def test_ambiguous_after_fails_if_expected_context_missing(self):
        from evals.context_eval import score_case

        result = score_case(
            self.AMBIGUOUS, "SELECT SUM(refund_amount)", True, [], mode="after"
        )
        self.assertTrue(result["fragments_pass"])
        self.assertTrue(result["executed_ok"])
        self.assertFalse(result["context_pass"])
        self.assertFalse(result["pass"])

    def test_pass_requires_fragments_execution_and_context(self):
        from evals.context_eval import score_case

        good = score_case(
            self.AMBIGUOUS, "SELECT SUM(refund_amount)", True, ["net_revenue"], mode="after"
        )
        self.assertTrue(good["pass"])

        bad_fragments = score_case(
            self.AMBIGUOUS, "SELECT SUM(total_amount)", True, ["net_revenue"], mode="after"
        )
        self.assertFalse(bad_fragments["pass"])

        bad_execution = score_case(
            self.AMBIGUOUS, "SELECT SUM(refund_amount)", False, ["net_revenue"], mode="after"
        )
        self.assertFalse(bad_execution["pass"])

    def test_before_mode_ambiguous_context_check_is_vacuous(self):
        from evals.context_eval import score_case

        result = score_case(
            self.AMBIGUOUS, "SELECT SUM(refund_amount)", True, [], mode="before"
        )
        self.assertTrue(result["context_pass"])
        self.assertTrue(result["pass"])


if __name__ == "__main__":
    unittest.main()
