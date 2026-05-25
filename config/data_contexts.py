"""Explicit data contexts for the live app and isolated enterprise pilot demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_CONTEXT_KEY = "live"
PILOT_CONTEXT_KEY = "enterprise_pilot"
PILOT_DATASET_ID = "enterprise_pilot_v1"
PILOT_COMBINED_VIEW = '"nexusiq_expansion_staging"."combined_sales_transactions_enterprise_pilot_v1_793cb277"'
PILOT_CHROMA_DIRECTORY = (
    REPO_ROOT / "data" / "chroma_staging" / PILOT_DATASET_ID / "validated_v2" / "financial_documents"
)
PILOT_COLLECTION_NAME = "nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2"


@dataclass(frozen=True)
class DataContext:
    """A complete SQL/RAG evidence boundary used by an app session."""

    key: str
    label: str
    sql_table: str
    sql_scope: str
    date_guidance: str
    document_scope: str
    available_years: tuple[int, ...] = (2024,)
    chroma_directory: Optional[Path] = None
    chroma_collection: str = "nexusiq_docs"
    isolated_pilot: bool = False
    allow_web: bool = True

    @property
    def is_pilot(self) -> bool:
        return self.isolated_pilot


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

PILOT_CONTEXT = DataContext(
    key=PILOT_CONTEXT_KEY,
    label="Enterprise Pilot (Validated Staging)",
    sql_table=PILOT_COMBINED_VIEW,
    sql_scope=(
        "250,000 read-only combined staging-view transactions: 100,000 preserved live 2024 rows "
        "plus 150,000 generated rows outside 2024"
    ),
    date_guidance=(
        "This isolated pilot spans FY 2021, FY 2022, FY 2023, preserved live FY 2024, FY 2025, "
        "and H1 2026. Only FY 2021, FY 2022, FY 2023, FY 2025, and H1 2026 have validated "
        "pilot PDF/index evidence. Never claim pilot PDF validation for 2024."
    ),
    document_scope=(
        "5 isolated validated financial PDFs for FY 2021, FY 2022, FY 2023, FY 2025, and H1 2026"
    ),
    available_years=(2021, 2022, 2023, 2024, 2025, 2026),
    chroma_directory=PILOT_CHROMA_DIRECTORY,
    chroma_collection=PILOT_COLLECTION_NAME,
    isolated_pilot=True,
    allow_web=False,
)


def get_data_context(key: str = LIVE_CONTEXT_KEY) -> DataContext:
    """Return a supported app data context, defaulting safely to live."""
    contexts = {
        LIVE_CONTEXT_KEY: LIVE_CONTEXT,
        PILOT_CONTEXT_KEY: PILOT_CONTEXT,
    }
    try:
        return contexts[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported NexusIQ data context: {key!r}") from exc
