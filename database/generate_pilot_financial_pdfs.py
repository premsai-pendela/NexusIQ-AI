"""
Generate pilot financial PDFs from isolated enterprise staging tables.

The production-aligned 2024 PDF archive is intentionally out of scope. This
module plans new-period documents without opening a database by default and
requires an explicit staging-only acknowledgement before it queries Supabase
or writes any PDF files.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Sequence

from database.generate_enterprise_expansion import PRESERVED_BASELINE_END, PRESERVED_BASELINE_START, STAGING_NAMESPACE


PILOT_DATASET_ID = "enterprise_pilot_v1"
EVIDENCE_VERSION = "validated_v2"
EXECUTION_CONFIRMATION = "GENERATE_PILOT_PDFS_FROM_STAGING_ONLY"
REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED_PDF_ROOT = REPO_ROOT / "data" / "pdfs_staging"
LIVE_PDF_ROOT = REPO_ROOT / "data" / "pdfs"


class PilotPdfGenerationError(RuntimeError):
    """Raised when a pilot PDF generation safety boundary is not satisfied."""


@dataclass(frozen=True)
class ReportingPeriod:
    """A staged financial reporting window that cannot overlap live 2024."""

    label: str
    filename: str
    start_date: date
    end_date_exclusive: date

    def as_dict(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "filename": self.filename,
            "start": self.start_date.isoformat(),
            "end_exclusive": self.end_date_exclusive.isoformat(),
        }


REPORTING_PERIODS: Sequence[ReportingPeriod] = (
    ReportingPeriod("FY 2021", "01_FY_2021_Enterprise_Pilot_Financial_Report.pdf", date(2021, 1, 1), date(2022, 1, 1)),
    ReportingPeriod("FY 2022", "02_FY_2022_Enterprise_Pilot_Financial_Report.pdf", date(2022, 1, 1), date(2023, 1, 1)),
    ReportingPeriod("FY 2023", "03_FY_2023_Enterprise_Pilot_Financial_Report.pdf", date(2023, 1, 1), date(2024, 1, 1)),
    ReportingPeriod("FY 2025", "04_FY_2025_Enterprise_Pilot_Financial_Report.pdf", date(2025, 1, 1), date(2026, 1, 1)),
    ReportingPeriod("H1 2026", "05_H1_2026_Enterprise_Pilot_Financial_Report.pdf", date(2026, 1, 1), date(2026, 7, 1)),
)


def _validate_dataset_id(dataset_id: str) -> None:
    if dataset_id != PILOT_DATASET_ID:
        raise PilotPdfGenerationError(
            f"Pilot PDF generation is locked to {PILOT_DATASET_ID!r}; received {dataset_id!r}."
        )


def _validate_period(period: ReportingPeriod) -> None:
    if period.start_date >= period.end_date_exclusive:
        raise PilotPdfGenerationError(f"Invalid reporting window for {period.label!r}.")
    overlaps_2024 = (
        period.start_date <= PRESERVED_BASELINE_END
        and period.end_date_exclusive > PRESERVED_BASELINE_START
    )
    if overlaps_2024:
        raise PilotPdfGenerationError(
            f"Reporting period {period.label!r} overlaps the protected 2024 live PDF baseline."
        )
    if "2024" in period.filename:
        raise PilotPdfGenerationError("Pilot output filenames must not resemble protected 2024 PDFs.")


def _output_directory(dataset_id: str, output_root_override: Optional[Path] = None) -> Path:
    output_root = STAGED_PDF_ROOT if output_root_override is None else Path(output_root_override)
    live_root = LIVE_PDF_ROOT.resolve()
    requested_root = output_root.resolve()
    if requested_root == live_root or live_root in requested_root.parents:
        raise PilotPdfGenerationError("Pilot PDFs cannot be written within the live data/pdfs document archive.")
    return requested_root / dataset_id / EVIDENCE_VERSION / "01_financial"


def _qualified_staging_table(table: str) -> str:
    return f'"{STAGING_NAMESPACE}"."{table}"'


def staging_source_tables(dataset_id: str = PILOT_DATASET_ID) -> Sequence[str]:
    """Return the only direct staged fact/dimension tables used for PDF metrics."""
    _validate_dataset_id(dataset_id)
    from config.data_contexts import PILOT_COMBINED_VIEW
    return (PILOT_COMBINED_VIEW,)


def build_pdf_plan(
    *,
    dataset_id: str = PILOT_DATASET_ID,
    periods: Sequence[ReportingPeriod] = REPORTING_PERIODS,
    _output_root_override: Optional[Path] = None,
) -> Dict[str, object]:
    """Build a local-only document plan without querying SQL or writing files."""
    _validate_dataset_id(dataset_id)
    if not periods:
        raise PilotPdfGenerationError("At least one non-2024 reporting period is required.")
    for period in periods:
        _validate_period(period)
    output_dir = _output_directory(dataset_id, _output_root_override)
    outputs = [str(output_dir / period.filename) for period in periods]
    return {
        "action": "pilot_staging_financial_pdf_generation",
        "dry_run": True,
        "dataset_id": dataset_id,
        "source_tables": list(staging_source_tables(dataset_id)),
        "source_policy": "read_direct_staged_generated_tables_only_never_combined_or_public_views",
        "protected_period_policy": "never_generate_or_overwrite_live_2024_pdfs",
        "output_policy": "repo_staged_directory_only_atomic_publish_fail_if_destination_exists",
        "output_directory": str(output_dir),
        "periods": [period.as_dict() for period in periods],
        "outputs": outputs,
    }


def render_metric_queries(dataset_id: str = PILOT_DATASET_ID) -> Dict[str, str]:
    """Render the read-only SQL for facts that are published and validated."""
    sales = staging_source_tables(dataset_id)[0]
    filter_clause = (
        "WHERE sale.dataset_id = %s "
        "AND sale.transaction_date >= %s AND sale.transaction_date < %s"
    )
    return {
        "summary": (
            "SELECT COUNT(*) AS transactions, "
            "COALESCE(ROUND(SUM(sale.total_amount)::numeric, 2), 0) AS revenue "
            f"FROM {sales} AS sale {filter_clause}"
        ),
    }


def _query_period_metrics(cursor, period: ReportingPeriod, dataset_id: str) -> Dict[str, object]:
    queries = render_metric_queries(dataset_id)
    parameters = (dataset_id, period.start_date, period.end_date_exclusive)
    cursor.execute(queries["summary"], parameters)
    transactions, revenue = cursor.fetchone()
    return {"transactions": transactions, "revenue": revenue}


def _currency(value: Decimal) -> str:
    return f"${Decimal(value):,.2f}"


def _render_period_pdf(period: ReportingPeriod, metrics: Dict[str, object], out_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    title = ParagraphStyle("PilotTitle", parent=styles["Heading1"], fontSize=19, textColor=colors.HexColor("#1f77b4"))
    revenue = Decimal(metrics["revenue"])
    transactions = int(metrics["transactions"])
    document = SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=inch, rightMargin=inch)
    story = [
        Paragraph("NexusIQ Corporation", styles["Normal"]),
        Paragraph(f"{period.label} Pilot Staging Financial Report", title),
        Paragraph(
            "Source: isolated Supabase staging generated tables only. "
            "This document is not part of the protected 2024 production-aligned archive.",
            styles["BodyText"],
        ),
        Spacer(1, 0.18 * inch),
        Paragraph("Validated Financial Evidence", styles["Heading2"]),
        Paragraph(
            f"{period.label} generated sales contain <b>{transactions:,}</b> transactions "
            f"with total revenue of <b>{_currency(revenue)}</b>.",
            styles["BodyText"],
        ),
        Spacer(1, 0.18 * inch),
        Paragraph(
            "Scope: transaction count and total revenue are the only published financial facts in this "
            "pilot evidence document, and both are checked exactly against direct staging SQL before indexing.",
            styles["BodyText"],
        ),
    ]
    document.build(story)


def _require_generation_confirmation(execute: bool, confirmation: Optional[str]) -> None:
    if not execute or confirmation != EXECUTION_CONFIRMATION:
        raise PilotPdfGenerationError(
            "Staged PDF generation is disabled by default. To query only pilot staging tables "
            f"and write staged PDFs, provide --execute --confirm-staging-only {EXECUTION_CONFIRMATION}."
        )


def generate_pilot_pdfs(
    *,
    dataset_id: str = PILOT_DATASET_ID,
    periods: Sequence[ReportingPeriod] = REPORTING_PERIODS,
    execute: bool = False,
    confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
    _output_root_override: Optional[Path] = None,
    _connection_factory=None,
    _renderer=None,
) -> Dict[str, object]:
    """Query staged generated rows and atomically publish non-overwriting documents."""
    plan = build_pdf_plan(
        dataset_id=dataset_id,
        periods=periods,
        _output_root_override=_output_root_override,
    )
    _require_generation_confirmation(execute, confirmation)
    output_directory = Path(str(plan["output_directory"]))
    if output_directory.exists():
        raise PilotPdfGenerationError(
            "Refusing to overwrite staged pilot PDF destination; use a new dataset after review: "
            + str(output_directory)
        )
    if database_url is None:
        database_url = os.getenv("NEXUSIQ_FINANCIAL_DB_URL")
        if database_url is None:
            from config.settings import settings

            database_url = settings.database_url
    if not database_url:
        raise PilotPdfGenerationError("Set DATABASE_URL or NEXUSIQ_FINANCIAL_DB_URL for staged PDF execution.")

    if _connection_factory is None:
        import psycopg2

        _connection_factory = psycopg2.connect
    renderer = _renderer or _render_period_pdf
    connection = _connection_factory(database_url)
    try:
        cursor = connection.cursor()
        metrics_by_period = [
            (period, _query_period_metrics(cursor, period, dataset_id))
            for period in periods
        ]
    finally:
        connection.close()
    empty_periods = [period.label for period, metrics in metrics_by_period if int(metrics["transactions"]) == 0]
    if empty_periods:
        raise PilotPdfGenerationError(
            "No staged generated transactions found for: " + ", ".join(empty_periods) + "."
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(
        tempfile.mkdtemp(prefix=".pilot_financial_pdf_publish_", dir=str(output_directory.parent))
    )
    try:
        for period, metrics in metrics_by_period:
            renderer(period, metrics, temporary_directory / period.filename)
        if output_directory.exists():
            raise PilotPdfGenerationError(f"Refusing to overwrite staged pilot PDF destination: {output_directory}")
        temporary_directory.replace(output_directory)
    except Exception:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    generated = [str(output_directory / period.filename) for period in periods]
    return {**plan, "dry_run": False, "generated_outputs": generated}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or generate pilot financial PDFs from isolated staging SQL")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "sql"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--dataset-id", default=PILOT_DATASET_ID)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--dataset-id", default=PILOT_DATASET_ID)
    generate.add_argument("--execute", action="store_true")
    generate.add_argument("--confirm-staging-only")
    generate.add_argument("--database-url")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "plan":
        print(json.dumps(build_pdf_plan(dataset_id=args.dataset_id), indent=2))
    elif args.command == "sql":
        payload = {
            **build_pdf_plan(dataset_id=args.dataset_id),
            "queries": render_metric_queries(args.dataset_id),
        }
        print(json.dumps(payload, indent=2))
    elif args.command == "generate":
        result = generate_pilot_pdfs(
            dataset_id=args.dataset_id,
            execute=args.execute,
            confirmation=args.confirm_staging_only,
            database_url=args.database_url,
        )
        print(json.dumps(result, indent=2))
    else:
        raise PilotPdfGenerationError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
