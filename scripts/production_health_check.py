#!/usr/bin/env python3
"""Check NexusIQ production health from local, CI, or EC2."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _get_json(base_url: str, path: str, api_key: str | None = None) -> dict:
    url = base_url.rstrip("/") + path
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if api_key:
        request.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NexusIQ production health checks.")
    parser.add_argument("--base-url", default=os.getenv("NEXUSIQ_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("NEXUSIQ_API_KEY"))
    parser.add_argument("--min-chunks", type=int, default=int(os.getenv("NEXUSIQ_MIN_CHUNKS", "1")))
    args = parser.parse_args()

    try:
        health = _get_json(args.base_url, "/api/v1/health", args.api_key)
        agents = _get_json(args.base_url, "/api/v1/agents/status", args.api_key)
        metrics = _get_json(args.base_url, "/api/v1/metrics", args.api_key)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _fail(f"HTTP {exc.code}: {body[:500]}")
    except Exception as exc:
        _fail(str(exc))

    if health.get("status") != "healthy":
        _fail(f"health status is {health.get('status')}: {health.get('agents')}")

    for name, value in (health.get("agents") or {}).items():
        if value != "online":
            _fail(f"agent {name} is not online: {value}")

    chunks = int(health.get("chroma_chunks", -1))
    if chunks < args.min_chunks:
        _fail(f"chroma chunk count too low: {chunks}")

    features = health.get("production_features") or {}
    for feature in ("production_harness", "langgraph", "trace_enabled", "llm_ledger_enabled"):
        if features.get(feature) is not True:
            _fail(f"{feature} is not enabled: {features.get(feature)}")

    print("OK: production health check passed")
    print(json.dumps(
        {
            "base_url": args.base_url,
            "status": health.get("status"),
            "agents": health.get("agents"),
            "production_features": features,
            "chroma_chunks": chunks,
            "cache_entries": health.get("cache_entries"),
            "metrics_chroma_chunks": metrics.get("chroma_chunk_count"),
            "agent_status": agents,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
