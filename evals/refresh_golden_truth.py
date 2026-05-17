"""
Refresh numeric golden eval expectations from the configured DATABASE_URL.

This keeps golden evals aligned with the database the app actually uses.

Usage:
    python -m evals.refresh_golden_truth --dry-run
    python -m evals.refresh_golden_truth
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import create_engine, text

from config.settings import settings


CASES_PATH = Path(__file__).with_name("golden_cases.json")

TRUTH_QUERIES = {
    "q4_electronics_revenue": {
        "label": "Q4 2024 Electronics revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE product_category = 'Electronics'
              AND transaction_date >= '2024-10-01'
              AND transaction_date < '2025-01-01'
        """,
    },
    "q4_total_revenue_validation": {
        "label": "Q4 2024 revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE transaction_date >= '2024-10-01'
              AND transaction_date < '2025-01-01'
        """,
    },
    "annual_total_revenue": {
        "label": "total 2024 revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE transaction_date >= '2024-01-01'
              AND transaction_date < '2025-01-01'
        """,
    },
    "top_region_by_revenue": {
        "label": "West revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE region = 'West'
        """,
    },
    "q3_q4_performance_comparison:q3": {
        "case_id": "q3_q4_performance_comparison",
        "label": "Q3 revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE transaction_date >= '2024-07-01'
              AND transaction_date < '2024-10-01'
        """,
    },
    "q3_q4_performance_comparison:q4": {
        "case_id": "q3_q4_performance_comparison",
        "label": "Q4 revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE transaction_date >= '2024-10-01'
              AND transaction_date < '2025-01-01'
        """,
    },
    "full_q4_business_analysis": {
        "label": "Q4 2024 revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE transaction_date >= '2024-10-01'
              AND transaction_date < '2025-01-01'
        """,
    },
    "region_typo_autocorrect": {
        "label": "West revenue",
        "sql": """
            SELECT SUM(total_amount) AS value
            FROM sales_transactions
            WHERE region = 'West'
        """,
    },
}


def _as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return round(float(value), 2)
    return round(float(value), 2)


def fetch_truth_values() -> Dict[str, float]:
    engine = create_engine(settings.database_url)
    values: Dict[str, float] = {}
    with engine.connect() as conn:
        for key, query in TRUTH_QUERIES.items():
            row = conn.execute(text(query["sql"])).mappings().first()
            if not row or row["value"] is None:
                raise RuntimeError(f"Truth query returned no value for {key}")
            values[key] = _as_float(row["value"])
    return values


def update_cases(cases: list[Dict[str, Any]], truth_values: Dict[str, float]) -> list[Dict[str, Any]]:
    case_by_id = {case["id"]: case for case in cases}

    for key, value in truth_values.items():
        query = TRUTH_QUERIES[key]
        case_id = query.get("case_id", key)
        label = query["label"]
        case = case_by_id.get(case_id)
        if not case:
            continue

        for expected in case.get("expected_numbers", []):
            if expected.get("label") == label:
                expected["value"] = value
                break

    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh golden numeric truth from DATABASE_URL")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="Golden cases JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text())
    truth_values = fetch_truth_values()
    updated = update_cases(cases, truth_values)

    print("Golden truth from configured DATABASE_URL:")
    for key, value in truth_values.items():
        query = TRUTH_QUERIES[key]
        print(f"  {query.get('case_id', key)} / {query['label']}: {value:,.2f}")

    if args.dry_run:
        return 0

    args.cases.write_text(json.dumps(updated, indent=2) + "\n")
    print(f"Updated {args.cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

