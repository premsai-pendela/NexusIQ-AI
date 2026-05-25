import os
import unittest
from unittest.mock import patch

import numpy as np

from agents.fusion_agent import FusionAgent
from agents.rag_agent import RAGAgent
from agents.sql_agent import SQLAgent
from config.data_contexts import (
    LIVE_CONTEXT,
    PILOT_CHROMA_DIRECTORY,
    PILOT_COLLECTION_NAME,
    PILOT_COMBINED_VIEW,
    PILOT_CONTEXT,
    get_data_context,
)
from utils.validators import validate_question


class PilotDemoModeTests(unittest.TestCase):
    def test_live_context_remains_default_production_boundary(self):
        context = get_data_context()

        self.assertEqual(context, LIVE_CONTEXT)
        self.assertEqual(context.sql_table, "sales_transactions")
        self.assertEqual(context.chroma_collection, "nexusiq_docs")
        self.assertTrue(context.allow_web)

    def test_pilot_context_uses_only_validated_staged_resources(self):
        self.assertEqual(PILOT_CONTEXT.sql_table, PILOT_COMBINED_VIEW)
        self.assertEqual(PILOT_CONTEXT.chroma_collection, PILOT_COLLECTION_NAME)
        self.assertIn("chroma_staging", str(PILOT_CHROMA_DIRECTORY))
        self.assertNotIn("data/chroma_db", str(PILOT_CHROMA_DIRECTORY))
        self.assertTrue(PILOT_CONTEXT.is_pilot)
        self.assertFalse(PILOT_CONTEXT.allow_web)

    def test_pilot_year_validation_accepts_supported_periods_without_changing_live_scope(self):
        question = "Validate FY 2025 revenue against PDF evidence."

        self.assertFalse(validate_question(question, auto_fix=True)["valid"])
        self.assertTrue(
            validate_question(
                question,
                auto_fix=True,
                available_years=PILOT_CONTEXT.available_years,
            )["valid"]
        )
        self.assertFalse(
            validate_question(
                "Validate FY 2030 revenue.",
                auto_fix=True,
                available_years=PILOT_CONTEXT.available_years,
            )["valid"]
        )

    def test_pilot_sql_rejects_live_or_unscoped_relations(self):
        agent = SQLAgent.__new__(SQLAgent)
        agent.data_context = PILOT_CONTEXT

        safe_query = f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW}"
        safe_extract_query = (
            f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW} pilot "
            "WHERE EXTRACT(YEAR FROM pilot.transaction_date) = 2025"
        )
        missing_scope = "SELECT COUNT(*) FROM sales_transactions"
        mixed_query = (
            f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW} pilot "
            "JOIN public.sales_transactions live ON live.id::text = pilot.transaction_id"
        )
        unrelated_join = (
            f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW} pilot "
            "JOIN customers customer ON customer.customer_id = pilot.customer_id"
        )
        implicit_join = f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW} pilot, customers customer"
        safe_cte = (
            f"WITH totals AS (SELECT COUNT(*) AS total FROM {PILOT_COMBINED_VIEW}) "
            "SELECT total FROM totals"
        )

        self.assertTrue(agent._validate_query(safe_query)[0])
        self.assertTrue(agent._validate_query(safe_extract_query)[0])
        self.assertTrue(agent._validate_query(safe_cte)[0])
        self.assertFalse(agent._validate_query(missing_scope)[0])
        self.assertFalse(agent._validate_query(mixed_query)[0])
        self.assertFalse(agent._validate_query(unrelated_join)[0])
        self.assertFalse(agent._validate_query(implicit_join)[0])

    def test_pilot_row_display_request_uses_detail_query_without_aggregate(self):
        agent = SQLAgent.__new__(SQLAgent)
        agent.data_context = PILOT_CONTEXT

        result = agent.generate_query("display the 2025 transactions upto 10 rows")
        query = result["query"].upper()

        self.assertTrue(result["success"])
        self.assertEqual(result["model_used"], "Deterministic pilot row retrieval")
        self.assertIn("TRANSACTION_ID", query)
        self.assertIn("LIMIT 10", query)
        self.assertNotIn("COUNT(", query)
        self.assertTrue(agent._validate_query(result["query"])[0])

    def test_sql_prompt_for_row_requests_forbids_aggregate_columns(self):
        agent = SQLAgent.__new__(SQLAgent)
        agent.data_context = PILOT_CONTEXT
        agent.schema_context = "pilot schema"

        prompt = agent._create_sql_prompt("show 2025 transactions up to 10 rows")

        self.assertIn("return detail columns with LIMIT only", prompt)
        self.assertIn("never add aggregate columns", prompt)

    def test_pilot_routing_only_cross_validates_supported_document_periods(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent.data_context = PILOT_CONTEXT
        agent._last_routing_model = None
        agent._no_data_reason = None

        self.assertEqual(
            agent._pilot_routing_override("Validate FY 2025 revenue against the PDF evidence."),
            "sql_rag",
        )
        self.assertEqual(
            agent._pilot_routing_override("What is the total revenue in the combined pilot view?"),
            "sql_only",
        )
        self.assertEqual(
            agent._pilot_routing_override("Show competitor web prices."),
            "no_data",
        )

    def test_live_context_does_not_apply_pilot_routing_override(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent.data_context = LIVE_CONTEXT

        self.assertIsNone(agent._pilot_routing_override("Show competitor web prices."))

    def test_forced_web_route_is_refused_in_pilot_mode(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent.data_context = PILOT_CONTEXT
        agent._query_cache = {}
        agent._cache_ttl = 3600
        agent._cache_max = 50
        agent._history = []
        agent._history_max = 5
        agent._last_routing_model = None
        agent._last_routing_fallback = False
        agent._no_data_reason = None

        with patch.dict(os.environ, {"NEXUSIQ_TRACE_ENABLED": "0"}):
            result = agent.query("Show competitor prices.", force_source="web_only")

        self.assertEqual(result["source_type"], "no_data")
        self.assertIn("disabled in Enterprise Pilot mode", result["answer"])

    def test_fusion_preserves_sql_failure_detail_for_pilot_debugging(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent.sql_agent = type(
            "FailedSqlAgent",
            (),
            {"ask": lambda _self, _question: {"success": False, "error": "approved query rejected"}},
        )()

        result = agent._run_sql_query("Validate FY 2025 revenue.")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approved query rejected")

    def test_pilot_hybrid_search_does_not_discard_results_when_bm25_scores_are_negative(self):
        class FakeBm25:
            def get_scores(self, _query):
                return np.array([-3.9, -2.3])

        class FakeEmbeddingModel:
            def encode(self, *_args, **_kwargs):
                return np.array([1.0])

        class FakeCollection:
            def query(self, **_kwargs):
                return {
                    "ids": [["fy2021", "fy2025"]],
                    "distances": [[0.44, 0.43]],
                }

        agent = RAGAgent.__new__(RAGAgent)
        agent.bm25_index = FakeBm25()
        agent.bm25_documents = ["FY 2021 report", "FY 2025 revenue report"]
        agent.bm25_ids = ["fy2021", "fy2025"]
        agent.bm25_metadatas = [{"filename": "FY_2021.pdf"}, {"filename": "FY_2025.pdf"}]
        agent.embedding_model = FakeEmbeddingModel()
        agent.collection = FakeCollection()
        agent._ensure_bm25_fresh = lambda: None

        results = agent.hybrid_search("Validate FY 2025 revenue.", n_results=2)

        self.assertTrue(results)
        self.assertEqual(results[0]["filename"], "FY_2025.pdf")


if __name__ == "__main__":
    unittest.main()
