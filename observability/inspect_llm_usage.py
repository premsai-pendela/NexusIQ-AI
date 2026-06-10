"""Summarize local LLM task ledger usage and reliability signals."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_LEDGER_PATH = Path("data/llm_task_ledger.jsonl")
DEFAULT_TRACE_INDEX_PATH = Path("data/query_traces.jsonl")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load valid JSON objects from a JSONL file, ignoring blank lines."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _is_invalid_response(event: Dict[str, Any]) -> bool:
    if event.get("failure_kind") == "invalid_response":
        return True
    return "task validation" in str(event.get("error") or "").lower()


def _aggregate(events: List[Dict[str, Any]], key_name: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get(key_name) or "unknown")].append(event)

    rows = []
    for name, group in grouped.items():
        latencies = [event.get("latency_s", 0) or 0 for event in group]
        rows.append({
            key_name: name,
            "attempts": len(group),
            "successes": sum(event.get("status") == "success" for event in group),
            "invalid_responses": sum(_is_invalid_response(event) for event in group),
            "failed": sum(event.get("status") == "failed" for event in group),
            "skipped": sum(event.get("status") == "skipped" for event in group),
            "avoided": sum(event.get("status") == "avoided" for event in group),
            "tokens_avoided": sum(event.get("tokens_avoided_estimate", 0) or 0 for event in group),
            "tokens": sum(event.get("total_tokens_estimate", 0) or 0 for event in group),
            "input_tokens": sum(event.get("input_tokens_estimate", 0) or 0 for event in group),
            "output_tokens": sum(event.get("output_tokens_estimate", 0) or 0 for event in group),
            "actual_tokens": sum(event.get("total_tokens_actual", 0) or 0 for event in group),
            "actual_input_tokens": sum(event.get("input_tokens_actual", 0) or 0 for event in group),
            "actual_output_tokens": sum(event.get("output_tokens_actual", 0) or 0 for event in group),
            "actual_token_events": sum(bool(event.get("actual_tokens_available")) for event in group),
            "average_latency_s": sum(latencies) / len(latencies),
            "p95_latency_s": _percentile(latencies, 0.95),
        })
    return sorted(rows, key=lambda row: (-row["tokens"], row[key_name]))


def summarize_usage(
    events: List[Dict[str, Any]],
    trace_index: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Create task/model metrics without requiring prompt contents."""
    traces = trace_index or []
    statuses = Counter(str(event.get("status") or "unknown") for event in events)
    invocations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ungrouped_attempts = 0
    for event in events:
        invocation_id = event.get("invocation_id")
        if invocation_id:
            invocations[str(invocation_id)].append(event)
        else:
            ungrouped_attempts += 1

    fallback_count = 0
    for attempts in invocations.values():
        if len(attempts) > 1 and any(event.get("status") == "success" for event in attempts):
            successful_index = next(
                index for index, event in enumerate(attempts) if event.get("status") == "success"
            )
            if successful_index > 0:
                fallback_count += 1

    latencies = [event.get("latency_s", 0) or 0 for event in events]
    return {
        "attempts": len(events),
        "invocations_observed": len(invocations),
        "ungrouped_legacy_attempts": ungrouped_attempts,
        "successes": statuses["success"],
        "failed": statuses["failed"],
        "skipped": statuses["skipped"],
        "avoided": statuses["avoided"],
        "tokens_avoided": sum(event.get("tokens_avoided_estimate", 0) or 0 for event in events),
        "invalid_responses": sum(_is_invalid_response(event) for event in events),
        "fallback_invocations": fallback_count,
        "tokens": sum(event.get("total_tokens_estimate", 0) or 0 for event in events),
        "input_tokens": sum(event.get("input_tokens_estimate", 0) or 0 for event in events),
        "output_tokens": sum(event.get("output_tokens_estimate", 0) or 0 for event in events),
        "actual_tokens": sum(event.get("total_tokens_actual", 0) or 0 for event in events),
        "actual_input_tokens": sum(event.get("input_tokens_actual", 0) or 0 for event in events),
        "actual_output_tokens": sum(event.get("output_tokens_actual", 0) or 0 for event in events),
        "actual_token_events": sum(bool(event.get("actual_tokens_available")) for event in events),
        "average_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "p95_latency_s": _percentile(latencies, 0.95),
        "cache_hits_observed": sum(bool(trace.get("from_cache")) for trace in traces),
        "by_measurement_profile": _aggregate(events, "measurement_profile"),
        "by_task": _aggregate(events, "task"),
        "by_model": _aggregate(events, "model"),
        "highest_cost_attempts": sorted(
            events,
            key=lambda event: event.get("total_tokens_estimate", 0) or 0,
            reverse=True,
        )[:5],
    }


