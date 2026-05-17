import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.fusion_agent import FusionAgent
from evals.offline_eval import (
    OFFLINE_EVAL_CASES,
    OfflineEvaluationHarness,
    validate_sql_result,
    validate_web_result,
)
from evals.golden_eval import (
    append_trend,
    build_case_result,
    extract_numbers,
    load_cases,
    number_matches,
    replay_golden_eval,
    resolve_replay_path,
    response_has_transient_failure,
    score_case_rules,
    summarize_trace_for_report,
)
from evals.refresh_golden_truth import update_cases
from observability.inspect_traces import format_trace_summary, get_trace_diagnostics
from observability.tracer import get_tracer, summarize_agent_result
from run_tests import parse_queries, routing_matches
from utils.validators import validate_question


class FusionValidationTests(unittest.TestCase):
    def setUp(self):
        self.agent = FusionAgent.__new__(FusionAgent)

    def test_q4_electronics_revenue_validates_against_rounded_pdf_value(self):
        sql_result = {
            "success": True,
            "answer": "Q4 Electronics revenue was $33,885,324.16 across 7,721 transactions.",
            "results": [
                {
                    "q4_electronics_revenue": 33_885_324.16,
                    "transactions_analyzed": 7_721,
                }
            ],
        }
        rag_result = {
            "success": True,
            "answer": "The Q4 financial report lists Electronics revenue at $33.9M.",
        }

        validation = self.agent._cross_validate(sql_result, rag_result)

        self.assertTrue(validation["validated"])
        self.assertEqual(validation["confidence"], "HIGH")
        self.assertEqual(validation["sql_numbers_found"], 1)
        self.assertEqual(validation["matches"][0]["sql_label"], "q4_electronics_revenue")

    def test_transaction_count_metadata_does_not_validate_pdf_revenue(self):
        sql_result = {
            "success": True,
            "answer": "The query analyzed 90,500 transactions.",
            "results": [{"transactions_analyzed": 90_500}],
        }
        rag_result = {
            "success": True,
            "answer": "The Q4 financial report lists revenue at $45.2M.",
        }

        validation = self.agent._cross_validate(sql_result, rag_result)

        self.assertFalse(validation["validated"])
        self.assertEqual(validation["confidence"], "MEDIUM")
        self.assertEqual(validation["matches"], [])
        self.assertEqual(validation["discrepancies"], [])
        self.assertEqual(validation["sql_numbers_found"], 0)

    def test_material_sql_rag_mismatch_is_low_confidence(self):
        sql_result = {
            "success": True,
            "answer": "Actual Q4 transaction revenue was $45,195,318.45.",
            "results": [{"q4_revenue": 45_195_318.45}],
        }
        rag_result = {
            "success": True,
            "answer": "The Q4 financial report lists reported revenue of $38.7M.",
        }

        validation = self.agent._cross_validate(sql_result, rag_result)

        self.assertFalse(validation["validated"])
        self.assertEqual(validation["confidence"], "LOW")
        self.assertGreaterEqual(len(validation["discrepancies"]), 1)


class RoutingAndInputTests(unittest.TestCase):
    def test_routing_matcher_accepts_equivalent_fusion_labels(self):
        self.assertTrue(routing_matches("rag_sql", "sql_rag"))
        self.assertTrue(routing_matches("sql_rag_web", "all"))
        self.assertFalse(routing_matches("rag_only", "sql_only"))

    def test_query_parser_keeps_expected_regression_suite_size(self):
        queries = parse_queries(Path("test_queries.txt"))

        self.assertEqual(len(queries), 105)
        self.assertEqual(queries[0]["id"], 1)
        self.assertEqual(queries[-1]["id"], 105)
        self.assertEqual(queries[0]["expected_routing"], "sql_rag")

    def test_category_typo_guard_does_not_turn_reports_into_sports(self):
        result = validate_question("Validate Q4 revenue against PDF reports", auto_fix=True)

        self.assertTrue(result["valid"])
        self.assertFalse(result["auto_corrected"])


class OfflineEvalHarnessTests(unittest.TestCase):
    def test_offline_eval_fixture_suite_passes(self):
        report = OfflineEvaluationHarness().run()

        self.assertEqual(report["meta"]["case_count"], len(OFFLINE_EVAL_CASES))
        self.assertEqual(report["meta"]["failed"], 0)

    def test_source_contract_validators_catch_missing_evidence(self):
        self.assertIn("SQL result is missing answer text", validate_sql_result({"success": True}))

        web_issues = validate_web_result(
            {
                "success": True,
                "answer": "Prices are available.",
                "category": "electronics",
                "raw_data": {"competitors": [{"name": "Newegg", "products": []}]},
            }
        )
        self.assertIn("Web result is missing competitor product evidence", web_issues)


