"""
NexusIQ AI - LLM Gateway

Centralizes model invocation so agents can share fallback, quota, tracing, and
usage-ledger behavior instead of each agent hand-rolling provider calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, Optional

from config.settings import settings
from observability.langfuse_adapter import get_langfuse_observer

logger = logging.getLogger(__name__)


DEFAULT_LEDGER_PATH = Path(__file__).parent.parent / "data" / "llm_task_ledger.jsonl"
_llm_call_context: ContextVar[Dict[str, Any]] = ContextVar("llm_call_context", default={})


class LLMResponseValidationError(ValueError):
    """The provider responded, but the content is unusable for this task."""


def _estimate_tokens(text: Any) -> int:
    """Cheap provider-agnostic token estimate for cost/usage monitoring."""
    if text is None:
        return 0
    return max(1, int(len(str(text)) / 4))


def _response_text(response: Any) -> str:
    """Normalize LangChain-style responses and plain strings."""
    content = getattr(response, "content", response)
    return str(content).strip()


def _normalize_token_usage(raw_usage: Any) -> Optional[Dict[str, Any]]:
    """Normalize provider/LangChain token usage metadata when available."""
    if not isinstance(raw_usage, dict):
        return None

    input_tokens = (
        raw_usage.get("input_tokens")
        or raw_usage.get("prompt_tokens")
        or raw_usage.get("input_token_count")
        or raw_usage.get("prompt_token_count")
    )
    output_tokens = (
        raw_usage.get("output_tokens")
        or raw_usage.get("completion_tokens")
        or raw_usage.get("output_token_count")
        or raw_usage.get("candidates_token_count")
    )
    total_tokens = (
        raw_usage.get("total_tokens")
        or raw_usage.get("total_token_count")
        or raw_usage.get("total_tokens_count")
    )

    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    return {
        "input_tokens_actual": input_tokens,
        "output_tokens_actual": output_tokens,
        "total_tokens_actual": total_tokens,
    }


def _extract_actual_token_usage(response: Any) -> Dict[str, Any]:
    """
    Extract provider-reported token usage from LangChain responses.

    Gemini, Groq, OpenAI-compatible, and Vertex wrappers expose usage in
    slightly different places, so this checks the common response surfaces.
    """
    candidates = []
    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata:
        candidates.append(("usage_metadata", usage_metadata))

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for key in ("token_usage", "usage", "usage_metadata"):
            if response_metadata.get(key):
                candidates.append((f"response_metadata.{key}", response_metadata[key]))

    raw = getattr(response, "raw", None)
    if isinstance(raw, dict):
        for key in ("usage", "usage_metadata"):
            if raw.get(key):
                candidates.append((f"raw.{key}", raw[key]))

    for source, usage in candidates:
        normalized = _normalize_token_usage(usage)
        if normalized:
            normalized["actual_token_source"] = source
            normalized["actual_tokens_available"] = True
            return normalized

    return {
        "input_tokens_actual": None,
        "output_tokens_actual": None,
        "total_tokens_actual": None,
        "actual_token_source": None,
        "actual_tokens_available": False,
    }


@contextmanager
def llm_call_context(**context: Any) -> Iterator[None]:
    """Attach query/trace context to every LLM ledger row in this call stack."""
    previous = _llm_call_context.get().copy()
    merged = {**previous, **{key: value for key, value in context.items() if value is not None}}
    token = _llm_call_context.set(merged)
    try:
        yield
    finally:
        _llm_call_context.reset(token)


def _error_status(error_message: str) -> str:
    """Map provider errors to the legacy status labels used by the UI."""
    lower = error_message.lower()
    if "429" in error_message or "quota" in lower or "resource_exhausted" in lower:
        return "❌ QUOTA EXCEEDED"
    if "404" in error_message or "not found" in lower:
        return "❌ MODEL NOT FOUND"
    if "connection" in lower or "timeout" in lower or "deadline_exceeded" in lower:
        return "❌ CONNECTION ERROR"
    return "❌ FAILED"


class LLMGateway:
    """Shared entry point for monitored LLM calls."""

    def __init__(
        self,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
        client_factory: Optional[Callable[[Dict[str, Any], float], Any]] = None,
    ):
        self.ledger_path = ledger_path
        self.client_factory = client_factory or self._create_client

    def _ledger_enabled(self) -> bool:
        return os.getenv("NEXUSIQ_LLM_LEDGER_ENABLED", "1") != "0"

    def _record_attempt(self, event: Dict[str, Any]) -> None:
        """Append one LLM task attempt without storing prompt contents."""
        context = _llm_call_context.get()
        trace = context.get("trace")
        safe_context = {key: value for key, value in context.items() if key != "trace"}
        if safe_context:
            event.update(safe_context)
            event["query_context"] = safe_context
            event["metadata"] = {**safe_context, **(event.get("metadata") or {})}

        if trace is not None:
            try:
                trace.record_event(
                    "llm.call",
                    {
                        key: value
                        for key, value in event.items()
                        if key not in {"error"}
                    },
                )
            except Exception as exc:
                logger.warning("Could not attach LLM event to trace: %s", exc)

        self._write_ledger_row(event)

    def _write_ledger_row(self, event: Dict[str, Any]) -> None:
        """Append one event row to the local JSONL ledger."""
        event.setdefault(
            "measurement_profile",
            os.getenv("NEXUSIQ_MEASUREMENT_PROFILE", "foundation_before_call_disabling"),
        )
        if not self._ledger_enabled():
            return

        path = Path(os.getenv("NEXUSIQ_LLM_LEDGER_PATH", str(self.ledger_path)))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, default=str) + "\n")
        except Exception as exc:
            logger.warning("Could not write LLM task ledger event: %s", exc)

    def record_avoided_call(
        self,
        *,
        task: str,
        reason: str,
        prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an LLM call replaced by deterministic logic.

        Savings accounting is conservative: only the prompt tokens that were
        never sent are counted; the unsent completion is not estimated.
        """
        tokens_avoided = _estimate_tokens(prompt) if prompt else 0
        context = _llm_call_context.get()
        trace = context.get("trace")
        safe_context = {key: value for key, value in context.items() if key != "trace"}

        if trace is not None:
            try:
                trace.record_event(
                    "llm.call_skipped",
                    {
                        "task": task,
                        "reason": reason,
                        "estimated_tokens_avoided": tokens_avoided,
                        **(metadata or {}),
                    },
                )
            except Exception as exc:
                logger.warning("Could not attach avoided-call event to trace: %s", exc)

        event = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "invocation_id": uuid.uuid4().hex[:16],
            "task": task,
            "model": "deterministic",
            "model_type": None,
            "temperature": None,
            "status": "avoided",
            "failure_kind": None,
            "skip_reason": reason,
            "error": None,
            "latency_s": 0.0,
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16] if prompt else None,
            "input_tokens_estimate": 0,
            "output_tokens_estimate": 0,
            "total_tokens_estimate": 0,
            "tokens_avoided_estimate": tokens_avoided,
            "input_tokens_actual": None,
            "output_tokens_actual": None,
            "total_tokens_actual": None,
            "actual_token_source": None,
            "actual_tokens_available": False,
            "metadata": {**safe_context, **(metadata or {})},
        }
        if safe_context:
            event.update(safe_context)
            event["query_context"] = safe_context
        self._write_ledger_row(event)
        logger.info("🧮 Avoided LLM call for %s (%s): ~%s prompt tokens not sent", task, reason, tokens_avoided)

    def _create_client(self, model_config: Dict[str, Any], temperature: float) -> Any:
        """Create a LangChain chat client from a NexusIQ model config."""
        model_type = model_config["type"]
        model_name = model_config["name"]

        if model_type == "gemini":
            if not settings.google_api_key:
                raise RuntimeError("Gemini API key not configured")

            from langchain_google_genai import ChatGoogleGenerativeAI

            if "pro" in model_name.lower():
                max_retries = settings.gemini_pro_max_retries
                timeout = settings.gemini_pro_timeout
            else:
                max_retries = settings.gemini_flash_max_retries
                timeout = settings.gemini_flash_timeout

            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.google_api_key,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout,
            )

        if model_type == "groq":
            if not settings.groq_api_key:
                raise RuntimeError("Groq API key not configured")

            from langchain_groq import ChatGroq

            return ChatGroq(
                model=model_name,
                groq_api_key=settings.groq_api_key,
                temperature=temperature,
            )

        if model_type == "vertex":
            import google.auth
            from langchain_google_genai import ChatGoogleGenerativeAI

            credentials, _ = google.auth.default()
            return ChatGoogleGenerativeAI(
                model=model_name,
                credentials=credentials,
                temperature=temperature,
            )

        if model_type == "ollama":
            import ollama

            class OllamaClient:
                def invoke(self, prompt: str) -> str:
                    response = ollama.chat(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={"temperature": temperature},
                    )
                    return response["message"]["content"]

            return OllamaClient()

        raise RuntimeError(f"Unknown model type: {model_type}")

    def invoke_with_fallback(
        self,
        *,
        prompt: str,
        models: Iterable[Dict[str, Any]],
        tracker: Any,
        task: str,
        temperature: float = 0.1,
        metadata: Optional[Dict[str, Any]] = None,
        response_validator: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke the first available model that succeeds.

        Returns the same shape SQLAgent already expects while also writing a
        no-prompt usage ledger for monitoring.
        """
        models_tried = []
        invocation_id = uuid.uuid4().hex[:16]
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        prompt_tokens = _estimate_tokens(prompt)

        for model_config in models:
            model_name = model_config["name"]
            started_at = datetime.now(timezone.utc).isoformat()
            model_start = time.time()

            is_available, skip_reason = tracker.is_available(model_name)
            if not is_available:
                token_usage = {
                    "input_tokens_actual": None,
                    "output_tokens_actual": None,
                    "total_tokens_actual": None,
                    "actual_token_source": None,
                    "actual_tokens_available": False,
                }
                attempt = {
                    "model": model_name,
                    "description": model_config.get("description", model_name),
                    "status": "⏭️ SKIPPED",
                    "error": skip_reason,
                    "time": 0.0,
                    "task": task,
                }
                models_tried.append(attempt)
                self._record_attempt({
                    "started_at": started_at,
                    "invocation_id": invocation_id,
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "skipped",
                    "failure_kind": None,
                    "skip_reason": skip_reason,
                    "error": skip_reason,
                    "latency_s": 0.0,
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": 0,
                    "total_tokens_estimate": prompt_tokens,
                    **token_usage,
                    "metadata": metadata or {},
                })
                logger.info("⏭️ Skipping %s: %s", model_name, skip_reason)
                continue

            observer = get_langfuse_observer()
            generation = None
            try:
                logger.info("🔄 Trying %s...", model_config.get("description", model_name))
                client = self.client_factory(model_config, temperature)
                with observer.generation_context(
                    task=task,
                    model=model_name,
                    model_type=model_config.get("type"),
                    metadata=metadata or {},
                    input_summary={
                        "prompt_hash": prompt_hash,
                        "input_tokens_estimate": prompt_tokens,
                    },
                ) as generation:
                    response = client.invoke(prompt)
                    content = _response_text(response)
                if response_validator is not None and not response_validator(content):
                    raise LLMResponseValidationError("LLM response did not pass task validation")
                elapsed = time.time() - model_start
                output_tokens = _estimate_tokens(content)
                actual_usage = _extract_actual_token_usage(response)
                output_summary = {
                    "output_tokens_estimate": output_tokens,
                    "total_tokens_estimate": prompt_tokens + output_tokens,
                    **actual_usage,
                }
                observer.update_generation(
                    generation,
                    status="success",
                    output_summary=output_summary,
                    metadata={"status": "success"},
                )

                tracker.report_success(model_name)
                attempt = {
                    "model": model_name,
                    "description": model_config.get("description", model_name),
                    "status": "✅ SUCCESS",
                    "error": None,
                    "time": round(elapsed, 2),
                    "task": task,
                }
                models_tried.append(attempt)

                self._record_attempt({
                    "started_at": started_at,
                    "invocation_id": invocation_id,
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "success",
                    "failure_kind": None,
                    "error": None,
                    "latency_s": round(elapsed, 3),
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": output_tokens,
                    "total_tokens_estimate": prompt_tokens + output_tokens,
                    **actual_usage,
                    "metadata": metadata or {},
                })
                logger.info("✅ Success with %s in %.2fs", model_name, elapsed)

                return {
                    "success": True,
                    "response": content,
                    "model_used": model_config.get("description", model_name),
                    "models_tried": models_tried,
                }

            except Exception as exc:
                elapsed = time.time() - model_start
                error_msg = str(exc)
                if isinstance(exc, LLMResponseValidationError):
                    status = "❌ INVALID RESPONSE"
                    failure_kind = "invalid_response"
                else:
                    tracker.report_failure(model_name, error_msg)
                    status = _error_status(error_msg)
                    failure_kind = "provider_failure"

                attempt = {
                    "model": model_name,
                    "description": model_config.get("description", model_name),
                    "status": status,
                    "error": error_msg[:150],
                    "time": round(elapsed, 2),
                    "task": task,
                }
                models_tried.append(attempt)
                observer.update_generation(
                    generation,
                    status="failed",
                    output_summary={
                        "output_tokens_estimate": 0,
                        "total_tokens_estimate": prompt_tokens,
                    },
                    metadata={
                        "status": "failed",
                        "failure_kind": failure_kind,
                    },
                    error=error_msg,
                )
                self._record_attempt({
                    "started_at": started_at,
                    "invocation_id": invocation_id,
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "failed",
                    "failure_kind": failure_kind,
                    "error": error_msg[:300],
                    "latency_s": round(elapsed, 3),
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": 0,
                    "total_tokens_estimate": prompt_tokens,
                    "input_tokens_actual": None,
                    "output_tokens_actual": None,
                    "total_tokens_actual": None,
                    "actual_token_source": None,
                    "actual_tokens_available": False,
                    "metadata": metadata or {},
                })
                logger.warning("%s %s: %s", status, model_name, error_msg[:100])

        return {
            "success": False,
            "response": None,
            "model_used": None,
            "models_tried": models_tried,
            "error": "All LLM models failed",
        }


_gateway_instance: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """Get the shared LLM gateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
