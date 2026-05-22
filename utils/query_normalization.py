"""Question normalization helpers shared by cache and UI repeat detection."""

from __future__ import annotations

import re


_TOKEN_ALIASES = {
    "sql": "sql",
    "pdf": "pdf",
    "pdfs": "pdf",
    "report": "reports",
    "reports": "reports",
}


def canonical_question_key(question: str) -> str:
    """Return a stable key for equivalent wording with reordered terms.

    This intentionally stays conservative: it handles case, punctuation,
    whitespace, and simple token reordering such as "SQL and PDF" vs
    "PDF and sql" without trying to be a semantic cache.
    """
    text = str(question or "").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    normalized = [_TOKEN_ALIASES.get(token, token) for token in tokens]
    return " ".join(sorted(normalized))


def display_question_key(question: str) -> str:
    """Normalize for human-facing exact repeats while preserving word order."""
    return re.sub(r"\s+", " ", str(question or "").strip().lower())
