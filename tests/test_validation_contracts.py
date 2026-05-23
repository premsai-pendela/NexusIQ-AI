import json
import os
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.fusion_agent import FusionAgent
from agents.rag_agent import RAGAgent
from agents.web_agent import WebAgent
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
from ui.fusion_chat import (
    escape_streamlit_math,
    find_previous_answer,
    normalize_repeat_question,
    previous_answer_message,
)
from utils.llm_gateway import LLMGateway
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

    def test_q4_electronics_revenue_validates_from_pdf_percentage_of_total(self):
        sql_result = {
            "success": True,
            "answer": "Q4 Electronics revenue was $31,710,925.89 across 5,899 transactions.",
            "results": [{"q4_electronics_revenue": 31_710_925.89, "transactions_analyzed": 5_899}],
        }
        rag_result = {
            "success": True,
            "answer": "In Q4 2024, total revenue was $59.3M, and Electronics accounted for 53.4% of this revenue. (Source: 01_Q4_2024_Financial_Report.pdf, Page 1)",
        }

        validation = self.agent._cross_validate(sql_result, rag_result)

        self.assertTrue(validation["validated"])
        self.assertEqual(validation["confidence"], "HIGH")
        self.assertEqual(validation["matches"][0]["rag_label"], "derived_percentage_revenue")

    def test_high_confidence_fusion_answer_is_stable_for_public_demo(self):
        sql_result = {
            "success": True,
            "answer": "Q4 Electronics revenue was $31,710,925.89 across 5,899 transactions.",
            "results": [{"q4_electronics_revenue": 31_710_925.89, "transactions_analyzed": 5_899}],
            "row_count": 1,
        }
        rag_result = {
            "success": True,
            "answer": "In Q4 2024, total revenue was $59.3M, and Electronics accounted for 53.4% of this revenue.",
            "chunks_retrieved": 5,
        }
        validation = self.agent._cross_validate(sql_result, rag_result)

        answer = self.agent._generate_fused_answer(
            "Validate Q4 Electronics revenue across SQL and PDF reports.",
            sql_result=sql_result,
            rag_result=rag_result,
            validation=validation,
        )

        self.assertIn("$31,710,925.89", answer)
        self.assertIn("$31,666,200.00", answer)
        self.assertIn("5,899 transactions", answer)
        self.assertIn("**Confidence:** HIGH", answer)
        self.assertNotIn("fromtheSQL", answer)
        self.assertNotIn("*from", answer)

    def test_high_confidence_sql_rag_result_is_cacheable(self):
        result = {
            "answer": "Validated answer",
            "source_type": "sql_rag",
            "sql_result": {"success": True},
            "rag_result": {"success": True},
            "validation": {
                "validated": True,
                "confidence": "HIGH",
                "matches": [{"sql_label": "revenue"}],
                "discrepancies": [],
            },
        }

        should_cache, reason = self.agent._should_cache_result("sql_rag", result)

        self.assertTrue(should_cache)
        self.assertEqual(reason, "passed_quality_gate")

    def test_low_confidence_sql_rag_result_is_not_cacheable(self):
        result = {
            "answer": "Uncertain answer",
            "source_type": "sql_rag",
            "sql_result": {"success": True},
            "rag_result": {"success": True},
            "validation": {
                "validated": False,
                "confidence": "LOW",
                "matches": [],
                "discrepancies": [{"sql": 10, "rag": 20}],
            },
        }

        should_cache, reason = self.agent._should_cache_result("sql_rag", result)

        self.assertFalse(should_cache)
        self.assertEqual(reason, "validation_not_verified")

    def test_degraded_sql_failed_result_is_not_cacheable(self):
        result = {
            "answer": "Document-only fallback",
            "source_type": "rag_only (sql_failed)",
            "sql_result": {"success": False, "error": "quota"},
            "rag_result": {"success": True, "chunks_retrieved": 2},
        }

        should_cache, reason = self.agent._should_cache_result("rag_only (sql_failed)", result)

        self.assertFalse(should_cache)
        self.assertEqual(reason, "degraded_sql_failed")

    def test_cache_key_matches_reordered_sql_pdf_question(self):
        self.agent._query_cache = {}
        self.agent._cache_ttl = 3600
        self.agent._cache_max = 50
        result = {"answer": "Validated answer", "source_type": "sql_rag"}

        self.agent._cache_set("Validate Q4 Electronics revenue across SQL and PDF reports.", result)
        cached = self.agent._cache_get("Validate Q4 Electronics revenue across PDF and sql reports.")

        self.assertIsNotNone(cached)
        self.assertTrue(cached["_from_cache"])


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


