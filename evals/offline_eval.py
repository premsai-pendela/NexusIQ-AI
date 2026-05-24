"""
Deterministic offline evaluation harness for NexusIQ-AI validation behavior.

This harness does not call LLM providers, web scrapers, ChromaDB, or the SQL
database. It uses fixed SQL/RAG/Web result fixtures to prove that the validation
contracts around fused answers behave predictably.

Usage:
    python -m evals.offline_eval
    python -m evals.offline_eval --json
    python -m evals.offline_eval --output eval-reports
"""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.fusion_agent import FusionAgent


ALLOWED_SOURCE_TYPES = {
    "sql_only",
    "rag_only",
    "web_only",
    "sql_rag",
    "sql_web",
    "rag_web",
    "all",
    "comparison",
    "no_data",
}

ALLOWED_WEB_CATEGORIES = {"electronics", "home", "clothing", "food", "sports"}


@dataclass(frozen=True)
class OfflineEvalCase:
    name: str
    question: str
    source_type: str
    sql_result: Optional[Dict[str, Any]] = None
    rag_result: Optional[Dict[str, Any]] = None
    web_result: Optional[Dict[str, Any]] = None
    expected_confidence: Optional[str] = None
    expected_validated: Optional[bool] = None
    expected_min_matches: int = 0
    expected_min_discrepancies: int = 0
    notes: str = ""
    tags: List[str] = field(default_factory=list)


OFFLINE_EVAL_CASES: List[OfflineEvalCase] = [
    OfflineEvalCase(
        name="q4_electronics_sql_rag_high_confidence",
        question="What was Q4 2024 Electronics revenue?",
        source_type="sql_rag",
        sql_result={
            "success": True,
            "answer": "Q4 Electronics revenue was $33,885,324.16 across 7,721 transactions.",
            "results": [
                {
                    "q4_electronics_revenue": 33_885_324.16,
                    "transactions_analyzed": 7_721,
                }
            ],
            "row_count": 1,
        },
        rag_result={
            "success": True,
            "answer": "The Q4 financial report lists Electronics revenue at $33.9M.",
            "chunks_retrieved": 3,
            "sources": [{"filename": "01_Q4_2024_Financial_Report.pdf"}],
        },
        expected_confidence="HIGH",
        expected_validated=True,
        expected_min_matches=1,
        notes="Structured SQL revenue should validate against rounded PDF revenue.",
        tags=["sql", "rag", "cross-validation"],
    ),
    OfflineEvalCase(
        name="q4_total_sql_rag_discrepancy",
        question="Validate Q4 2024 revenue against the financial report.",
        source_type="sql_rag",
        sql_result={
            "success": True,
            "answer": "Actual Q4 transaction revenue was $45,195,318.45.",
            "results": [{"q4_revenue": 45_195_318.45}],
            "row_count": 1,
        },
        rag_result={
            "success": True,
            "answer": "The Q4 financial report lists reported revenue of $38.7M.",
            "chunks_retrieved": 4,
            "sources": [{"filename": "01_Q4_2024_Financial_Report.pdf"}],
        },
        expected_confidence="LOW",
        expected_validated=False,
        expected_min_discrepancies=1,
        notes="A material SQL/PDF mismatch should be flagged as low confidence.",
        tags=["sql", "rag", "discrepancy"],
    ),
    OfflineEvalCase(
        name="metadata_count_does_not_validate_revenue",
        question="Validate Q4 2024 revenue.",
        source_type="sql_rag",
        sql_result={
            "success": True,
            "answer": "The query analyzed 100,000 transactions.",
            "results": [{"transactions_analyzed": 100_000}],
            "row_count": 1,
        },
        rag_result={
            "success": True,
            "answer": "The Q4 financial report lists revenue of $45.2M.",
            "chunks_retrieved": 2,
            "sources": [{"filename": "01_Q4_2024_Financial_Report.pdf"}],
        },
        expected_confidence="MEDIUM",
        expected_validated=False,
        notes="Transaction count metadata must not validate or contradict PDF revenue.",
        tags=["sql", "rag", "metadata"],
    ),
    OfflineEvalCase(
        name="sql_only_result_contract",
        question="Which region had the highest revenue?",
        source_type="sql_only",
        sql_result={
            "success": True,
            "answer": "The West region had the highest revenue at $32.4M.",
            "query": "SELECT region, SUM(total_amount) AS revenue FROM sales_transactions GROUP BY region ORDER BY revenue DESC LIMIT 1",
            "results": [{"region": "West", "revenue": 32_400_000.0}],
            "row_count": 1,
        },
        notes="SQL-only answers require executable evidence and a non-empty answer.",
        tags=["sql", "contract"],
    ),
    OfflineEvalCase(
        name="rag_only_result_contract",
        question="What is the refund policy?",
        source_type="rag_only",
        rag_result={
            "success": True,
            "answer": "Customers may return most items within 30 days with proof of purchase.",
            "chunks_retrieved": 2,
            "sources": [{"filename": "Returns_Refunds_Policy.pdf"}],
        },
        notes="RAG-only answers require source evidence.",
        tags=["rag", "contract"],
    ),
    OfflineEvalCase(
        name="web_only_result_contract",
        question="What are competitor prices for electronics?",
        source_type="web_only",
        web_result={
            "success": True,
            "answer": "Electronics competitors show prices from $129.99 to $799.99.",
            "category": "electronics",
            "raw_data": {
                "competitors": [
                    {
                        "name": "Newegg",
                        "products": [
                            {"name": "Wireless Headphones", "price": 129.99},
                            {"name": "Gaming Monitor", "price": 799.99},
                        ],
                    }
                ]
            },
        },
        notes="Web answers require a recognized category and product price evidence.",
        tags=["web", "contract"],
    ),
    OfflineEvalCase(
        name="web_stale_cache_disclosure_contract",
        question="What is the price range for Goal Zero products?",
        source_type="web_only",
        web_result={
            "success": True,
            "answer": "Goal Zero: $262.89 - $599.95. Prices are cached; live refresh failed.",
            "category": "electronics",
            "raw_data": {
                "competitors": [{
                    "competitor": "Goal Zero",
                    "data_status": "cached_stale",
                    "captured_at": "2026-05-23T15:28:58",
                    "products": [{"name": "Yeti 300", "price": "$262.89"}],
                }]
            },
        },
        notes="Stale cached Web evidence remains usable only with clear disclosure.",
        tags=["web", "cache", "trust"],
    ),
]


