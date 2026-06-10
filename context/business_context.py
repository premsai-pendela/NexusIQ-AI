"""Deterministic business-context retrieval for Text-to-SQL generation.

Enterprise Text-to-SQL fails when the model knows SQL syntax but not
company-specific definitions ("net revenue", "active customer", fiscal
calendars). This module retrieves the few glossary definitions relevant to a
question and renders a compact prompt block — no LLM calls, no embeddings,
fully unit-testable.

Retrieval is intentionally conservative: an entry is selected only on an
exact term/alias phrase match or strong keyword overlap, so ordinary
questions ("total revenue in October") get an unchanged prompt.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_GLOSSARY_PATH = Path(__file__).parent.parent / "config" / "business_glossary.json"

# Words too generic to signal a business term on their own.
_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "by", "we",
    "our", "us", "is", "are", "was", "were", "what", "which", "how", "many",
    "much", "did", "do", "does", "have", "has", "had", "with", "from", "at",
    "per", "total", "all", "show", "me", "get", "give", "list", "2024", "q1",
    "q2", "q3", "q4", "year", "month", "quarter", "last", "this", "that",
}

# Minimum keyword-overlap score for selection when no exact phrase matches.
_OVERLAP_THRESHOLD = 2
_MAX_ENTRIES = 3
_MAX_BLOCK_CHARS = 900
_PHRASE_SCORE = 10


@dataclass
class BusinessContextEntry:
    id: str
    term: str
    definition: str
    aliases: List[str] = field(default_factory=list)
    category: str = "metric"
    tables: List[str] = field(default_factory=list)

    def phrases(self) -> List[str]:
        return [self.term.lower()] + [alias.lower() for alias in self.aliases]

    def keywords(self) -> set:
        words = set()
        for phrase in self.phrases():
            words.update(_tokenize(phrase))
        return words


def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9_]+", str(text or "").lower())
    normalized = []
    for word in words:
        if word in _STOPWORDS:
            continue
        # Light plural stem so "customers" matches "customer".
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        normalized.append(word)
    return normalized


def load_glossary(path: Optional[Path] = None) -> List[BusinessContextEntry]:
    """Load glossary entries, skipping malformed ones instead of failing."""
    glossary_path = Path(
        os.getenv("NEXUSIQ_BUSINESS_GLOSSARY_PATH", str(path or DEFAULT_GLOSSARY_PATH))
    )
    try:
        raw = json.loads(glossary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not load business glossary %s: %s", glossary_path, exc)
        return []

    entries = []
    for item in raw.get("entries", []):
        try:
            entries.append(
                BusinessContextEntry(
                    id=str(item["id"]),
                    term=str(item["term"]),
                    definition=str(item["definition"]),
                    aliases=[str(alias) for alias in item.get("aliases", [])],
                    category=str(item.get("category", "metric")),
                    tables=[str(table) for table in item.get("tables", [])],
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed glossary entry %r: %s", item, exc)
    return entries


class BusinessContextRetriever:
    """Score glossary entries against a question; deterministic, no LLM."""

    def __init__(self, entries: Optional[List[BusinessContextEntry]] = None):
        self.entries = entries if entries is not None else load_glossary()

    def score(self, question: str, entry: BusinessContextEntry) -> int:
        question_lower = " ".join(re.findall(r"[a-z0-9_]+", str(question or "").lower()))
        best = 0
        for phrase in entry.phrases():
            if phrase and phrase in question_lower:
                best = max(best, _PHRASE_SCORE + len(phrase.split()))
        if best:
            return best
        overlap = len(set(_tokenize(question)) & entry.keywords())
        return overlap if overlap >= _OVERLAP_THRESHOLD else 0

    def retrieve(self, question: str, max_entries: int = _MAX_ENTRIES) -> List[Tuple[int, BusinessContextEntry]]:
        scored = [(self.score(question, entry), entry) for entry in self.entries]
        hits = [(score, entry) for score, entry in scored if score > 0]
        hits.sort(key=lambda item: (-item[0], item[1].id))
        return hits[:max_entries]


def build_context_block(
    question: str,
    retriever: Optional[BusinessContextRetriever] = None,
    max_chars: int = _MAX_BLOCK_CHARS,
) -> Dict[str, object]:
    """Return {'block': str, 'ids': [...], 'chars': int} for prompt injection.

    Empty block (ids == []) means the SQL prompt must remain unchanged.
    """
    try:
        retriever = retriever or _get_default_retriever()
        hits = retriever.retrieve(question)
    except Exception as exc:
        logger.warning("Business context retrieval failed; continuing without it: %s", exc)
        return {"block": "", "ids": [], "chars": 0}

    lines = []
    ids = []
    used = 0
    for _score, entry in hits:
        line = f"- {entry.term}: {entry.definition}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        ids.append(entry.id)
        used += len(line)

    if not lines:
        return {"block": "", "ids": [], "chars": 0}

    block = (
        "COMPANY BUSINESS DEFINITIONS (apply these when the question uses these terms):\n"
        + "\n".join(lines)
    )
    return {"block": block, "ids": ids, "chars": len(block)}


_default_retriever: Optional[BusinessContextRetriever] = None


def _get_default_retriever() -> BusinessContextRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = BusinessContextRetriever()
    return _default_retriever


def reset_default_retriever() -> None:
    """Test hook: force glossary reload."""
    global _default_retriever
    _default_retriever = None


def expected_metric_ids(question: str) -> List[str]:
    """IDs of company-defined *metric* glossary entries the question targets.

    Used by Fusion to detect when a question asks for a business-defined
    metric (net revenue, return rate, ...) that cannot be answered from
    documents alone. Deterministic; returns [] on any failure.
    """
    try:
        hits = _get_default_retriever().retrieve(question)
    except Exception as exc:
        logger.warning("Metric-context check failed; assuming none: %s", exc)
        return []
    return [entry.id for _score, entry in hits if entry.category == "metric"]


def business_context_enabled() -> bool:
    return os.getenv("NEXUSIQ_BUSINESS_CONTEXT", "1").strip().lower() not in {"0", "false", "no", "off"}
