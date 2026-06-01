#!/usr/bin/env python3
"""Run one real NexusIQ production query and verify trace metadata."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_QUESTION = "Validate Q4 Electronics revenue across SQL and PDF reports."


def _post_json(base_url: str, path: str, payload: dict, api_key: str | None = None) -> dict:
    url = base_url.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    if api_key:
        request.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a NexusIQ production smoke query.")
    parser.add_argument("--base-url", default=os.getenv("NEXUSIQ_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("NEXUSIQ_API_KEY"))
    parser.add_argument("--question", default=os.getenv("NEXUSIQ_SMOKE_QUESTION", DEFAULT_QUESTION))
    parser.add_argument("--source", default=os.getenv("NEXUSIQ_SMOKE_SOURCE", "auto"))
    args = parser.parse_args()

    try:
        result = _post_json(
            args.base_url,
            "/api/v1/query",
            {"question": args.question, "source": args.source},
            args.api_key,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _fail(f"HTTP {exc.code}: {body[:500]}")
    except Exception as exc:
        _fail(str(exc))

    answer = str(result.get("answer") or "").strip()
    route = result.get("route")
    trace_id = result.get("trace_id")

    if not answer:
        _fail("empty answer")
    if route in {"unknown", "error", None}:
        _fail(f"bad route: {route}")
    if not trace_id:
        _fail("missing trace_id")
    if "error" in answer.lower() and len(answer) < 160:
        _fail(f"answer looks like an error: {answer}")

    print("OK: production smoke query passed")
    print(json.dumps(
        {
            "base_url": args.base_url,
            "question": args.question,
            "route": route,
            "confidence": result.get("confidence"),
            "trace_id": trace_id,
            "latency_ms": result.get("latency_ms"),
            "cached": result.get("cached"),
            "answer_preview": answer[:300],
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
