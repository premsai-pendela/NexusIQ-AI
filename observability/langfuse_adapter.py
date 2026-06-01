"""
Optional Langfuse integration for NexusIQ observability.

NexusIQ's local traces and LLM ledger remain the source of truth. This adapter
mirrors safe, compact metadata to Langfuse only when explicitly configured.
Raw prompts are not sent by default.
"""

from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _truthy_env(name: str, default: str = "0") -> bool:
    return _config_value(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _credentials_present() -> bool:
    return bool(_config_value("LANGFUSE_PUBLIC_KEY") and _config_value("LANGFUSE_SECRET_KEY"))


def _config_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        from config.settings import settings

        value = getattr(settings, name.lower(), default)
    except Exception:
        value = default
    return str(value or default)


def _ensure_langfuse_env() -> None:
    for name in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_HOST",
    ):
        value = _config_value(name)
        if value and not os.getenv(name):
            os.environ[name] = value

    if os.getenv("LANGFUSE_HOST") and not os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST", "")


class LangfuseObserver:
    """Small wrapper around the Langfuse SDK with fail-closed behavior."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client
        self._client_loaded = client is not None

    def enabled(self) -> bool:
        if not _truthy_env("NEXUSIQ_LANGFUSE_ENABLED", "1"):
            return False
        if not _credentials_present() and self._client is None:
            return False
        return self.client is not None

    @property
    def client(self) -> Optional[Any]:
        if self._client_loaded:
            return self._client
        self._client_loaded = True
        try:
            _ensure_langfuse_env()
            from langfuse import get_client

            self._client = get_client()
        except Exception as exc:
            logger.warning("Langfuse client unavailable: %s", exc)
            self._client = None
        return self._client

    def generation_context(
        self,
        *,
        task: str,
        model: str,
        model_type: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        input_summary: Optional[Dict[str, Any]] = None,
    ):
        if not self.enabled():
            return nullcontext(None)

        client = self.client
        if client is None:
            return nullcontext(None)

        safe_metadata = {
            "service": "nexusiq-ai",
            "task": task,
            "model_type": model_type,
        }
        if metadata:
            safe_metadata.update(metadata)

        try:
            return client.start_as_current_observation(
                as_type="generation",
                name=task,
                model=model,
                input=input_summary or {},
                metadata=safe_metadata,
            )
        except TypeError:
            # Older SDK variants may not accept every keyword. Keep the app alive.
            return client.start_as_current_observation(
                as_type="generation",
                name=task,
                model=model,
            )
        except Exception as exc:
            logger.warning("Langfuse generation context failed: %s", exc)
            return nullcontext(None)

    def update_generation(
        self,
        generation: Any,
        *,
        status: str,
        output_summary: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        if generation is None:
            return
        payload: Dict[str, Any] = {
            "output": output_summary or {},
            "metadata": metadata or {},
        }
        if error:
            payload["level"] = "ERROR"
            payload["status_message"] = error[:300]
        elif status == "skipped":
            payload["level"] = "WARNING"
            payload["status_message"] = "Model skipped by quota tracker"
        try:
            generation.update(**payload)
        except Exception as exc:
            logger.warning("Langfuse generation update failed: %s", exc)

    def record_trace_summary(self, trace_data: Dict[str, Any]) -> Optional[str]:
        if not self.enabled():
            return None
        client = self.client
        if client is None:
            return None

        metadata = trace_data.get("metadata") or {}
        final = trace_data.get("final") or {}
        input_summary = {
            "question": trace_data.get("question"),
            "local_trace_id": trace_data.get("trace_id"),
            "orchestrator": metadata.get("orchestrator"),
        }
        output_summary = {
            "source_type": final.get("source_type"),
            "duration_s": trace_data.get("duration_s"),
            "from_cache": final.get("from_cache"),
            "validation": final.get("validation"),
        }

        try:
            trace_context = None
            if hasattr(client, "create_trace_id") and trace_data.get("trace_id"):
                trace_context = {"trace_id": client.create_trace_id(seed=str(trace_data["trace_id"]))}
            kwargs = {
                "as_type": "agent",
                "name": "nexusiq.fusion_query",
                "input": input_summary,
                "metadata": {
                    "service": "nexusiq-ai",
                    "local_trace_id": trace_data.get("trace_id"),
                    "trace_type": trace_data.get("trace_type"),
                    "span_count": len(trace_data.get("spans") or []),
                    **metadata,
                },
            }
            if trace_context:
                kwargs["trace_context"] = trace_context
            with client.start_as_current_observation(**kwargs) as observation:
                observation.update(output=output_summary)
                if final.get("source_type") == "error":
                    observation.update(level="ERROR", status_message=str(final.get("error") or "error")[:300])
            if hasattr(client, "get_trace_url") and trace_context:
                return client.get_trace_url(trace_id=trace_context["trace_id"])
        except Exception as exc:
            logger.warning("Langfuse trace summary failed: %s", exc)
        return None

    def flush(self) -> None:
        if not self.enabled():
            return
        client = self.client
        if client is None or not hasattr(client, "flush"):
            return
        try:
            client.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)


_observer = LangfuseObserver()


def get_langfuse_observer() -> LangfuseObserver:
    return _observer
