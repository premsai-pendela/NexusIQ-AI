"""
Local JSON tracing for NexusIQ-AI.

This is intentionally lightweight: it records what happened during a query
without calling extra LLMs or uploading data to an external service.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from observability.langfuse_adapter import get_langfuse_observer

logger = logging.getLogger(__name__)


def _send_to_cloudwatch(trace_data: Dict[str, Any]) -> None:
    if os.environ.get("ENVIRONMENT") != "production":
        return
    try:
        import boto3
        client = boto3.client("logs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        log_group = "/nexusiq/traces"
        log_stream = datetime.now(UTC).strftime("%Y/%m/%d")
        try:
            client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
        except client.exceptions.ResourceAlreadyExistsException:
            pass
        client.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=[{
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(trace_data, default=str),
            }],
        )
    except Exception as e:
        logger.warning("CloudWatch trace upload failed: %s", e)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_DIR = ROOT / "traces"
DEFAULT_TRACE_INDEX_PATH = ROOT / "data" / "query_traces.jsonl"
TRACE_SCHEMA_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_enabled() -> bool:
    value = os.getenv("NEXUSIQ_TRACE_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _trace_dir() -> Path:
    return Path(os.getenv("NEXUSIQ_TRACE_DIR", str(DEFAULT_TRACE_DIR)))


def _trace_index_path() -> Path:
    return Path(os.getenv("NEXUSIQ_TRACE_INDEX_PATH", str(DEFAULT_TRACE_INDEX_PATH)))


def _include_previews() -> bool:
    value = os.getenv("NEXUSIQ_TRACE_INCLUDE_PREVIEWS", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _max_files() -> int:
    try:
        return max(0, int(os.getenv("NEXUSIQ_TRACE_MAX_FILES", "200")))
    except ValueError:
        return 200


def _redact(text: str) -> str:
    redactions = [
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,]+",
        r"postgresql://[^\s'\"]+",
        r"sk-[A-Za-z0-9_-]{12,}",
    ]
    redacted = text
    for pattern in redactions:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted


def _preview(value: Any, max_chars: int = 500) -> str:
    if not _include_previews():
        return "[preview disabled]"
    text = str(value or "")
    return _redact(text[:max_chars])


def _prune_old_traces(trace_dir: Path) -> None:
    max_files = _max_files()
    if max_files <= 0:
        return
    traces = sorted(trace_dir.glob("trace-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_trace in traces[max_files:]:
        try:
            old_trace.unlink()
        except OSError:
            pass


def _append_trace_index(trace_data: Dict[str, Any], trace_path: Path) -> None:
    index_path = _trace_index_path()
    final = trace_data.get("final") or {}
    row = {
        "started_at": trace_data.get("started_at"),
        "trace_id": trace_data.get("trace_id"),
        "trace_path": str(trace_path),
        "question": trace_data.get("question"),
        "source_type": final.get("source_type"),
        "duration_s": trace_data.get("duration_s"),
        "from_cache": final.get("from_cache"),
        "routing_model": final.get("routing_model"),
        "answer_models": final.get("answer_models"),
        "validation": final.get("validation"),
    }
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
    except OSError as exc:
        logger.warning("Trace index write failed: %s", exc)


def summarize_agent_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a compact, non-sensitive summary of an agent result."""
    if not result:
        return {"present": False}

    summary: Dict[str, Any] = {
        "present": True,
        "success": bool(result.get("success")),
        "source": result.get("source"),
        "time_s": result.get("time"),
    }
    if result.get("error"):
        summary["error"] = _preview(result.get("error"), 300)
    if result.get("model_used"):
        summary["model_used"] = result.get("model_used")
    if result.get("query"):
        summary["sql_query"] = result.get("query")
    if result.get("row_count") is not None:
        summary["row_count"] = result.get("row_count")
    if result.get("chunks_retrieved") is not None:
        summary["chunks_retrieved"] = result.get("chunks_retrieved")
    if result.get("category"):
        summary["category"] = result.get("category")
    if result.get("answer_mode"):
        summary["answer_mode"] = result.get("answer_mode")

    sources = result.get("sources") or []
    if sources:
        summary["sources"] = [
            {
                "filename": source.get("filename") or source.get("source") or source.get("title"),
                "page": source.get("page"),
            }
            for source in sources[:5]
            if isinstance(source, dict)
        ]

    raw_data = result.get("raw_data") or {}
    competitors = raw_data.get("competitors") or []
    if competitors:
        summary["competitor_count"] = len(competitors)
        summary["web_data_statuses"] = sorted({
            competitor.get("data_status", "unknown")
            for competitor in competitors
            if isinstance(competitor, dict)
        })
        summary["sample_data"] = any(
            competitor.get("is_mock") or competitor.get("data_status") == "sample"
            for competitor in competitors
            if isinstance(competitor, dict)
        )

    answer = result.get("answer")
    if answer:
        summary["answer_preview"] = _preview(answer)

    return summary


class TraceSession:
    def __init__(self, question: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.enabled = _is_enabled()
        self.trace_id = uuid.uuid4().hex[:16]
        self.started_at = _utc_now()
        self._start_time = time.time()
        self._lock = threading.Lock()
        self.path: Optional[Path] = None
        self.data: Dict[str, Any] = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "trace_id": self.trace_id,
            "service": "nexusiq-ai",
            "trace_type": "fusion_query",
            "started_at": self.started_at,
            "ended_at": None,
            "duration_s": None,
            "question": question,
            "metadata": metadata or {},
            "spans": [],
            "final": {},
        }

    @contextmanager
    def span(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        started = time.time()
        span_data: Dict[str, Any] = {
            "span_id": uuid.uuid4().hex[:8],
            "name": name,
            "started_at": _utc_now(),
            "ended_at": None,
            "duration_s": None,
            "status": "ok",
            "metadata": metadata or {},
            "error": None,
        }
        try:
            yield span_data
        except Exception as exc:
            span_data["status"] = "error"
            span_data["error"] = _preview(exc, 500)
            raise
        finally:
            span_data["ended_at"] = _utc_now()
            span_data["duration_s"] = round(time.time() - started, 3)
            self.add_span(span_data)

    def add_span(self, span_data: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        with self._lock:
            self.data["spans"].append(span_data)

    def record_event(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        self.add_span(
            {
                "name": name,
                "started_at": _utc_now(),
                "ended_at": _utc_now(),
                "duration_s": 0,
                "status": "ok",
                "metadata": metadata or {},
                "error": None,
            }
        )

    def finish(self, final: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        if not self.enabled:
            return None
        self.data["ended_at"] = _utc_now()
        self.data["duration_s"] = round(time.time() - self._start_time, 3)
        self.data["final"] = final or {}

        trace_dir = _trace_dir()
        trace_dir.mkdir(parents=True, exist_ok=True)
        _prune_old_traces(trace_dir)
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        self.path = trace_dir / f"trace-{timestamp}-{self.trace_id}.json"
        langfuse_observer = get_langfuse_observer()
        langfuse_url = langfuse_observer.record_trace_summary(self.data)
        if langfuse_url:
            self.data["langfuse_url"] = langfuse_url
        langfuse_observer.flush()
        self.path.write_text(json.dumps(self.data, indent=2, default=str))
        _append_trace_index(self.data, self.path)
        _send_to_cloudwatch(self.data)
        return self.path


class LocalTracer:
    def start_trace(self, question: str, metadata: Optional[Dict[str, Any]] = None) -> TraceSession:
        return TraceSession(question, metadata)


_tracer = LocalTracer()


def get_tracer() -> LocalTracer:
    return _tracer
