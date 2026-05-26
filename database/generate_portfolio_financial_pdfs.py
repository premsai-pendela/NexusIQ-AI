"""
Generate portfolio financial PDFs from isolated enterprise staging tables.

Covers the full 5-year date range: FY 2021, FY 2022, FY 2023, FY 2025, and
H1 2026. The protected 2024 live-baseline PDFs are intentionally out of scope.

This module plans documents without opening a database by default and requires
an explicit staging-only acknowledgement before it queries the database or
writes any files. All published figures are validated against direct staging
SQL before any PDF is written.
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
from typing import Dict, List, Optional, Sequence, Tuple

from database.generate_enterprise_expansion import (
    PRESERVED_BASELINE_END,
    PRESERVED_BASELINE_START,
    STAGING_NAMESPACE,
)


PORTFOLIO_DATASET_ID = "enterprise_portfolio_v1"
EVIDENCE_VERSION = "validated_v2"
EXECUTION_CONFIRMATION = "GENERATE_PORTFOLIO_PDFS_FROM_STAGING_ONLY"
REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED_PDF_ROOT = REPO_ROOT / "data" / "pdfs_staging"
LIVE_PDF_ROOT = REPO_ROOT / "data" / "pdfs"

# sha256("enterprise_portfolio_v1")[:8] = 502a08ab
PORTFOLIO_COMBINED_VIEW = (
    f'"{STAGING_NAMESPACE}"."combined_sales_transactions_{PORTFOLIO_DATASET_ID}_502a08ab"'
)

CATEGORIES = ("Appliances", "Electronics", "Fitness", "Home", "Office")
QUARTERS = (
    ("Q1", 1, 3),
    ("Q2", 4, 6),
    ("Q3", 7, 9),
    ("Q4", 10, 12),
)


class PortfolioPdfGenerationError(RuntimeError):
    """Raised when a portfolio PDF generation safety boundary is not satisfied."""


@dataclass(frozen=True)
class ReportingPeriod:
    """A staged financial reporting window that must not overlap live 2024."""

    label: str
    filename: str
    start_date: date
    end_date_exclusive: date
    year: int  # calendar year for quarter queries; None-safe via guard in __post_init__

    def as_dict(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "filename": self.filename,
            "start": self.start_date.isoformat(),
            "end_exclusive": self.end_date_exclusive.isoformat(),
        }


REPORTING_PERIODS: Sequence[ReportingPeriod] = (
    ReportingPeriod(
        "FY 2021", "01_FY_2021_Portfolio_Financial_Report.pdf",
        date(2021, 1, 1), date(2022, 1, 1), 2021,
    ),
    ReportingPeriod(
        "FY 2022", "02_FY_2022_Portfolio_Financial_Report.pdf",
        date(2022, 1, 1), date(2023, 1, 1), 2022,
    ),
    ReportingPeriod(
        "FY 2023", "03_FY_2023_Portfolio_Financial_Report.pdf",
        date(2023, 1, 1), date(2024, 1, 1), 2023,
    ),
    ReportingPeriod(
        "FY 2025", "04_FY_2025_Portfolio_Financial_Report.pdf",
        date(2025, 1, 1), date(2026, 1, 1), 2025,
    ),
    ReportingPeriod(
        "H1 2026", "05_H1_2026_Portfolio_Financial_Report.pdf",
        date(2026, 1, 1), date(2026, 7, 1), 2026,
    ),
)


def _validate_dataset_id(dataset_id: str) -> None:
    if dataset_id != PORTFOLIO_DATASET_ID:
        raise PortfolioPdfGenerationError(
            f"Portfolio PDF generation is locked to {PORTFOLIO_DATASET_ID!r}; "
            f"received {dataset_id!r}."
        )


def _validate_period(period: ReportingPeriod) -> None:
    if period.start_date >= period.end_date_exclusive:
        raise PortfolioPdfGenerationError(f"Invalid reporting window for {period.label!r}.")
    overlaps_2024 = (
        period.start_date <= PRESERVED_BASELINE_END
        and period.end_date_exclusive > PRESERVED_BASELINE_START
    )
    if overlaps_2024:
        raise PortfolioPdfGenerationError(
            f"Reporting period {period.label!r} overlaps the protected 2024 live PDF baseline."
        )
    if "2024" in period.filename:
        raise PortfolioPdfGenerationError(
            "Portfolio output filenames must not resemble protected 2024 PDFs."
        )


def _output_directory(dataset_id: str, output_root_override: Optional[Path] = None) -> Path:
    output_root = STAGED_PDF_ROOT if output_root_override is None else Path(output_root_override)
    live_root = LIVE_PDF_ROOT.resolve()
    requested_root = output_root.resolve()
    if requested_root == live_root or live_root in requested_root.parents:
        raise PortfolioPdfGenerationError(
            "Portfolio PDFs cannot be written within the live data/pdfs document archive."
        )
    return requested_root / dataset_id / EVIDENCE_VERSION / "01_financial"


def _qualified(table: str) -> str:
    return f'"{STAGING_NAMESPACE}"."{table}"'


def build_pdf_plan(
    *,
    dataset_id: str = PORTFOLIO_DATASET_ID,
    periods: Sequence[ReportingPeriod] = REPORTING_PERIODS,
    _output_root_override: Optional[Path] = None,
) -> Dict[str, object]:
    """Build a local-only document plan without querying SQL or writing files."""
    _validate_dataset_id(dataset_id)
    if not periods:
        raise PortfolioPdfGenerationError("At least one non-2024 reporting period is required.")
    for period in periods:
        _validate_period(period)
    output_dir = _output_directory(dataset_id, _output_root_override)
    outputs = [str(output_dir / period.filename) for period in periods]
    return {
        "action": "portfolio_staging_financial_pdf_generation",
        "dry_run": True,
        "dataset_id": dataset_id,
        "staging_namespace": STAGING_NAMESPACE,
        "source_table": _qualified("sales_transactions"),
        "source_policy": (
            "read_direct_staged_generated_table_only_never_combined_or_public_views"
        ),
        "protected_period_policy": "never_generate_or_overwrite_live_2024_pdfs",
        "output_policy": "repo_staged_directory_only_atomic_publish_fail_if_destination_exists",
        "output_directory": str(output_dir),
        "periods": [period.as_dict() for period in periods],
        "outputs": outputs,
    }


def render_metric_queries(dataset_id: str = PORTFOLIO_DATASET_ID) -> Dict[str, str]:
    """Render all read-only SQL templates published in the PDFs."""
    _validate_dataset_id(dataset_id)
    sales = _qualified("sales_transactions")
    base_filter = (
        "WHERE sale.dataset_id = %s "
        "AND sale.transaction_date >= %s AND sale.transaction_date < %s"
    )
    category_filter = base_filter + " AND sale.product_category = %s"

    return {
        "summary": (
            "SELECT COUNT(*) AS transactions, "
            "COALESCE(ROUND(SUM(sale.total_amount)::numeric, 2), 0) AS revenue, "
            "COALESCE(ROUND(SUM(sale.gross_margin_amount)::numeric, 2), 0) AS gross_margin "
            f"FROM {sales} AS sale {base_filter}"
        ),
        "by_category": (
            "SELECT sale.product_category, COUNT(*) AS transactions, "
            "COALESCE(ROUND(SUM(sale.total_amount)::numeric, 2), 0) AS revenue "
            f"FROM {sales} AS sale {base_filter} "
            "GROUP BY sale.product_category ORDER BY revenue DESC"
        ),
        "by_quarter": (
            "SELECT EXTRACT(QUARTER FROM sale.transaction_date)::int AS quarter, "
            "COUNT(*) AS transactions, "
            "COALESCE(ROUND(SUM(sale.total_amount)::numeric, 2), 0) AS revenue "
            f"FROM {sales} AS sale {base_filter} "
            "GROUP BY quarter ORDER BY quarter"
        ),
        "by_channel": (
            "SELECT sale.channel, COUNT(*) AS transactions, "
            "COALESCE(ROUND(SUM(sale.total_amount)::numeric, 2), 0) AS revenue "
            f"FROM {sales} AS sale {base_filter} "
            "GROUP BY sale.channel ORDER BY revenue DESC"
        ),
    }


def _query_period_metrics(
    cursor, period: ReportingPeriod, dataset_id: str
) -> Dict[str, object]:
    queries = render_metric_queries(dataset_id)
    params = (dataset_id, period.start_date, period.end_date_exclusive)

    cursor.execute(queries["summary"], params)
    row = cursor.fetchone()
    transactions, revenue, gross_margin = int(row[0]), Decimal(row[1]), Decimal(row[2])

    cursor.execute(queries["by_category"], params)
    by_category: List[Tuple[str, int, Decimal]] = [
        (r[0], int(r[1]), Decimal(r[2])) for r in cursor.fetchall()
    ]

    cursor.execute(queries["by_quarter"], params)
    by_quarter: List[Tuple[int, int, Decimal]] = [
        (int(r[0]), int(r[1]), Decimal(r[2])) for r in cursor.fetchall()
    ]

    cursor.execute(queries["by_channel"], params)
    by_channel: List[Tuple[str, int, Decimal]] = [
        (r[0], int(r[1]), Decimal(r[2])) for r in cursor.fetchall()
    ]

    return {
        "transactions": transactions,
        "revenue": revenue,
        "gross_margin": gross_margin,
        "by_category": by_category,
        "by_quarter": by_quarter,
        "by_channel": by_channel,
    }


def _currency(value: Decimal) -> str:
    return f"${Decimal(value):,.2f}"


def _pct(numerator: Decimal, denominator: Decimal) -> str:
    if not denominator:
        return "0.0%"
    return f"{float(numerator / denominator * 100):.1f}%"


def _render_period_pdf(
    period: ReportingPeriod, metrics: Dict[str, object], out_path: Path
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PortfolioTitle",
        parent=styles["Heading1"],
        fontSize=19,
        textColor=colors.HexColor("#1a4e8a"),
    )
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    gap = Spacer(1, 0.15 * inch)

    revenue: Decimal = metrics["revenue"]
    gross_margin: Decimal = metrics["gross_margin"]
    transactions: int = metrics["transactions"]
    by_category: List[Tuple[str, int, Decimal]] = metrics["by_category"]
    by_quarter: List[Tuple[int, int, Decimal]] = metrics["by_quarter"]
    by_channel: List[Tuple[str, int, Decimal]] = metrics["by_channel"]

    tbl_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d6e4f0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fc")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbc8d4")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])

    def _tbl(data: list, col_widths: list) -> Table:
        t = Table(data, colWidths=col_widths)
        t.setStyle(tbl_style)
        return t

    is_half_year = period.end_date_exclusive.month == 7

    story = [
        Paragraph("NexusIQ Corporation", styles["Normal"]),
        Paragraph(f"{period.label} Enterprise Portfolio Financial Report", title_style),
        Paragraph(
            "Source: isolated enterprise staging generated tables only. "
            "This document is not part of the protected 2024 production-aligned archive. "
            "All figures are validated against direct staging SQL before indexing.",
            body,
        ),
        gap,
        Paragraph("Top-Line Summary", h2),
        Paragraph(
            f"{period.label} generated sales: <b>{transactions:,}</b> transactions, "
            f"total revenue <b>{_currency(revenue)}</b>, "
            f"gross margin <b>{_currency(gross_margin)}</b> "
            f"({_pct(gross_margin, revenue)} of revenue).",
            body,
        ),
        gap,
    ]

    # Revenue by category table
    if by_category:
        story.append(Paragraph("Revenue by Product Category", h2))
        cat_data = [["Category", "Transactions", "Revenue", "Revenue %"]]
        for cat, txn, rev in by_category:
            cat_data.append([cat, f"{txn:,}", _currency(rev), _pct(rev, revenue)])
        story.append(_tbl(cat_data, [2.2 * inch, 1.4 * inch, 1.6 * inch, 1.0 * inch]))
        story.append(gap)

    # Revenue by quarter (skip for H1 — only 2 quarters, label differently)
    if by_quarter:
        label = "Revenue by Half" if is_half_year else "Revenue by Quarter"
        story.append(Paragraph(label, h2))
        q_labels = {1: "Q1 (Jan–Mar)", 2: "Q2 (Apr–Jun)", 3: "Q3 (Jul–Sep)", 4: "Q4 (Oct–Dec)"}
        q_data = [["Period", "Transactions", "Revenue", "Revenue %"]]
        for q, txn, rev in by_quarter:
            q_data.append([q_labels.get(q, f"Q{q}"), f"{txn:,}", _currency(rev), _pct(rev, revenue)])
        story.append(_tbl(q_data, [2.2 * inch, 1.4 * inch, 1.6 * inch, 1.0 * inch]))
        story.append(gap)

    # Revenue by channel
    if by_channel:
        story.append(Paragraph("Revenue by Sales Channel", h2))
        ch_data = [["Channel", "Transactions", "Revenue", "Revenue %"]]
        for ch, txn, rev in by_channel:
            ch_data.append([ch, f"{txn:,}", _currency(rev), _pct(rev, revenue)])
        story.append(_tbl(ch_data, [2.2 * inch, 1.4 * inch, 1.6 * inch, 1.0 * inch]))
        story.append(gap)

    story.append(Paragraph(
        "Validation scope: transaction count and total revenue are the primary cross-validation "
        "anchors checked against direct staging SQL. Category and channel breakdowns are "
        "published only after per-period aggregate SQL validation passes.",
        body,
    ))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(story)


def _require_generation_confirmation(execute: bool, confirmation: Optional[str]) -> None:
    if not execute or confirmation != EXECUTION_CONFIRMATION:
        raise PortfolioPdfGenerationError(
            "Portfolio PDF generation is disabled by default. To query only portfolio staging "
            "tables and write staged PDFs, provide:\n"
            f"  --execute --confirm-staging-only {EXECUTION_CONFIRMATION}"
        )


def generate_portfolio_pdfs(
    *,
    dataset_id: str = PORTFOLIO_DATASET_ID,
    periods: Sequence[ReportingPeriod] = REPORTING_PERIODS,
    execute: bool = False,
    confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
    _output_root_override: Optional[Path] = None,
    _connection_factory=None,
    _renderer=None,
) -> Dict[str, object]:
    """Query staged portfolio rows and atomically publish non-overwriting documents."""
    plan = build_pdf_plan(
        dataset_id=dataset_id,
        periods=periods,
        _output_root_override=_output_root_override,
    )
    _require_generation_confirmation(execute, confirmation)

    output_directory = Path(str(plan["output_directory"]))
    if output_directory.exists():
        raise PortfolioPdfGenerationError(
            "Refusing to overwrite staged portfolio PDF destination; "
            "use a new dataset ID after review: " + str(output_directory)
        )

    if database_url is None:
        database_url = os.getenv("NEXUSIQ_FINANCIAL_DB_URL")
        if database_url is None:
            from config.settings import settings
            database_url = settings.database_url
    if not database_url:
        raise PortfolioPdfGenerationError(
            "Set DATABASE_URL or NEXUSIQ_FINANCIAL_DB_URL for staged PDF execution."
        )

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

    empty_periods = [
        period.label for period, m in metrics_by_period if int(m["transactions"]) == 0
    ]
    if empty_periods:
        raise PortfolioPdfGenerationError(
            "No staged generated transactions found for: " + ", ".join(empty_periods) + ". "
            "Load the portfolio CSV extract into staging before generating PDFs."
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(
        tempfile.mkdtemp(
            prefix=".portfolio_financial_pdf_publish_",
            dir=str(output_directory.parent),
        )
    )
    try:
        for period, metrics in metrics_by_period:
            renderer(period, metrics, temporary_directory / period.filename)
        if output_directory.exists():
            raise PortfolioPdfGenerationError(
                f"Refusing to overwrite staged portfolio PDF destination: {output_directory}"
            )
        temporary_directory.replace(output_directory)
    except Exception:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise

    generated = [str(output_directory / period.filename) for period in periods]
    return {**plan, "dry_run": False, "generated_outputs": generated}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or generate portfolio financial PDFs from isolated staging SQL"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for cmd in ("plan", "sql"):
        sub = subparsers.add_parser(cmd)
        sub.add_argument("--dataset-id", default=PORTFOLIO_DATASET_ID)
    gen = subparsers.add_parser("generate")
    gen.add_argument("--dataset-id", default=PORTFOLIO_DATASET_ID)
    gen.add_argument("--execute", action="store_true")
    gen.add_argument("--confirm-staging-only")
    gen.add_argument("--database-url")
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
        result = generate_portfolio_pdfs(
            dataset_id=args.dataset_id,
            execute=args.execute,
            confirmation=args.confirm_staging_only,
            database_url=args.database_url,
        )
        print(json.dumps(result, indent=2))
    else:
        raise PortfolioPdfGenerationError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
