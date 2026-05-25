import os
import unittest
from unittest.mock import patch

from agents.fusion_agent import FusionAgent
from agents.sql_agent import SQLAgent
from config.data_contexts import (
    LIVE_CONTEXT,
    PILOT_CHROMA_DIRECTORY,
    PILOT_COLLECTION_NAME,
    PILOT_COMBINED_VIEW,
    PILOT_CONTEXT,
    get_data_context,
)


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

    def test_pilot_sql_rejects_live_or_unscoped_relations(self):
        agent = SQLAgent.__new__(SQLAgent)
        agent.data_context = PILOT_CONTEXT

        safe_query = f"SELECT COUNT(*) FROM {PILOT_COMBINED_VIEW}"
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
        self.assertTrue(agent._validate_query(safe_cte)[0])
        self.assertFalse(agent._validate_query(missing_scope)[0])
        self.assertFalse(agent._validate_query(mixed_query)[0])
        self.assertFalse(agent._validate_query(unrelated_join)[0])
        self.assertFalse(agent._validate_query(implicit_join)[0])

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


if __name__ == "__main__":
    unittest.main()
