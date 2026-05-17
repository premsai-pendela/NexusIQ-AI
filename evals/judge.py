"""
Optional LLM judge helpers for NexusIQ golden evals.

The golden eval runner is useful without this module. Rule-based checks provide
the primary score. The judge adds a secondary quality score for natural-language
answer quality when an API-backed LLM client is available.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from agents.rag_agent import get_rag_agent

logger = logging.getLogger(__name__)


JUDGE_SYSTEM_PROMPT = """You are a strict evaluator for a business intelligence AI system.
Grade only the provided answer against the question and rubric. Do not reward unsupported claims.
Return JSON only."""


def build_judge_prompt(case: Dict[str, Any], response: Dict[str, Any]) -> str:
    return f"""{JUDGE_SYSTEM_PROMPT}

Question:
{case.get("question")}

Expected behavior:
- Expected route: {case.get("expected_route")}
- Expected confidence: {case.get("expected_confidence", "not specified")}
- Required terms: {case.get("required_terms", [])}
- Forbidden terms: {case.get("forbidden_terms", [])}
- Expected numbers: {case.get("expected_numbers", [])}

Actual route:
{response.get("source_type")}

Actual validation:
{response.get("validation")}

Actual answer:
{response.get("answer", "")}

Rubric:
1. correctness: Is the answer factually aligned with expected facts?
2. completeness: Does it answer the full question?
3. groundedness: Does it stay grounded in the available SQL/RAG/Web evidence?
4. clarity: Is it understandable to a business user?

Return JSON in this exact shape:
{{
  "score": 0.0,
  "correctness": 0.0,
  "completeness": 0.0,
  "groundedness": 0.0,
  "clarity": 0.0,
  "reason": "one short explanation"
}}
Scores must be between 0 and 1."""


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def judge_response(case: Dict[str, Any], response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return judge scores, or None when no judge client is available."""
    try:
        rag_agent = get_rag_agent()
    except Exception as exc:
        logger.info("LLM judge unavailable while loading RAG agent: %s", exc)
        return None

    clients = []
    if getattr(rag_agent, "gemini_flash", None):
        clients.append(("Gemini Flash", rag_agent.gemini_flash))
    if getattr(rag_agent, "groq_client", None):
        clients.append(("Groq", rag_agent.groq_client))

    prompt = build_judge_prompt(case, response)
    for name, client in clients:
        try:
            result = client.invoke(prompt)
            parsed = _parse_json_object(result.content)
            if not parsed:
                continue
            score = float(parsed.get("score", 0))
            parsed["score"] = max(0.0, min(1.0, score))
            parsed["judge_model"] = name
            return parsed
        except Exception as exc:
            logger.info("LLM judge failed with %s: %s", name, exc)

    return None