class FakeTracker:
    def __init__(self, unavailable=None):
        self.unavailable = unavailable or {}
        self.successes = []
        self.failures = []

    def is_available(self, model_name):
        if model_name in self.unavailable:
            return False, self.unavailable[model_name]
        return True, "available"

    def report_success(self, model_name):
        self.successes.append(model_name)

    def report_failure(self, model_name, error_message):
        self.failures.append((model_name, error_message))


class RecordingGateway:
    def __init__(self, response="answer", model_used="Recorded Model"):
        self.response = response
        self.model_used = model_used
        self.calls = []

    def invoke_with_fallback(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "response": self.response,
            "model_used": self.model_used,
            "models_tried": [],
        }


class LLMGatewayTests(unittest.TestCase):
    def test_gateway_records_success_without_prompt_text(self):
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "llm-ledger.jsonl"

            def factory(model_config, temperature):
                class Client:
                    def invoke(self, prompt):
                        return FakeLLMResponse("SELECT COUNT(*) FROM sales_transactions")

                return Client()

            gateway = LLMGateway(ledger_path=ledger_path, client_factory=factory)
            tracker = FakeTracker()
            result = gateway.invoke_with_fallback(
                prompt="secret-ish prompt that should not be stored",
                models=[{"name": "test-model", "type": "fake", "description": "Test Model"}],
                tracker=tracker,
                task="sql.generate_query",
                temperature=0.1,
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["response"], "SELECT COUNT(*) FROM sales_transactions")
            self.assertEqual(tracker.successes, ["test-model"])

            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual(events[0]["task"], "sql.generate_query")
            self.assertEqual(events[0]["model"], "test-model")
            self.assertEqual(events[0]["status"], "success")
            self.assertIn("prompt_hash", events[0])
            self.assertNotIn("secret-ish prompt", ledger_path.read_text())

    def test_gateway_skips_unavailable_model_then_falls_back(self):
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "llm-ledger.jsonl"

            def factory(model_config, temperature):
                class Client:
                    def invoke(self, prompt):
                        return FakeLLMResponse("fallback answer")

                return Client()

            gateway = LLMGateway(ledger_path=ledger_path, client_factory=factory)
            tracker = FakeTracker(unavailable={"primary": "RESOURCE_EXHAUSTED: Retry in 20m"})
            result = gateway.invoke_with_fallback(
                prompt="Question",
                models=[
                    {"name": "primary", "type": "fake", "description": "Primary"},
                    {"name": "fallback", "type": "fake", "description": "Fallback"},
                ],
                tracker=tracker,
                task="rag.answer",
                temperature=0.2,
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["model_used"], "Fallback")
            self.assertEqual(result["models_tried"][0]["status"], "⏭️ SKIPPED")
            self.assertEqual(tracker.successes, ["fallback"])

            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual([event["status"] for event in events], ["skipped", "success"])

    def test_gateway_reports_failure_before_next_model(self):
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "llm-ledger.jsonl"

            def factory(model_config, temperature):
                class Client:
                    def invoke(self, prompt):
                        if model_config["name"] == "broken":
                            raise RuntimeError("429 quota exceeded")
                        return FakeLLMResponse("ok")

                return Client()

            gateway = LLMGateway(ledger_path=ledger_path, client_factory=factory)
            tracker = FakeTracker()
            result = gateway.invoke_with_fallback(
                prompt="Question",
                models=[
                    {"name": "broken", "type": "fake", "description": "Broken"},
                    {"name": "working", "type": "fake", "description": "Working"},
                ],
                tracker=tracker,
                task="fusion.answer",
            )

            self.assertTrue(result["success"])
            self.assertEqual(tracker.failures[0][0], "broken")
            self.assertEqual(tracker.successes, ["working"])
            self.assertEqual(result["models_tried"][0]["status"], "❌ QUOTA EXCEEDED")

    def test_gateway_falls_back_when_task_response_fails_validation(self):
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "llm-ledger.jsonl"

            def factory(model_config, temperature):
                class Client:
                    def invoke(self, prompt):
                        if model_config["name"] == "malformed":
                            return FakeLLMResponse("not json")
                        return FakeLLMResponse('{"sql": false, "rag": true, "web": false}')

                return Client()

            gateway = LLMGateway(ledger_path=ledger_path, client_factory=factory)
            tracker = FakeTracker()
            result = gateway.invoke_with_fallback(
                prompt="route this",
                models=[
                    {"name": "malformed", "type": "fake"},
                    {"name": "valid", "type": "fake"},
                ],
                tracker=tracker,
                task="fusion.route",
                response_validator=lambda content: content.startswith("{"),
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["model_used"], "valid")
            self.assertEqual(tracker.failures, [])
            self.assertEqual(result["models_tried"][0]["status"], "❌ INVALID RESPONSE")
            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual([event["status"] for event in events], ["failed", "success"])
            self.assertIn("task validation", events[0]["error"])