def _table(title: str, rows: List[Dict[str, Any]], key_name: str) -> List[str]:
    lines = [
        title,
        f"{key_name:<28} {'tries':>5} {'ok':>4} {'invalid':>7} {'tokens':>8} {'avg s':>7} {'p95 s':>7}",
    ]
    for row in rows:
        lines.append(
            f"{row[key_name]:<28} {row['attempts']:>5} {row['successes']:>4} "
            f"{row['invalid_responses']:>7} {row['tokens']:>8} "
            f"{row['average_latency_s']:>7.3f} {row['p95_latency_s']:>7.3f}"
        )
    return lines


def format_usage_report(summary: Dict[str, Any]) -> str:
    """Format metrics for a terminal-friendly local usage report."""
    lines = [
        "LLM Usage Report",
        (
            f"Attempts: {summary['attempts']} | Success: {summary['successes']} | "
            f"Failed: {summary['failed']} | Skipped: {summary['skipped']} | "
            f"Invalid responses: {summary['invalid_responses']}"
        ),
        (
            f"Avoided calls (deterministic paths): {summary['avoided']} | "
            f"Estimated prompt tokens not sent: {summary['tokens_avoided']}"
        ),
        (
            f"Estimated tokens: {summary['tokens']} "
            f"(input {summary['input_tokens']}, output {summary['output_tokens']}) | "
            f"Latency avg/p95: {summary['average_latency_s']:.3f}s/{summary['p95_latency_s']:.3f}s"
        ),
        (
            f"Provider actual tokens: {summary['actual_tokens']} "
            f"(input {summary['actual_input_tokens']}, output {summary['actual_output_tokens']}) | "
            f"actual-token events: {summary['actual_token_events']}"
        ),
        (
            f"Grouped fallback invocations: {summary['fallback_invocations']} | "
            f"Legacy attempts without invocation ID: {summary['ungrouped_legacy_attempts']}"
        ),
        (
            f"Cache hits observed in trace index: {summary['cache_hits_observed']} "
            "(token savings are not estimable until cache traces link to ledger invocations)"
        ),
        "",
    ]
    lines.extend(_table("By task", summary["by_task"], "task"))
    lines.append("")
    lines.extend(_table("By model", summary["by_model"], "model"))
    lines.append("")
    lines.extend(_table("By measurement profile", summary["by_measurement_profile"], "measurement_profile"))
    lines.extend(["", "Highest-cost attempts"])
    for event in summary["highest_cost_attempts"]:
        lines.append(
            f"- {event.get('task', 'unknown')} / {event.get('model', 'unknown')}: "
            f"{event.get('total_tokens_estimate', 0)} tokens, {event.get('latency_s', 0)}s"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect NexusIQ local LLM usage ledger")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH, help="LLM ledger JSONL path")
    parser.add_argument(
        "--trace-index",
        type=Path,
        default=DEFAULT_TRACE_INDEX_PATH,
        help="Optional compact trace index JSONL path for cache-hit counts",
    )
    parser.add_argument("--json", action="store_true", help="Print structured metrics as JSON")
    args = parser.parse_args()

    events = load_jsonl(args.ledger)
    if not events:
        print(f"No LLM ledger events found in {args.ledger}")
        return 1
    summary = summarize_usage(events, load_jsonl(args.trace_index))
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(format_usage_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
