"""Inspect local NexusIQ trace files from the command line."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from observability.tracer import DEFAULT_TRACE_DIR


SLOW_SPAN_SECONDS = 3.0


def _load_trace(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def list_traces(trace_dir: Path, limit: int) -> List[Path]:
    return sorted(trace_dir.glob("trace-*.json"), reverse=True)[:limit]


def format_trace_summary(trace: Dict[str, Any], path: Path) -> str:
    final = trace.get("final") or {}
    spans = trace.get("spans", [])
    slowest = max(spans, key=lambda span: span.get("duration_s") or 0, default=None)
    lines = [
        f"Trace: {trace.get('trace_id')} ({path})",
        f"Question: {trace.get('question')}",
        f"Route: {final.get('source_type')}",
        f"Duration: {trace.get('duration_s')}s",
        f"Routing model: {final.get('routing_model') or 'n/a'}",
        f"Validation: {(final.get('validation') or {}).get('confidence') or 'n/a'}",
        f"From cache: {final.get('from_cache')}",
        f"Slowest span: {slowest.get('name')} ({slowest.get('duration_s')}s)" if slowest else "Slowest span: n/a",
        "Spans:",
    ]
    for span in spans:
        status = span.get("status", "ok")
        duration = span.get("duration_s", 0)
        slow_marker = " ⚠️ slow" if duration and duration > SLOW_SPAN_SECONDS else ""
        lines.append(f"- {span.get('name')} [{status}] {duration}s{slow_marker}")
        error = span.get("error")
        if error:
            lines.append(f"  error: {error}")
    return "\n".join(lines)


def get_trace_diagnostics(trace: Dict[str, Any], slow_threshold: float = SLOW_SPAN_SECONDS) -> Dict[str, Any]:
    spans = trace.get("spans", [])
    slowest = max(spans, key=lambda span: span.get("duration_s") or 0, default=None)
    slow_spans = [
        span for span in spans
        if (span.get("duration_s") or 0) > slow_threshold
    ]
    error_spans = [
        span for span in spans
        if span.get("status") == "error" or span.get("error")
    ]
    return {
        "slowest_span": slowest,
        "slow_spans": slow_spans,
        "error_spans": error_spans,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local NexusIQ observability traces")
    parser.add_argument("--dir", type=Path, default=DEFAULT_TRACE_DIR, help="Trace directory")
    parser.add_argument("--latest", action="store_true", help="Show the newest trace")
    parser.add_argument("--list", action="store_true", help="List recent traces")
    parser.add_argument("--limit", type=int, default=10, help="Number of traces to list")
    parser.add_argument("--file", type=Path, help="Inspect a specific trace JSON file")
    parser.add_argument("--json", action="store_true", help="Print raw JSON for inspected trace")
    args = parser.parse_args()

    if args.file:
        path = args.file
    else:
        traces = list_traces(args.dir, args.limit)
        if args.list and not args.latest:
            if not traces:
                print(f"No traces found in {args.dir}")
                return 1
            for trace_path in traces:
                trace = _load_trace(trace_path)
                final = trace.get("final") or {}
                print(
                    f"{trace.get('started_at')}  {trace.get('trace_id')}  "
                    f"{final.get('source_type')}  {trace.get('duration_s')}s  {trace_path}"
                )
            return 0
        if not traces:
            print(f"No traces found in {args.dir}")
            return 1
        path = traces[0]

    trace = _load_trace(path)
    if args.json:
        print(json.dumps(trace, indent=2, default=str))
    else:
        print(format_trace_summary(trace, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