class RoutingAndInputTests(unittest.TestCase):
    def test_streamlit_markdown_escapes_currency_math(self):
        text = "**$31,710,925.89** across **5,899 transactions**, while **$31,700,000.00**"

        escaped = escape_streamlit_math(text)

        self.assertEqual(
            escaped,
            "**\\$31,710,925.89** across **5,899 transactions**, while **\\$31,700,000.00**",
        )

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

    def test_repeat_lookup_matches_same_question_and_source_filter(self):
        now = datetime.now()
        history = [
            {
                "question": "What was Q4 revenue?",
                "answer": "Prior answer",
                "source_filter": "Auto",
                "timestamp": now,
            }
        ]

        self.assertIsNotNone(find_previous_answer(history, "  what was q4 revenue?  ", "Auto"))
        self.assertIsNone(find_previous_answer(history, "What was Q4 revenue?", "SQL Only"))

    def test_repeat_lookup_matches_reordered_sql_pdf_question(self):
        now = datetime.now()
        history = [
            {
                "question": "Validate Q4 Electronics revenue across SQL and PDF reports.",
                "answer": "Prior answer",
                "source_filter": "Auto",
                "timestamp": now,
            }
        ]

        self.assertEqual(
            normalize_repeat_question("Validate Q4 Electronics revenue across SQL and PDF reports."),
            normalize_repeat_question("Validate Q4 Electronics revenue across PDF and sql reports."),
        )
        self.assertIsNotNone(
            find_previous_answer(
                history,
                "Validate Q4 Electronics revenue across PDF and sql reports.",
                "Auto",
            )
        )

    def test_question_resolution_does_not_rewrite_self_contained_policy_question(self):
        class ExplodingClient:
            def invoke(self, prompt):
                raise AssertionError("Self-contained question should not call LLM resolver")

        agent = FusionAgent.__new__(FusionAgent)
        agent._history = [
            {
                "question": "Validate Q4 Electronics revenue across SQL and PDF reports.",
                "answer": "Q4 Electronics revenue was validated.",
            }
        ]
        agent.gemini_flash = ExplodingClient()
        agent.groq_client = ExplodingClient()

        question = "What is the return policy?"

        self.assertFalse(agent._needs_history_resolution(question))
        self.assertEqual(agent._resolve_question(question), question)

    def test_question_resolution_allows_contextual_followup(self):
        agent = FusionAgent.__new__(FusionAgent)
        self.assertTrue(agent._needs_history_resolution("What about Q3?"))
        self.assertTrue(agent._needs_history_resolution("Compare that with Q2"))
        self.assertFalse(agent._needs_history_resolution("what is policy for returns?"))

    def test_contextual_resolution_runs_through_gateway_task(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent._history = [{"question": "Q4 Electronics revenue?", "answer": "$31.7M"}]
        agent.gemini_flash = object()
        agent.groq_client = None
        agent.llm_gateway = RecordingGateway("What was Q3 Electronics revenue?")

        resolved = agent._resolve_question("What about Q3?")

        self.assertEqual(resolved, "What was Q3 Electronics revenue?")
        self.assertEqual(agent.llm_gateway.calls[0]["task"], "fusion.resolve_question")

    def test_routing_runs_through_gateway_task(self):
        agent = FusionAgent.__new__(FusionAgent)
        agent._history = []
        agent.gemini_flash = object()
        agent.groq_client = None
        agent._gemini_routing_calls = []
        agent._gemini_rpm_limit = 4
        agent.llm_gateway = RecordingGateway(
            '{"sql": false, "rag": true, "web": false, "cross_validate": false, "reasoning": "policy"}',
            "Gemini Flash",
        )

        route = agent._classify_query_source_llm("What is the return policy?")

        self.assertEqual(route, "rag_only")
        self.assertEqual(agent.llm_gateway.calls[0]["task"], "fusion.route")

    def test_rag_answer_generation_runs_through_gateway_task(self):
        agent = RAGAgent.__new__(RAGAgent)
        agent.gemini_pro = None
        agent.gemini_flash = None
        agent.groq_client = object()
        agent.llm_gateway = RecordingGateway("Return policy answer", "Groq Llama")

        answer, model, _ = agent._generate_answer_with_fallback("prompt", "simple")

        self.assertEqual(answer, "Return policy answer")
        self.assertEqual(model, "Groq Llama")
        self.assertEqual(agent.llm_gateway.calls[0]["task"], "rag.answer")

    def test_web_answer_generation_runs_through_gateway_task(self):
        agent = WebAgent.__new__(WebAgent)
        agent.groq_client = object()
        agent.llm_gateway = RecordingGateway("Competitor summary", "Groq Llama")
        agent.scrape_competitor_pricing = lambda category: {"competitors": [], "category": category}

        result = agent.query("Compare electronics prices", category="Electronics")

        self.assertEqual(result["answer"], "Competitor summary")
        self.assertEqual(agent.llm_gateway.calls[0]["task"], "web.answer")

    def test_previous_answer_message_marks_answer_as_cache_result(self):
        previous = {
            "answer": "Prior answer",
            "source_type": "sql_rag",
            "timestamp": datetime.now(),
        }

        msg = previous_answer_message(previous, "msg-1")

        self.assertEqual(msg["role"], "assistant")
        self.assertTrue(msg["from_cache"])
        self.assertEqual(msg["cache_label"], "previous_answer")
        self.assertEqual(msg["query_time"], 0.0)


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
        previous_index = os.environ.get("NEXUSIQ_TRACE_INDEX_PATH")
        previous_enabled = os.environ.get("NEXUSIQ_TRACE_ENABLED")
        with TemporaryDirectory() as tmp:
            os.environ["NEXUSIQ_TRACE_DIR"] = tmp
            os.environ["NEXUSIQ_TRACE_INDEX_PATH"] = str(Path(tmp) / "query_traces.jsonl")
            os.environ["NEXUSIQ_TRACE_ENABLED"] = "1"
            trace = get_tracer().start_trace("What was Q4 revenue?", {"force_source": None})
            with trace.span("routing") as span:
                span["metadata"]["source_type"] = "sql_rag"
            path = trace.finish({
                "source_type": "sql_rag",
                "from_cache": False,
                "routing_model": "Gemini Flash",
                "answer_models": "SQL: Groq Llama 3.3 70B",
            })

            self.assertTrue(path.exists())
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertEqual(payload["question"], "What was Q4 revenue?")
            self.assertEqual(payload["final"]["source_type"], "sql_rag")
            self.assertEqual(payload["final"]["answer_models"], "SQL: Groq Llama 3.3 70B")
            self.assertEqual(payload["spans"][0]["name"], "routing")
            self.assertIn("span_id", payload["spans"][0])
            index_path = Path(os.environ["NEXUSIQ_TRACE_INDEX_PATH"])
            index_row = json.loads(index_path.read_text().splitlines()[0])
            self.assertEqual(index_row["trace_id"], payload["trace_id"])
            self.assertEqual(index_row["answer_models"], "SQL: Groq Llama 3.3 70B")

        if previous_dir is None:
            os.environ.pop("NEXUSIQ_TRACE_DIR", None)
        else:
            os.environ["NEXUSIQ_TRACE_DIR"] = previous_dir
        if previous_index is None:
            os.environ.pop("NEXUSIQ_TRACE_INDEX_PATH", None)
        else:
            os.environ["NEXUSIQ_TRACE_INDEX_PATH"] = previous_index
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