def validate_sql_result(result: Optional[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    if not result:
        return ["missing SQL result"]
    if not result.get("success"):
        issues.append(f"SQL result was not successful: {result.get('error', 'unknown error')}")
    if not str(result.get("answer", "")).strip():
        issues.append("SQL result is missing answer text")
    if result.get("row_count", 0) > 0 and not result.get("results"):
        issues.append("SQL row_count is positive but results are empty")
    if result.get("results") is not None and not isinstance(result.get("results"), list):
        issues.append("SQL results must be a list of row dictionaries")
    return issues


def validate_rag_result(result: Optional[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    if not result:
        return ["missing RAG result"]
    if not result.get("success"):
        issues.append(f"RAG result was not successful: {result.get('error', 'unknown error')}")
    if not str(result.get("answer", "")).strip():
        issues.append("RAG result is missing answer text")
    if result.get("chunks_retrieved", 0) <= 0:
        issues.append("RAG result has no retrieved chunks")
    if not result.get("sources"):
        issues.append("RAG result is missing source citations")
    return issues


def _iter_web_products(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    raw_data = result.get("raw_data") or {}
    for competitor in raw_data.get("competitors", []):
        products.extend(competitor.get("products", []))
    return products


def validate_web_result(result: Optional[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    if not result:
        return ["missing Web result"]
    if not result.get("success"):
        issues.append(f"Web result was not successful: {result.get('error', 'unknown error')}")
    if not str(result.get("answer", "")).strip():
        issues.append("Web result is missing answer text")

    category = result.get("category")
    if category not in ALLOWED_WEB_CATEGORIES:
        issues.append(f"Web category must be one of {sorted(ALLOWED_WEB_CATEGORIES)}")

    products = _iter_web_products(result)
    if not products:
        issues.append("Web result is missing competitor product evidence")
    for product in products:
        price = product.get("price")
        if isinstance(price, str):
            match = re.search(r"\d[\d,]*(?:\.\d+)?", price)
            try:
                price = Decimal(match.group(0).replace(",", "")) if match else None
            except InvalidOperation:
                price = None
        if not isinstance(price, (int, float, Decimal)) or price <= 0:
            issues.append(f"Invalid web product price: {product!r}")
            break
    competitors = (result.get("raw_data") or {}).get("competitors", [])
    if any(
        competitor.get("is_mock") or competitor.get("data_status") == "sample"
        for competitor in competitors
    ):
        issues.append("Web result uses sample data as live evidence")
    if any(competitor.get("data_status") == "cached_stale" for competitor in competitors):
        answer = str(result.get("answer", "")).lower()
        if "cached" not in answer or "refresh failed" not in answer:
            issues.append("Stale Web result must disclose cached data and refresh failure")
    return issues


class OfflineEvaluationHarness:
    def __init__(self) -> None:
        # Bypass FusionAgent.__init__ so offline evals never initialize live agents.
        self.fusion_agent = FusionAgent.__new__(FusionAgent)

    def run_case(self, case: OfflineEvalCase) -> Dict[str, Any]:
        issues: List[str] = []
        validation = None

        if case.source_type not in ALLOWED_SOURCE_TYPES:
            issues.append(f"unknown source_type: {case.source_type}")

        if "sql" in case.source_type:
            issues.extend(validate_sql_result(case.sql_result))
        if "rag" in case.source_type or case.source_type == "comparison":
            issues.extend(validate_rag_result(case.rag_result))
        if "web" in case.source_type or case.source_type == "all":
            issues.extend(validate_web_result(case.web_result))

        if case.sql_result and case.rag_result:
            validation = self.fusion_agent._cross_validate(case.sql_result, case.rag_result)
            if case.expected_confidence and validation.get("confidence") != case.expected_confidence:
                issues.append(
                    f"expected confidence {case.expected_confidence}, got {validation.get('confidence')}"
                )
            if case.expected_validated is not None and validation.get("validated") != case.expected_validated:
                issues.append(
                    f"expected validated={case.expected_validated}, got {validation.get('validated')}"
                )
            if len(validation.get("matches", [])) < case.expected_min_matches:
                issues.append(
                    f"expected at least {case.expected_min_matches} matches, got {len(validation.get('matches', []))}"
                )
            if len(validation.get("discrepancies", [])) < case.expected_min_discrepancies:
                issues.append(
                    "expected at least "
                    f"{case.expected_min_discrepancies} discrepancies, got {len(validation.get('discrepancies', []))}"
                )

        return {
            "name": case.name,
            "question": case.question,
            "source_type": case.source_type,
            "status": "pass" if not issues else "fail",
            "issues": issues,
            "validation": validation,
            "notes": case.notes,
            "tags": case.tags,
        }

    def run(self, cases: Optional[List[OfflineEvalCase]] = None) -> Dict[str, Any]:
        selected_cases = cases or OFFLINE_EVAL_CASES
        results = [self.run_case(case) for case in selected_cases]
        passed = sum(1 for result in results if result["status"] == "pass")
        return {
            "meta": {
                "date": datetime.now().isoformat(timespec="seconds"),
                "case_count": len(results),
                "passed": passed,
                "failed": len(results) - passed,
            },
            "results": results,
        }


def build_markdown_report(report: Dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        "# NexusIQ-AI Offline Evaluation Report",
        "",
        f"Date: {meta['date']}",
        f"Cases: {meta['case_count']}",
        f"Passed: {meta['passed']}",
        f"Failed: {meta['failed']}",
        "",
        "| Case | Source | Status | Validation | Notes |",
        "|------|--------|--------|------------|-------|",
    ]
    for result in report["results"]:
        validation = result.get("validation") or {}
        validation_label = validation.get("confidence", "n/a")
        if validation:
            validation_label += f" ({validation.get('confidence_reason')})"
        issue_text = "; ".join(result["issues"])
        status = "PASS" if result["status"] == "pass" else f"FAIL: {issue_text}"
        lines.append(
            f"| `{result['name']}` | `{result['source_type']}` | {status} | "
            f"{validation_label} | {result['notes']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic NexusIQ-AI offline evals")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    parser.add_argument("--output", type=str, help="Write JSON and Markdown reports to this directory")
    args = parser.parse_args()

    harness = OfflineEvaluationHarness()
    report = harness.run()

    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        (out_dir / f"offline-eval-{timestamp}.json").write_text(json.dumps(report, indent=2))
        (out_dir / f"offline-eval-{timestamp}.md").write_text(build_markdown_report(report))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(build_markdown_report(report))

    return 0 if report["meta"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
