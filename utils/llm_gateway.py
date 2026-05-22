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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


DEFAULT_LEDGER_PATH = Path("data/llm_task_ledger.jsonl")


def _estimate_tokens(text: Any) -> int:
    """Cheap provider-agnostic token estimate for cost/usage monitoring."""
    if text is None:
        return 0
    return max(1, int(len(str(text)) / 4))


def _response_text(response: Any) -> str:
    """Normalize LangChain-style responses and plain strings."""
    content = getattr(response, "content", response)
    return str(content).strip()


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
        if not self._ledger_enabled():
            return

        path = Path(os.getenv("NEXUSIQ_LLM_LEDGER_PATH", str(self.ledger_path)))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, default=str) + "\n")
        except Exception as exc:
            logger.warning("Could not write LLM task ledger event: %s", exc)

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
            from langchain_ollama import ChatOllama

            return ChatOllama(model=model_name, temperature=temperature)

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
    ) -> Dict[str, Any]:
        """
        Invoke the first available model that succeeds.

        Returns the same shape SQLAgent already expects while also writing a
        no-prompt usage ledger for monitoring.
        """
        models_tried = []
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        prompt_tokens = _estimate_tokens(prompt)

        for model_config in models:
            model_name = model_config["name"]
            started_at = datetime.now(timezone.utc).isoformat()
            model_start = time.time()

            is_available, skip_reason = tracker.is_available(model_name)
            if not is_available:
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
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "skipped",
                    "error": skip_reason,
                    "latency_s": 0.0,
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": 0,
                    "total_tokens_estimate": prompt_tokens,
                    "metadata": metadata or {},
                })
                logger.info("⏭️ Skipping %s: %s", model_name, skip_reason)
                continue

            try:
                logger.info("🔄 Trying %s...", model_config.get("description", model_name))
                client = self.client_factory(model_config, temperature)
                response = client.invoke(prompt)
                content = _response_text(response)
                elapsed = time.time() - model_start

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

                output_tokens = _estimate_tokens(content)
                self._record_attempt({
                    "started_at": started_at,
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "success",
                    "error": None,
                    "latency_s": round(elapsed, 3),
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": output_tokens,
                    "total_tokens_estimate": prompt_tokens + output_tokens,
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
                tracker.report_failure(model_name, error_msg)
                status = _error_status(error_msg)

                attempt = {
                    "model": model_name,
                    "description": model_config.get("description", model_name),
                    "status": status,
                    "error": error_msg[:150],
                    "time": round(elapsed, 2),
                    "task": task,
                }
                models_tried.append(attempt)
                self._record_attempt({
                    "started_at": started_at,
                    "task": task,
                    "model": model_name,
                    "model_type": model_config.get("type"),
                    "temperature": temperature,
                    "status": "failed",
                    "error": error_msg[:300],
                    "latency_s": round(elapsed, 3),
                    "prompt_hash": prompt_hash,
                    "input_tokens_estimate": prompt_tokens,
                    "output_tokens_estimate": 0,
                    "total_tokens_estimate": prompt_tokens,
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