class GoldenEvalTests(unittest.TestCase):
    def test_golden_cases_load_and_have_core_coverage(self):
        cases = load_cases()
        ids = {case["id"] for case in cases}

        self.assertGreaterEqual(len(cases), 10)
        self.assertIn("q4_electronics_revenue", ids)
        self.assertIn("refund_policy", ids)
        self.assertIn("electronics_competitor_prices", ids)
        self.assertIn("out_of_range_revenue", ids)

    def test_number_extraction_handles_currency_scales(self):
        numbers = extract_numbers("Revenue was $15.4M and transactions were 8,525.")

        self.assertIn(15_400_000, numbers)
        self.assertIn(8_525, numbers)

    def test_number_match_uses_tolerance(self):
        matched, diff = number_matches([15_400_000], {"value": 15_399_999.75, "tolerance_pct": 0.1})

        self.assertTrue(matched)
        self.assertLess(diff, 0.1)

    def test_rule_scorer_scores_expected_route_number_and_confidence(self):
        case = {
            "id": "sample",
            "question": "What was Q4 2024 Electronics revenue?",
            "expected_route": "sql_rag",
            "expected_confidence": "HIGH",
            "expected_numbers": [{"value": 15_399_999.75, "tolerance_pct": 1}],
            "required_terms": ["Electronics"],
            "required_sources": ["Q4"],
            "requires_sql": True,
            "requires_rag": True,
        }
        response = {
            "answer": "Q4 Electronics revenue was $15.4M.",
            "source_type": "sql_rag",
            "validation": {"confidence": "HIGH"},
            "sql_result": {"success": True, "results": [{"revenue": 15_399_999.75}]},
            "rag_result": {
                "success": True,
                "sources": [{"filename": "01_Q4_2024_Financial_Report.pdf"}],
            },
            "web_result": None,
        }

        scored = score_case_rules(case, response)

        self.assertEqual(scored["score"], scored["max_score"])
        self.assertTrue(scored["checks"]["route"]["passed"])
        self.assertTrue(scored["checks"]["numbers"]["passed"])

    def test_answer_only_mode_skips_route_scoring(self):
        case = {"id": "sample", "question": "Q", "expected_route": "sql_rag"}
        response = {
            "answer": "Answer",
            "source_type": "sql_rag",
            "_eval_answer_only": True,
        }

        scored = score_case_rules(case, response)

        self.assertEqual(scored["checks"]["route"]["max_points"], 0)
        self.assertIn("skipped", scored["checks"]["route"]["detail"])

    def test_transient_failure_detection_catches_provider_errors(self):
        response = {"answer": "Unable to generate comparison. All models failed."}

        self.assertTrue(response_has_transient_failure(response))
        self.assertTrue(response_has_transient_failure(None, "429 RESOURCE_EXHAUSTED"))

    def test_execution_failure_result_includes_actionable_check(self):
        case = {"id": "sample", "question": "Q"}

        result = build_case_result(case, None, 0.1, error="RESOURCE_EXHAUSTED")

        self.assertEqual(result["status"], "fail")
        self.assertIn("execution", result["checks"])
        self.assertIn("RESOURCE_EXHAUSTED", result["checks"]["execution"]["detail"])

    def test_refresh_golden_truth_updates_expected_number_by_label(self):
        cases = [
            {
                "id": "annual_total_revenue",
                "expected_numbers": [{"label": "total 2024 revenue", "value": 1.0}],
            }
        ]

        updated = update_cases(cases, {"annual_total_revenue": 175_164_502.35})

        self.assertEqual(updated[0]["expected_numbers"][0]["value"], 175_164_502.35)

    def test_replay_rescores_stored_response_without_agent_call(self):
        case = {
            "id": "sample",
            "question": "What was total 2024 revenue?",
            "expected_route": "sql_rag",
            "expected_numbers": [{"label": "revenue", "value": 175_164_502.35, "tolerance_pct": 1}],
        }
        prior_report = {
            "meta": {},
            "results": [
                {
                    "id": "sample",
                    "elapsed_s": 12.3,
                    "response": {
                        "answer": "Total 2024 revenue was $175,164,502.35.",
                        "source_type": "sql_rag",
                    },
                }
            ],
        }

        with TemporaryDirectory() as tmp:
            replay_path = Path(tmp) / "prior.json"
            replay_path.write_text(json.dumps(prior_report))

            report = replay_golden_eval([case], replay_path)

        self.assertEqual(report["meta"]["passed"], 1)
        self.assertEqual(report["results"][0]["score"], 100.0)
        self.assertEqual(report["results"][0]["replayed_from"], str(replay_path))

    def test_latest_replay_path_skips_reports_without_cached_responses(self):
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            old_path = out_dir / "golden-eval-2026-05-17_00-00-00.json"
            new_path = out_dir / "golden-eval-2026-05-17_00-00-01.json"
            old_path.write_text(json.dumps({"results": [{"id": "old"}]}))
            new_path.write_text(json.dumps({"results": [{"id": "new", "response": {"answer": "cached"}}]}))

            resolved = resolve_replay_path("latest", out_dir)

        self.assertEqual(resolved, new_path)

    def test_trend_csv_appends_run_summary(self):
        report = {
            "meta": {
                "date": "2026-05-17T00:00:00",
                "case_count": 3,
                "passed": 3,
                "warnings": 0,
                "failed": 0,
                "average_score": 100.0,
                "duration_s": 12.5,
                "judge_enabled": False,
                "judge_scored": 0,
                "answer_only": False,
                "replay_path": None,
                "cached_responses": 3,
                "transient_failures": 0,
            },
            "results": [],
        }

        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            trend_path = append_trend(report, out_dir / "report.json", out_dir / "report.md", out_dir)
            content = trend_path.read_text()

        self.assertIn("average_score", content)
        self.assertIn("2026-05-17T00:00:00", content)
        self.assertIn("100.0", content)


