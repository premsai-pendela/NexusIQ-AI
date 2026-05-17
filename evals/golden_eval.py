"""
Golden-answer evaluation runner for NexusIQ-AI.

This is the production-style eval layer:
  1. Load a small golden dataset of business questions.
  2. Run each question through the real FusionAgent.
  3. Score objective behavior with rule-based metrics.
  4. Optionally add an LLM judge score for answer quality.

Usage:
    python -m evals.golden_eval --dry-run
    python -m evals.golden_eval --ids q4_electronics_revenue,refund_policy
    python -m evals.golden_eval --limit 3
    python -m evals.golden_eval --with-judge
    python -m evals.golden_eval --answer-only --delay 8 --retries 1
    python -m evals.golden_eval --replay latest
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from run_tests import routing_matches
from observability.inspect_traces import get_trace_diagnostics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = Path(__file__).with_name("golden_cases.json")
DEFAULT_OUTPUT_DIR = ROOT / "eval-reports"

RULE_POINTS = {
    "route": 15,
    "numbers": 20,
    "confidence": 15,
    "evidence": 15,
    "safety": 5,
}
JUDGE_POINTS = 30


def load_cases(path: Path = DEFAULT_CASES_PATH) -> List[Dict[str, Any]]:
    return json.loads(path.read_text())


def _normalize_text(value: Any) -> str:
    return str(value or "").lower()


def _source_text(response: Dict[str, Any]) -> str:
    pieces = [response.get("answer", ""), response.get("source_type", "")]

    for key in ("sql_result", "rag_result", "web_result"):
        value = response.get(key)
        if value:
            pieces.append(json.dumps(value, default=str))
    if response.get("sources"):
        pieces.append(json.dumps(response["sources"], default=str))
    return "\n".join(str(piece) for piece in pieces if piece)


def extract_numbers(text: str) -> List[float]:
    """Extract plain, currency, and scaled numbers from natural-language output."""
    values: List[float] = []
    pattern = re.compile(r"\$?\b(\d[\d,]*(?:\.\d+)?)\s*(m|million|b|billion)?\b", re.IGNORECASE)
    for match in pattern.finditer(text or ""):
        raw_number, scale = match.groups()
        try:
            value = float(raw_number.replace(",", ""))
        except ValueError:
            continue

        scale_lower = (scale or "").lower()
        if scale_lower in {"m", "million"}:
            value *= 1_000_000
        elif scale_lower in {"b", "billion"}:
            value *= 1_000_000_000

        values.append(value)
    return values


def number_matches(actual_values: Iterable[float], expected: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    target = float(expected["value"])
    tolerance_pct = float(expected.get("tolerance_pct", 2.0))
    best_diff: Optional[float] = None

    for value in actual_values:
        if target == 0:
            pct_diff = 0 if value == 0 else math.inf
        else:
            pct_diff = abs(value - target) / abs(target) * 100
        if best_diff is None or pct_diff < best_diff:
            best_diff = pct_diff
        if pct_diff <= tolerance_pct:
            return True, pct_diff
    return False, best_diff


def score_case_rules(case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
    source_text = _source_text(response)
    source_text_lower = _normalize_text(source_text)
    answer_lower = _normalize_text(response.get("answer", ""))
    actual_route = response.get("source_type", "unknown")

    checks: Dict[str, Dict[str, Any]] = {}

    expected_route = case.get("expected_route")
    if response.get("_eval_answer_only"):
        checks["route"] = {
            "passed": True,
            "points": 0,
            "max_points": 0,
            "detail": f"skipped in answer-only mode; forced={expected_route}, actual={actual_route}",
        }
    else:
        route_ok = routing_matches(actual_route, expected_route) if expected_route else True
        checks["route"] = {
            "passed": route_ok,
            "points": RULE_POINTS["route"] if route_ok else 0,
            "max_points": RULE_POINTS["route"],
            "detail": f"expected={expected_route}, actual={actual_route}",
        }

    expected_numbers = case.get("expected_numbers", [])
    actual_numbers = extract_numbers(source_text)
    number_details = []
    number_passes = []
    for expected in expected_numbers:
        matched, best_diff = number_matches(actual_numbers, expected)
        number_passes.append(matched)
        best_detail = "not found" if best_diff is None else f"best_diff={best_diff:.2f}%"
        number_details.append(f"{expected.get('label', expected['value'])}: {best_detail}")
    numbers_ok = all(number_passes) if expected_numbers else True
    checks["numbers"] = {
        "passed": numbers_ok,
        "points": RULE_POINTS["numbers"] if numbers_ok else 0,
        "max_points": RULE_POINTS["numbers"],
        "detail": "; ".join(number_details) if number_details else "no numeric expectation",
    }

    expected_confidence = case.get("expected_confidence")
    actual_confidence = None
    if response.get("validation"):
        actual_confidence = response["validation"].get("confidence")
    confidence_ok = True if not expected_confidence else actual_confidence == expected_confidence
    checks["confidence"] = {
        "passed": confidence_ok,
        "points": RULE_POINTS["confidence"] if confidence_ok else 0,
        "max_points": RULE_POINTS["confidence"],
        "detail": f"expected={expected_confidence or 'n/a'}, actual={actual_confidence or 'n/a'}",
    }

    evidence_failures = []
    if case.get("requires_sql") and not (response.get("sql_result") or {}).get("success"):
        evidence_failures.append("missing successful SQL result")
    if case.get("requires_rag") and not (response.get("rag_result") or {}).get("success"):
        evidence_failures.append("missing successful RAG result")
    if case.get("requires_web") and not (response.get("web_result") or {}).get("success"):
        evidence_failures.append("missing successful Web result")

    for term in case.get("required_terms", []):
        if _normalize_text(term) not in answer_lower and _normalize_text(term) not in source_text_lower:
            evidence_failures.append(f"missing required term: {term}")
    for source in case.get("required_sources", []):
        if _normalize_text(source) not in source_text_lower:
            evidence_failures.append(f"missing required source signal: {source}")

    evidence_ok = not evidence_failures
    checks["evidence"] = {
        "passed": evidence_ok,
        "points": RULE_POINTS["evidence"] if evidence_ok else 0,
        "max_points": RULE_POINTS["evidence"],
        "detail": "ok" if evidence_ok else "; ".join(evidence_failures),
    }

    safety_failures = []
    for term in case.get("forbidden_terms", []):
        if _normalize_text(term) in answer_lower:
            safety_failures.append(f"forbidden term present: {term}")
    safety_ok = not safety_failures
    checks["safety"] = {
        "passed": safety_ok,
        "points": RULE_POINTS["safety"] if safety_ok else 0,
        "max_points": RULE_POINTS["safety"],
        "detail": "ok" if safety_ok else "; ".join(safety_failures),
    }

    rule_score = sum(check["points"] for check in checks.values())
    rule_max_score = sum(check["max_points"] for check in checks.values())
    return {
        "score": rule_score,
        "max_score": rule_max_score,
        "checks": checks,
        "actual_numbers": actual_numbers,
    }


def status_for_score(score: float) -> str:
    if score >= 85:
        return "pass"
    if score >= 70:
        return "warning"
    return "fail"


def build_case_result(
    case: Dict[str, Any],
    response: Optional[Dict[str, Any]],
    elapsed_s: float,
    error: Optional[str] = None,
    error_traceback: Optional[str] = None,
    judge: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if response is None:
        checks = {
            "execution": {
                "passed": False,
                "points": 0,
                "max_points": 100,
                "detail": error or "No response returned",
            }
        }
        return {
            "id": case["id"],
            "question": case["question"],
            "status": "fail",
            "score": 0,
            "max_score": 100,
            "rule_score": 0,
            "judge_score": None,
            "expected_route": case.get("expected_route"),
            "actual_route": None,
            "expected_confidence": case.get("expected_confidence"),
            "actual_confidence": None,
            "response": None,
            "checks": checks,
            "elapsed_s": round(elapsed_s, 2),
            "error": error,
            "error_traceback": error_traceback,
        }

    rule_result = score_case_rules(case, response)
    judge_score = None
    judge_points = None
    if judge:
        judge_score = float(judge.get("score", 0))
        judge_points = round(judge_score * JUDGE_POINTS, 2)
    elif case.get("judge_required"):
        # Keep max score at 70 when judge is skipped; no silent penalty for --no-judge.
        judge_points = None

    max_score = rule_result["max_score"] + (JUDGE_POINTS if judge_points is not None else 0)
    total_score = rule_result["score"] + (judge_points or 0)
    normalized_score = round(total_score / max_score * 100, 2) if max_score else 0

    return {
        "id": case["id"],
        "question": case["question"],
        "status": status_for_score(normalized_score),
        "score": normalized_score,
        "raw_score": total_score,
        "max_score": max_score,
        "rule_score": rule_result["score"],
        "rule_max_score": rule_result["max_score"],
        "judge_score": judge_score,
        "judge": judge,
        "checks": rule_result["checks"],
        "actual_route": response.get("source_type"),
        "expected_route": case.get("expected_route"),
        "actual_confidence": (response.get("validation") or {}).get("confidence"),
        "expected_confidence": case.get("expected_confidence"),
        "answer_snippet": (response.get("answer") or "")[:300].replace("\n", " "),
        "response": response,
        "trace_id": response.get("trace_id"),
        "trace_path": response.get("trace_path"),
        "transient_failure": response_has_transient_failure(response),
        "elapsed_s": round(elapsed_s, 2),
    }


def select_cases(cases: List[Dict[str, Any]], ids: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    selected = cases
    if ids:
        wanted = {item.strip() for item in ids.split(",") if item.strip()}
        selected = [case for case in selected if case["id"] in wanted]
    if limit:
        selected = selected[:limit]
    return selected


def resolve_replay_path(replay: str, out_dir: Path) -> Path:
    if replay == "latest":
        candidates = sorted(out_dir.glob("golden-eval-*.json"))
        for candidate in reversed(candidates):
            try:
                report = json.loads(candidate.read_text())
            except json.JSONDecodeError:
                continue
            if any(result.get("response") for result in report.get("results", [])):
                return candidate
        raise FileNotFoundError(f"No replayable golden eval JSON reports with cached responses found in {out_dir}")
    return Path(replay)


def replay_golden_eval(
    cases: List[Dict[str, Any]],
    replay_path: Path,
    with_judge: bool = False,
    answer_only: bool = False,
) -> Dict[str, Any]:
    started = time.time()
    prior_report = json.loads(replay_path.read_text())
    prior_by_id = {result.get("id"): result for result in prior_report.get("results", [])}

    judge_response = None
    if with_judge:
        from evals.judge import judge_response as _judge_response

        judge_response = _judge_response

    results = []
    for case in cases:
        prior = prior_by_id.get(case["id"])
        if not prior:
            result = build_case_result(
                case,
                None,
                0,
                error=f"No cached response found for {case['id']} in {replay_path}",
            )
            results.append(result)
            continue

        response = prior.get("response")
        if not response:
            result = build_case_result(
                case,
                None,
                prior.get("elapsed_s", 0),
                error=f"Cached result for {case['id']} has no stored response",
            )
            results.append(result)
            continue

        response = dict(response)
        if answer_only or response.get("_eval_answer_only"):
            response["_eval_answer_only"] = True

        judge_result = None
        if with_judge and case.get("judge_required") and judge_response:
            judge_result = judge_response(case, response)

        result = build_case_result(case, response, prior.get("elapsed_s", 0), judge=judge_result)
        result["replayed_from"] = str(replay_path)
        results.append(result)

    return summarize_results(results, started, with_judge, answer_only, replay_path=replay_path)


TRANSIENT_FAILURE_PATTERNS = [
    "technical issues",
    "all models failed",
    "resource_exhausted",
    "rate limit",
    "too many requests",
    "quota",
    "retry in",
    "deadline_exceeded",
    "connection",
    "timeout",
]


def response_has_transient_failure(response: Optional[Dict[str, Any]], error: Optional[str] = None) -> bool:
    combined = _normalize_text(error or "")
    if response:
        combined += "\n" + _normalize_text(_source_text(response))
    return any(pattern in combined for pattern in TRANSIENT_FAILURE_PATTERNS)


def run_single_case(
    agent,
    case: Dict[str, Any],
    with_judge: bool,
    judge_response,
    answer_only: bool,
) -> Tuple[Dict[str, Any], bool]:
    t0 = time.time()
    try:
        force_source = case.get("expected_route") if answer_only else None
        response = agent.query(case["question"], force_source=force_source)
        if answer_only:
            response["_eval_answer_only"] = True

        judge_result = None
        if with_judge and case.get("judge_required") and judge_response:
            judge_result = judge_response(case, response)

        elapsed = time.time() - t0
        result = build_case_result(case, response, elapsed, judge=judge_result)
        return result, response_has_transient_failure(response)
    except Exception as exc:
        elapsed = time.time() - t0
        result = build_case_result(
            case,
            None,
            elapsed,
            error=str(exc),
            error_traceback=traceback.format_exc(),
        )
        return result, response_has_transient_failure(None, str(exc))


def run_golden_eval(
    cases: List[Dict[str, Any]],
    with_judge: bool = False,
    delay_s: float = 0.0,
    retries: int = 0,
    retry_delay_s: float = 30.0,
    answer_only: bool = False,
) -> Dict[str, Any]:
    from agents.fusion_agent import get_fusion_agent

    results = []
    started = time.time()

    try:
        agent = get_fusion_agent()
    except Exception as exc:
        elapsed = time.time() - started
        init_traceback = traceback.format_exc()
        results = [
            build_case_result(
                case,
                None,
                elapsed,
                error=f"FusionAgent initialization failed: {exc}",
                error_traceback=init_traceback,
            )
            for case in cases
        ]
        return summarize_results(results, started, with_judge, answer_only)

    judge_response = None
    if with_judge:
        from evals.judge import judge_response as _judge_response

        judge_response = _judge_response

    try:
        for index, case in enumerate(cases, 1):
            print(f"[{index}/{len(cases)}] {case['id']}: {case['question'][:70]}...", flush=True)

            result = None
            for attempt in range(retries + 1):
                result, transient = run_single_case(agent, case, with_judge, judge_response, answer_only)
                if result["status"] != "fail" or not transient or attempt >= retries:
                    break
                print(
                    f"  transient failure; retrying in {retry_delay_s:.0f}s "
                    f"(attempt {attempt + 1}/{retries})",
                    flush=True,
                )
                time.sleep(retry_delay_s)

            print(f"  -> {result['status'].upper()} {result['score']}/100 ({result['elapsed_s']}s)", flush=True)
            results.append(result)
            if delay_s > 0 and index < len(cases):
                time.sleep(delay_s)
    finally:
        try:
            agent.close()
        except Exception:
            pass

    return summarize_results(results, started, with_judge, answer_only)


def summarize_results(
    results: List[Dict[str, Any]],
    started: float,
    with_judge: bool,
    answer_only: bool = False,
    replay_path: Optional[Path] = None,
) -> Dict[str, Any]:
    duration = time.time() - started
    passed = sum(1 for result in results if result["status"] == "pass")
    warnings = sum(1 for result in results if result["status"] == "warning")
    failed = sum(1 for result in results if result["status"] == "fail")
    avg_score = sum(result["score"] for result in results) / max(len(results), 1)
    judge_scored = sum(1 for result in results if result.get("judge_score") is not None)
    cached_responses = sum(1 for result in results if result.get("response"))
    transient_failures = sum(1 for result in results if result.get("transient_failure"))

    return {
        "meta": {
            "date": datetime.now().isoformat(timespec="seconds"),
            "case_count": len(results),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "average_score": round(avg_score, 2),
            "duration_s": round(duration, 2),
            "judge_enabled": with_judge,
            "judge_scored": judge_scored,
            "answer_only": answer_only,
            "replay_path": str(replay_path) if replay_path else None,
            "cached_responses": cached_responses,
            "transient_failures": transient_failures,
        },
        "results": results,
    }


def build_markdown_report(report: Dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        "# NexusIQ-AI Golden Eval Report",
        "",
        f"Date: {meta['date']}",
        f"Cases: {meta['case_count']}",
        f"Passed: {meta['passed']}",
        f"Warnings: {meta['warnings']}",
        f"Failed: {meta['failed']}",
        f"Average score: {meta['average_score']}/100",
        f"Duration: {meta['duration_s']}s",
        f"LLM judge: {'enabled' if meta['judge_enabled'] else 'disabled'}",
        f"LLM judge scored: {meta.get('judge_scored', 0)}/{meta['case_count']}",
        f"Answer-only mode: {'enabled' if meta.get('answer_only') else 'disabled'}",
        f"Replay source: {meta.get('replay_path') or 'none'}",
        f"Cached responses: {meta.get('cached_responses', 0)}/{meta['case_count']}",
        f"Transient failures detected: {meta.get('transient_failures', 0)}",
        "",
        "| Case | Score | Status | Route | Confidence | Notes |",
        "|------|-------|--------|-------|------------|-------|",
    ]
    for result in report["results"]:
        notes = []
        for name, check in result.get("checks", {}).items():
            if not check.get("passed"):
                notes.append(f"{name}: {check.get('detail')}")
        note_text = "<br>".join(notes) if notes else "ok"
        lines.append(
            f"| `{result['id']}` | {result['score']}/100 | {result['status'].upper()} | "
            f"`{result.get('expected_route')}` -> `{result.get('actual_route')}` | "
            f"`{result.get('expected_confidence') or 'n/a'}` -> `{result.get('actual_confidence') or 'n/a'}` | "
            f"{note_text} |"
        )

    failures = [result for result in report["results"] if result["status"] != "pass"]
    if failures:
        lines.extend(["", "## Non-Passing Cases", ""])
        for result in failures:
            lines.append(f"### {result['id']}")
            lines.append("")
            lines.append(f"Question: {result['question']}")
            lines.append("")
            lines.append(f"Answer snippet: {result.get('answer_snippet') or result.get('error')}")
            if result.get("trace_path"):
                lines.append("")
                lines.append(f"Trace: `{result.get('trace_path')}`")
                trace_summary = summarize_trace_for_report(result.get("trace_path"))
                if trace_summary:
                    lines.append(trace_summary)
            lines.append("")
            for name, check in result.get("checks", {}).items():
                lines.append(f"- {name}: {check.get('points')}/{check.get('max_points')} - {check.get('detail')}")
            lines.append("")

    return "\n".join(lines) + "\n"


def summarize_trace_for_report(trace_path: Optional[str]) -> str:
    if not trace_path:
        return ""
    try:
        trace = json.loads(Path(trace_path).read_text())
    except (OSError, json.JSONDecodeError):
        return ""

    diagnostics = get_trace_diagnostics(trace)
    parts = []
    slowest = diagnostics.get("slowest_span")
    if slowest:
        parts.append(f"slowest `{slowest.get('name')}` {slowest.get('duration_s')}s")
    error_spans = diagnostics.get("error_spans") or []
    if error_spans:
        parts.append(
            "errors "
            + ", ".join(f"`{span.get('name')}`" for span in error_spans)
        )
    slow_spans = diagnostics.get("slow_spans") or []
    if slow_spans:
        parts.append(
            "slow spans "
            + ", ".join(f"`{span.get('name')}` {span.get('duration_s')}s" for span in slow_spans[:3])
        )
    return f"Trace summary: {'; '.join(parts)}" if parts else ""


def write_reports(report: Dict[str, Any], out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = out_dir / f"golden-eval-{timestamp}.json"
    md_path = out_dir / f"golden-eval-{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str))
    md_path.write_text(build_markdown_report(report))
    return json_path, md_path


def append_trend(report: Dict[str, Any], json_path: Path, md_path: Path, out_dir: Path) -> Path:
    trend_path = out_dir / "trend.csv"
    fieldnames = [
        "date",
        "case_count",
        "passed",
        "warnings",
        "failed",
        "average_score",
        "duration_s",
        "judge_enabled",
        "judge_scored",
        "answer_only",
        "replay_path",
        "cached_responses",
        "transient_failures",
        "json_report",
        "md_report",
    ]
    meta = report["meta"]
    row = {
        "date": meta["date"],
        "case_count": meta["case_count"],
        "passed": meta["passed"],
        "warnings": meta["warnings"],
        "failed": meta["failed"],
        "average_score": meta["average_score"],
        "duration_s": meta["duration_s"],
        "judge_enabled": meta["judge_enabled"],
        "judge_scored": meta.get("judge_scored", 0),
        "answer_only": meta.get("answer_only", False),
        "replay_path": meta.get("replay_path") or "",
        "cached_responses": meta.get("cached_responses", 0),
        "transient_failures": meta.get("transient_failures", 0),
        "json_report": str(json_path),
        "md_report": str(md_path),
    }
    write_header = not trend_path.exists()
    with trend_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return trend_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NexusIQ-AI golden evals")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH, help="Path to golden cases JSON")
    parser.add_argument("--ids", type=str, help="Comma-separated case IDs to run")
    parser.add_argument("--limit", type=int, help="Run the first N selected cases")
    parser.add_argument("--dry-run", action="store_true", help="List selected cases without running the agent")
    parser.add_argument("--with-judge", action="store_true", help="Enable optional LLM-as-judge quality scoring")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between cases to reduce provider rate limits")
    parser.add_argument("--retries", type=int, default=0, help="Retry failed transient provider/quota cases")
    parser.add_argument("--retry-delay", type=float, default=30.0, help="Delay between transient retries")
    parser.add_argument(
        "--answer-only",
        action="store_true",
        help="Force each expected route to reduce routing calls; skips route scoring and evaluates answer quality.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for reports")
    parser.add_argument(
        "--replay",
        type=str,
        help="Rescore stored responses from a prior JSON report path, or 'latest'. Makes no agent calls.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    args = parser.parse_args()

    cases = select_cases(load_cases(args.cases), args.ids, args.limit)
    if args.dry_run:
        for case in cases:
            print(f"{case['id']}: {case['question']} [{case.get('expected_route', 'any')}]")
        return 0

    if args.replay:
        try:
            replay_path = resolve_replay_path(args.replay, args.output)
        except FileNotFoundError as exc:
            print(f"Replay error: {exc}", file=sys.stderr)
            return 2
        report = replay_golden_eval(
            cases,
            replay_path,
            with_judge=args.with_judge,
            answer_only=args.answer_only,
        )
    else:
        report = run_golden_eval(
            cases,
            with_judge=args.with_judge,
            delay_s=args.delay,
            retries=args.retries,
            retry_delay_s=args.retry_delay,
            answer_only=args.answer_only,
        )
    json_path, md_path = write_reports(report, args.output)
    trend_path = append_trend(report, json_path, md_path, args.output)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(build_markdown_report(report))
        print(f"Report: {md_path}")
        print(f"JSON: {json_path}")
        print(f"Trend: {trend_path}")

    return 1 if report["meta"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
