"""Before/after eval for the business context layer.

Runs ambiguous business questions through real SQL generation with the
business context layer off ("before") and on ("after"), scores the generated
SQL against expected fragments, and verifies the SQL executes.

Scoring is deterministic (regex + execution), no LLM judge. Control cases
assert plain questions retrieve no context and keep working.

Usage:
    python -m evals.context_eval --mode both            # full before/after
    python -m evals.context_eval --mode after --limit 3
    python -m evals.context_eval --mode both --ids net_revenue_q4,active_customers
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

CASES_PATH = Path(__file__).parent / "context_cases.json"
REPORTS_DIR = Path(__file__).parent.parent / "eval-reports"


def load_cases(ids=None, limit=None):
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if ids:
        wanted = set(ids)
        cases = [case for case in cases if case["id"] in wanted]
    if limit:
        cases = cases[:limit]
    return cases


def score_case(case, sql, executed_ok, context_ids, mode="after"):
    sql_text = sql or ""
    fragment_results = {
        pattern: bool(re.search(pattern, sql_text, re.IGNORECASE | re.DOTALL))
        for pattern in case["expected_fragments"]
    }
    fragments_pass = all(fragment_results.values())

    # Context expectations: controls must retrieve nothing in every mode.
    # Ambiguous cases must retrieve their expected IDs when the layer is on
    # ("after"); in "before" mode the layer is off by construction, so the
    # ID check is vacuous there — before measures raw SQL quality only.
    expected_ids = set(case.get("expect_context_ids", []))
    if case.get("control"):
        context_pass = not context_ids
    elif mode == "after":
        context_pass = expected_ids.issubset(set(context_ids or []))
    else:
        context_pass = True

    return {
        "fragments_pass": fragments_pass,
        "fragment_results": fragment_results,
        "executed_ok": executed_ok,
        "context_ids": context_ids or [],
        "context_pass": context_pass,
        "pass": fragments_pass and executed_ok and context_pass,
    }


def run_mode(agent, cases, mode, delay):
    os.environ["NEXUSIQ_BUSINESS_CONTEXT"] = "1" if mode == "after" else "0"
    os.environ["NEXUSIQ_MEASUREMENT_PROFILE"] = f"context_eval_{mode}"
    results = {}
    for index, case in enumerate(cases):
        if index:
            time.sleep(delay)
        generation = agent.generate_query(case["question"])
        sql = generation.get("query")
        executed_ok = False
        execution_error = None
        if generation.get("success") and sql:
            execution = agent.execute_query(sql)
            executed_ok = bool(execution.get("success"))
            execution_error = execution.get("error")
        context_meta = generation.get("business_context") or {}
        scored = score_case(case, sql, executed_ok, context_meta.get("ids", []), mode=mode)
        scored["sql"] = sql
        scored["generation_error"] = generation.get("error")
        scored["execution_error"] = execution_error
        results[case["id"]] = scored
        status = "PASS" if scored["pass"] else "FAIL"
        print(f"  [{mode}] {case['id']}: {status} (context: {scored['context_ids'] or '-'})")
    return results


def comparison_table(cases, before, after):
    lines = [
        "| Case | Control | Before | After | Context applied |",
        "|------|---------|--------|-------|-----------------|",
    ]
    for case in cases:
        case_id = case["id"]
        before_result = before.get(case_id, {})
        after_result = after.get(case_id, {})
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                case_id,
                "yes" if case.get("control") else "no",
                "PASS" if before_result.get("pass") else "FAIL",
                "PASS" if after_result.get("pass") else "FAIL",
                ", ".join(after_result.get("context_ids", [])) or "—",
            )
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Business context layer before/after eval")
    parser.add_argument("--mode", choices=["before", "after", "both"], default="both")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated case IDs")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=4.0, help="Seconds between LLM calls")
    args = parser.parse_args()

    cases = load_cases(args.ids.split(",") if args.ids else None, args.limit)
    print(f"Business context eval — {len(cases)} cases, mode={args.mode}\n")

    from agents.sql_agent import SQLAgent

    agent = SQLAgent(mode="development")
    original_flag = os.environ.get("NEXUSIQ_BUSINESS_CONTEXT")

    report = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "cases": [case["id"] for case in cases],
    }
    try:
        if args.mode in {"before", "both"}:
            print("Running BEFORE (business context OFF):")
            report["before"] = run_mode(agent, cases, "before", args.delay)
            print()
        if args.mode in {"after", "both"}:
            print("Running AFTER (business context ON):")
            report["after"] = run_mode(agent, cases, "after", args.delay)
            print()
    finally:
        if original_flag is None:
            os.environ.pop("NEXUSIQ_BUSINESS_CONTEXT", None)
        else:
            os.environ["NEXUSIQ_BUSINESS_CONTEXT"] = original_flag
        agent.close()

    if args.mode == "both":
        table = comparison_table(cases, report["before"], report["after"])
        print(table)
        before_passes = sum(result["pass"] for result in report["before"].values())
        after_passes = sum(result["pass"] for result in report["after"].values())
        ambiguous = [case for case in cases if not case.get("control")]
        before_ambiguous = sum(report["before"][case["id"]]["pass"] for case in ambiguous)
        after_ambiguous = sum(report["after"][case["id"]]["pass"] for case in ambiguous)
        summary = (
            f"\nTotal: before {before_passes}/{len(cases)} -> after {after_passes}/{len(cases)} | "
            f"Ambiguous cases: before {before_ambiguous}/{len(ambiguous)} -> after {after_ambiguous}/{len(ambiguous)}"
        )
        print(summary)
        report["summary"] = {
            "before_pass": before_passes,
            "after_pass": after_passes,
            "ambiguous_before_pass": before_ambiguous,
            "ambiguous_after_pass": after_ambiguous,
            "total_cases": len(cases),
            "ambiguous_cases": len(ambiguous),
        }
        report["markdown_table"] = table

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / f"context_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReport written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