class ObservabilityTests(unittest.TestCase):
    def test_trace_session_writes_local_json_without_llm_calls(self):
        previous_dir = os.environ.get("NEXUSIQ_TRACE_DIR")
        previous_enabled = os.environ.get("NEXUSIQ_TRACE_ENABLED")
        with TemporaryDirectory() as tmp:
            os.environ["NEXUSIQ_TRACE_DIR"] = tmp
            os.environ["NEXUSIQ_TRACE_ENABLED"] = "1"
            trace = get_tracer().start_trace("What was Q4 revenue?", {"force_source": None})
            with trace.span("routing") as span:
                span["metadata"]["source_type"] = "sql_rag"
            path = trace.finish({"source_type": "sql_rag", "from_cache": False})

            self.assertTrue(path.exists())
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertEqual(payload["question"], "What was Q4 revenue?")
            self.assertEqual(payload["final"]["source_type"], "sql_rag")
            self.assertEqual(payload["spans"][0]["name"], "routing")
            self.assertIn("span_id", payload["spans"][0])

        if previous_dir is None:
            os.environ.pop("NEXUSIQ_TRACE_DIR", None)
        else:
            os.environ["NEXUSIQ_TRACE_DIR"] = previous_dir
        if previous_enabled is None:
            os.environ.pop("NEXUSIQ_TRACE_ENABLED", None)
        else:
            os.environ["NEXUSIQ_TRACE_ENABLED"] = previous_enabled

    def test_agent_result_summary_keeps_debug_fields_compact(self):
        summary = summarize_agent_result(
            {
                "success": True,
                "answer": "A" * 700,
                "query": "SELECT SUM(total_amount) FROM sales_transactions",
                "row_count": 1,
                "model_used": "gemini-2.5-flash",
                "source": "SQL Database",
                "time": 1.2,
            }
        )

        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(summary["model_used"], "gemini-2.5-flash")
        self.assertLessEqual(len(summary["answer_preview"]), 500)

    def test_trace_summary_formats_key_spans(self):
        trace = {
            "schema_version": "1.0",
            "trace_id": "abc123",
            "question": "Q",
            "duration_s": 1.5,
            "final": {
                "source_type": "sql_only",
                "routing_model": "keyword fallback",
                "validation": None,
                "from_cache": False,
            },
            "spans": [
                {"name": "routing", "status": "ok", "duration_s": 0.1},
                {"name": "fusion.answer_generation", "status": "ok", "duration_s": 3.4},
            ],
        }

        summary = format_trace_summary(trace, Path("trace.json"))

        self.assertIn("Trace: abc123", summary)
        self.assertIn("Route: sql_only", summary)
        self.assertIn("routing", summary)
        self.assertIn("Slowest span: fusion.answer_generation", summary)
        self.assertIn("slow", summary)

        diagnostics = get_trace_diagnostics(trace)
        self.assertEqual(diagnostics["slowest_span"]["name"], "fusion.answer_generation")

    def test_trace_previews_can_be_disabled(self):
        previous = os.environ.get("NEXUSIQ_TRACE_INCLUDE_PREVIEWS")
        os.environ["NEXUSIQ_TRACE_INCLUDE_PREVIEWS"] = "0"
        try:
            summary = summarize_agent_result({"success": True, "answer": "Sensitive answer"})
            self.assertEqual(summary["answer_preview"], "[preview disabled]")
        finally:
            if previous is None:
                os.environ.pop("NEXUSIQ_TRACE_INCLUDE_PREVIEWS", None)
            else:
                os.environ["NEXUSIQ_TRACE_INCLUDE_PREVIEWS"] = previous

    def test_eval_report_trace_summary_highlights_slow_and_error_spans(self):
        trace = {
            "trace_id": "abc123",
            "spans": [
                {"name": "routing", "status": "ok", "duration_s": 0.2},
                {"name": "agent.sql", "status": "error", "duration_s": 4.2, "error": "quota"},
            ],
        }

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.json"
            path.write_text(json.dumps(trace))
            summary = summarize_trace_for_report(str(path))

        self.assertIn("slowest `agent.sql` 4.2s", summary)
        self.assertIn("errors `agent.sql`", summary)
        self.assertIn("slow spans `agent.sql` 4.2s", summary)


if __name__ == "__main__":
    unittest.main()
