"""Data context for the NexusIQ live app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_CONTEXT_KEY = "live"


@dataclass(frozen=True)
class DataContext:
    """SQL/RAG evidence boundary used by an app session."""

    key: str
    label: str
    sql_table: str
    sql_scope: str
    date_guidance: str
    document_scope: str
    available_years: tuple[int, ...] = (2024,)
    chroma_directory: Optional[Path] = None
    chroma_collection: str = "nexusiq_docs"
    allow_web: bool = True

    @property
    def is_pilot(self) -> bool:
        return False


LIVE_CONTEXT = DataContext(
    key=LIVE_CONTEXT_KEY,
    label="Live Baseline (2024)",
    sql_table="sales_transactions",
    sql_scope="100,000 validated Supabase sales transactions",
    date_guidance=(
        "All SQL transaction data is from year 2024 only (January 1 through December 31, 2024). "
        "When a user mentions Q1-Q4 without a year, use 2024."
    ),
    document_scope="25 indexed business PDFs covering 2024 reports, policies, and strategy",
)


def get_data_context(key: str = LIVE_CONTEXT_KEY) -> DataContext:
    """Return the live data context (only supported context)."""
    return LIVE_CONTEXT
