"""
Isolated pilot PDF ingestion and SQL-to-PDF alignment validation.

This phase consumes only the staged financial PDFs generated for the
enterprise pilot. Planning is local-only; Chroma or remote SQL access is
possible only through separately acknowledged execution functions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Dict, List, Optional

from database.generate_pilot_financial_pdfs import (
    LIVE_PDF_ROOT,
    EVIDENCE_VERSION,
    PILOT_DATASET_ID,
    REPORTING_PERIODS,
    STAGED_PDF_ROOT,
    ReportingPeriod,
    staging_source_tables,
)


STAGED_FINANCIAL_DIRECTORY = STAGED_PDF_ROOT / PILOT_DATASET_ID / EVIDENCE_VERSION / "01_financial"
LIVE_PDF_DIRECTORY = LIVE_PDF_ROOT
LIVE_CHROMA_DIRECTORY = STAGED_PDF_ROOT.parent / "chroma_db"
LIVE_COLLECTION_NAME = "nexusiq_docs"

PILOT_CHROMA_DIRECTORY = STAGED_PDF_ROOT.parent / "chroma_staging" / PILOT_DATASET_ID / EVIDENCE_VERSION / "financial_documents"
PILOT_COLLECTION_NAME = "nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2"
PILOT_STAGING_SALES_TABLE = staging_source_tables(PILOT_DATASET_ID)[0]

INGESTION_CONFIRMATION = "INGEST_PILOT_PDFS_TO_ISOLATED_STAGING_ONLY"
VALIDATION_CONFIRMATION = "VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY"
INDEX_VALIDATION_CONFIRMATION = "VALIDATE_PILOT_STAGING_INDEX_AGAINST_STAGING_SQL_ONLY"


class PilotDocumentPhaseError(RuntimeError):
    """Raised when a pilot document safety boundary or alignment check fails."""


def _is_configured_path(path: Path, expected: Path) -> bool:
    return path.resolve() == expected.resolve()


def _within(path: Path, parent: Path) -> bool:
    resolved = path.resolve()
    parent_resolved = parent.resolve()
    return resolved == parent_resolved or parent_resolved in resolved.parents


def _validate_pdf_directory(pdf_directory: Path) -> Path:
    directory = Path(pdf_directory)
    if _within(directory, LIVE_PDF_DIRECTORY):
        raise PilotDocumentPhaseError("Pilot document operations cannot read the live data/pdfs archive.")
    if not _is_configured_path(directory, STAGED_FINANCIAL_DIRECTORY):
        raise PilotDocumentPhaseError(
            "Pilot document operations are locked to "
            "data/pdfs_staging/enterprise_pilot_v1/validated_v2/01_financial."
        )
    return directory


def _validate_rag_destination(chroma_directory: Path, collection_name: str) -> Path:
    directory = Path(chroma_directory)
    if _within(directory, LIVE_CHROMA_DIRECTORY) or collection_name == LIVE_COLLECTION_NAME:
        raise PilotDocumentPhaseError("Pilot ingestion cannot use the live Chroma path or collection.")
    if not _is_configured_path(directory, PILOT_CHROMA_DIRECTORY):
        raise PilotDocumentPhaseError(
            "Pilot ingestion destination is locked to "
            "data/chroma_staging/enterprise_pilot_v1/validated_v2/financial_documents."
        )
    if collection_name != PILOT_COLLECTION_NAME:
        raise PilotDocumentPhaseError(
            f"Pilot ingestion collection is locked to {PILOT_COLLECTION_NAME!r}."
        )
    return directory


def _source_paths(pdf_directory: Path) -> List[Path]:
    return [pdf_directory / period.filename for period in REPORTING_PERIODS]


def _require_expected_documents(pdf_directory: Path) -> List[Path]:
    expected_paths = _source_paths(pdf_directory)
    missing = [str(path) for path in expected_paths if not path.is_file()]
    if missing:
        raise PilotDocumentPhaseError("Missing staged pilot PDFs: " + ", ".join(missing))

    expected_names = {period.filename for period in REPORTING_PERIODS}
    observed_names = {path.name for path in pdf_directory.glob("*.pdf")}
    unexpected = sorted(observed_names - expected_names)
    if unexpected:
        raise PilotDocumentPhaseError(
            "Unexpected staged PDF files are outside the five-period pilot contract: "
            + ", ".join(unexpected)
        )
    if any("2024" in path.name for path in expected_paths):
        raise PilotDocumentPhaseError("Protected 2024/live PDFs cannot enter the pilot document phase.")
    return expected_paths


def build_ingestion_plan(
    *,
    pdf_directory: Optional[Path] = None,
    chroma_directory: Optional[Path] = None,
    collection_name: str = PILOT_COLLECTION_NAME,
) -> Dict[str, object]:
    """Return an ingestion dry-run without opening Chroma or a database."""
    source = _validate_pdf_directory(pdf_directory or STAGED_FINANCIAL_DIRECTORY)
    destination = _validate_rag_destination(chroma_directory or PILOT_CHROMA_DIRECTORY, collection_name)
    return {
        "action": "pilot_document_ingestion",
        "dry_run": True,
        "dataset_id": PILOT_DATASET_ID,
        "pdf_directory": str(source),
        "pdfs": [str(path) for path in _source_paths(source)],
        "chroma_directory": str(destination),
        "collection": collection_name,
        "write_policy": "validated_pdfs_only_atomic_isolated_staging_chroma_publish",
        "protected_policy": "never_read_live_or_2024_financial_pdfs",
    }


def _require_ingestion_confirmation(execute: bool, confirmation: Optional[str]) -> None:
    if not execute or confirmation != INGESTION_CONFIRMATION:
        raise PilotDocumentPhaseError(
            "Pilot Chroma ingestion is disabled by default. To write only the isolated staging index, "
            f"provide --execute --confirm-staging-only {INGESTION_CONFIRMATION}."
        )


def execute_ingestion(
    *,
    pdf_directory: Optional[Path] = None,
    chroma_directory: Optional[Path] = None,
    collection_name: str = PILOT_COLLECTION_NAME,
    execute: bool = False,
    confirmation: Optional[str] = None,
    validation_confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
    pipeline_factory=None,
    connection_factory=None,
    text_loader: Optional[Callable[[Path], str]] = None,
) -> Dict[str, object]:
    """Validate PDFs against staging SQL, then atomically publish an isolated index."""
    plan = build_ingestion_plan(
        pdf_directory=pdf_directory,
        chroma_directory=chroma_directory,
        collection_name=collection_name,
    )
    _require_ingestion_confirmation(execute, confirmation)
    pdf_paths = _require_expected_documents(Path(str(plan["pdf_directory"])))
    validation = validate_pdf_sql_alignment(
        pdf_directory=Path(str(plan["pdf_directory"])),
        execute_remote=True,
        confirmation=validation_confirmation,
        database_url=database_url,
        text_loader=text_loader,
        connection_factory=connection_factory,
    )
    destination = Path(str(plan["chroma_directory"]))
    if destination.exists():
        raise PilotDocumentPhaseError(
            "Refusing to overwrite an existing staged pilot index; use a new evidence version after review."
        )

    if pipeline_factory is None:
        from database.setup_rag_pipeline import RAGPipelineSetup

        pipeline_factory = RAGPipelineSetup

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(tempfile.mkdtemp(prefix=".pilot_chroma_publish_", dir=str(destination.parent)))
    ingested = []
    total_chunks = 0
    try:
        pipeline = pipeline_factory(
            pdf_base_dir=Path(str(plan["pdf_directory"])),
            chroma_dir=temporary_directory,
            categories=["01_financial"],
            collection_name=str(plan["collection"]),
            reset_collection=False,
        )
        for pdf_path in pdf_paths:
            pages_data, metadata = pipeline.extract_text_from_pdf(pdf_path)
            if not pages_data:
                raise PilotDocumentPhaseError(f"No text extracted from staged pilot PDF: {pdf_path}")
            chunks = pipeline.chunk_text(pages_data, metadata)
            if not chunks:
                raise PilotDocumentPhaseError(f"No indexable chunks extracted from staged pilot PDF: {pdf_path}")
            pipeline.embed_and_store(chunks)
            ingested.append(str(pdf_path))
            total_chunks += len(chunks)
        temporary_directory.replace(destination)
    except Exception:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    return {
        **plan,
        "dry_run": False,
        "pdf_sql_validation": validation["aligned"],
        "ingested_pdfs": ingested,
        "chunks_created": total_chunks,
    }


def build_alignment_plan(*, pdf_directory: Optional[Path] = None) -> Dict[str, object]:
    """Return the local-only alignment work definition without a SQL connection."""
    source = _validate_pdf_directory(pdf_directory or STAGED_FINANCIAL_DIRECTORY)
    return {
        "action": "pilot_pdf_sql_alignment",
        "dry_run": True,
        "dataset_id": PILOT_DATASET_ID,
        "pdf_directory": str(source),
        "pdfs": [str(path) for path in _source_paths(source)],
        "periods": [period.as_dict() for period in REPORTING_PERIODS],
        "sql_query": render_alignment_query(),
        "source_policy": "read_pilot_rows_from_direct_staging_sales_table_only",
        "protected_policy": "never_read_live_or_2024_financial_pdfs",
    }


def build_index_alignment_plan(
    *,
    chroma_directory: Optional[Path] = None,
    collection_name: str = PILOT_COLLECTION_NAME,
) -> Dict[str, object]:
    """Return the staged-index alignment work definition without opening Chroma or SQL."""
    destination = _validate_rag_destination(chroma_directory or PILOT_CHROMA_DIRECTORY, collection_name)
    return {
        "action": "pilot_staged_index_sql_alignment",
        "dry_run": True,
        "dataset_id": PILOT_DATASET_ID,
        "chroma_directory": str(destination),
        "collection": collection_name,
        "filenames": [period.filename for period in REPORTING_PERIODS],
        "periods": [period.as_dict() for period in REPORTING_PERIODS],
        "sql_query": render_alignment_query(),
        "index_policy": "read_isolated_staging_chroma_collection_only",
        "source_policy": "read_pilot_rows_from_direct_staging_sales_table_only",
        "protected_policy": "never_read_live_chroma_or_2024_financial_documents",
    }


def render_alignment_query() -> str:
    """Render a read-only metric query against the generator's direct staging source."""
    return (
        "SELECT COUNT(*) AS transactions, "
        "COALESCE(ROUND(SUM(total_amount)::numeric, 2), 0) AS revenue "
        f"FROM {PILOT_STAGING_SALES_TABLE} "
        "WHERE dataset_id = %s AND transaction_date >= %s AND transaction_date < %s"
    )


def _read_pdf_text(pdf_path: Path) -> str:
    import pypdf

    with pdf_path.open("rb") as handle:
        reader = pypdf.PdfReader(handle)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_pdf_summary_metrics(
    pdf_path: Path,
    period: ReportingPeriod,
    *,
    text_loader: Optional[Callable[[Path], str]] = None,
) -> Dict[str, object]:
    """Extract the executive-summary transaction and revenue values from one staged PDF."""
    text = (text_loader or _read_pdf_text)(Path(pdf_path))
    return _extract_summary_metrics(text, period, str(pdf_path))


def _extract_summary_metrics(text: str, period: ReportingPeriod, source: str) -> Dict[str, object]:
    """Extract period totals from staged PDF text or staged index content."""
    pattern = re.compile(
        rf"{re.escape(period.label)}\s+generated sales contain\s+"
        r"(?P<transactions>[\d,]+)\s+transactions\s+with total revenue of\s+"
        r"\$(?P<revenue>[\d,]+\.\d{2})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise PilotDocumentPhaseError(f"Could not extract staged summary metrics for {period.label}: {source}")
    try:
        revenue = Decimal(match.group("revenue").replace(",", ""))
    except InvalidOperation as exc:
        raise PilotDocumentPhaseError(f"Invalid revenue in staged pilot content: {source}") from exc
    return {
        "label": period.label,
        "transactions": int(match.group("transactions").replace(",", "")),
        "revenue": revenue.quantize(Decimal("0.01")),
    }


def _require_validation_confirmation(execute_remote: bool, confirmation: Optional[str]) -> None:
    if not execute_remote or confirmation != VALIDATION_CONFIRMATION:
        raise PilotDocumentPhaseError(
            "Remote staging SQL validation is disabled by default. To read only staging SQL aggregates, "
            f"provide --execute-remote --confirm-staging-only {VALIDATION_CONFIRMATION}."
        )


def _require_index_validation_confirmation(execute_remote: bool, confirmation: Optional[str]) -> None:
    if not execute_remote or confirmation != INDEX_VALIDATION_CONFIRMATION:
        raise PilotDocumentPhaseError(
            "Staged Chroma/SQL validation is disabled by default. To read only the isolated staging index "
            "and staging SQL aggregates, provide --execute-remote --confirm-staging-only "
            f"{INDEX_VALIDATION_CONFIRMATION}."
        )


def _compare_metrics_to_staging_sql(
    *,
    plan: Dict[str, object],
    metrics_by_period: Dict[str, Dict[str, object]],
    database_url: Optional[str],
    connection_factory,
    evidence_prefix: str,
) -> Dict[str, object]:
    database_url = database_url or os.getenv("NEXUSIQ_FINANCIAL_DB_URL")
    if database_url is None:
        from config.settings import settings

        database_url = settings.database_url
    if not database_url:
        raise PilotDocumentPhaseError("Set DATABASE_URL or NEXUSIQ_FINANCIAL_DB_URL for alignment validation.")
    if connection_factory is None:
        import psycopg2

        connection_factory = psycopg2.connect

    query = str(plan["sql_query"])
    connection = connection_factory(database_url)
    comparisons = []
    mismatches = []
    try:
        cursor = connection.cursor()
        for period in REPORTING_PERIODS:
            parameters = (PILOT_DATASET_ID, period.start_date, period.end_date_exclusive)
            cursor.execute(query, parameters)
            row = cursor.fetchone()
            if row is None:
                raise PilotDocumentPhaseError(f"No staging SQL aggregate returned for {period.label}.")
            sql_transactions = int(row[0])
            sql_revenue = Decimal(str(row[1])).quantize(Decimal("0.01"))
            document = metrics_by_period[period.label]
            aligned = (
                sql_transactions == document["transactions"]
                and sql_revenue == document["revenue"]
            )
            comparison = {
                "label": period.label,
                f"{evidence_prefix}_transactions": document["transactions"],
                "sql_transactions": sql_transactions,
                f"{evidence_prefix}_revenue": str(document["revenue"]),
                "sql_revenue": str(sql_revenue),
                "aligned": aligned,
            }
            comparisons.append(comparison)
            if not aligned:
                mismatches.append(comparison)
    finally:
        connection.close()

    if mismatches:
        labels = ", ".join(item["label"] for item in mismatches)
        raise PilotDocumentPhaseError(f"Staged {evidence_prefix}/SQL metric mismatch for: {labels}.")
    return {**plan, "dry_run": False, "aligned": True, "comparisons": comparisons}


def validate_pdf_sql_alignment(
    *,
    pdf_directory: Optional[Path] = None,
    execute_remote: bool = False,
    confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
    text_loader: Optional[Callable[[Path], str]] = None,
    connection_factory=None,
) -> Dict[str, object]:
    """Compare every published pilot financial fact with direct staging SQL aggregates."""
    plan = build_alignment_plan(pdf_directory=pdf_directory)
    _require_validation_confirmation(execute_remote, confirmation)
    pdf_paths = _require_expected_documents(Path(str(plan["pdf_directory"])))
    pdf_metrics = {
        period.label: extract_pdf_summary_metrics(path, period, text_loader=text_loader)
        for period, path in zip(REPORTING_PERIODS, pdf_paths)
    }
    return _compare_metrics_to_staging_sql(
        plan=plan,
        metrics_by_period=pdf_metrics,
        database_url=database_url,
        connection_factory=connection_factory,
        evidence_prefix="pdf",
    )


def validate_index_sql_alignment(
    *,
    chroma_directory: Optional[Path] = None,
    collection_name: str = PILOT_COLLECTION_NAME,
    execute_remote: bool = False,
    confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
    collection_factory=None,
    connection_factory=None,
) -> Dict[str, object]:
    """Compare every indexed pilot financial fact with direct staging SQL aggregates."""
    plan = build_index_alignment_plan(
        chroma_directory=chroma_directory,
        collection_name=collection_name,
    )
    _require_index_validation_confirmation(execute_remote, confirmation)
    if collection_factory is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        def collection_factory(directory: Path, name: str):
            client = chromadb.PersistentClient(
                path=str(directory),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            return client.get_collection(name=name)

    collection = collection_factory(Path(str(plan["chroma_directory"])), str(plan["collection"]))
    index_metrics = {}
    for period in REPORTING_PERIODS:
        result = collection.get(
            where={"filename": period.filename},
            include=["documents", "metadatas"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        if not documents:
            raise PilotDocumentPhaseError(f"Missing staged index content for {period.filename}.")
        if any(metadata.get("filename") != period.filename for metadata in metadatas):
            raise PilotDocumentPhaseError(f"Unexpected staged index metadata returned for {period.filename}.")
        content = "\n".join(str(document) for document in documents)
        index_metrics[period.label] = _extract_summary_metrics(
            content,
            period,
            f"{plan['collection']}:{period.filename}",
        )
    return _compare_metrics_to_staging_sql(
        plan=plan,
        metrics_by_period=index_metrics,
        database_url=database_url,
        connection_factory=connection_factory,
        evidence_prefix="index",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated pilot document ingestion and PDF/SQL validation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan-ingestion")
    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--execute", action="store_true")
    ingest.add_argument("--confirm-staging-only")
    ingest.add_argument("--confirm-pdf-validation")
    ingest.add_argument("--database-url")
    subparsers.add_parser("plan-alignment")
    validate = subparsers.add_parser("validate-alignment")
    validate.add_argument("--execute-remote", action="store_true")
    validate.add_argument("--confirm-staging-only")
    validate.add_argument("--database-url")
    subparsers.add_parser("plan-index-alignment")
    validate_index = subparsers.add_parser("validate-index-alignment")
    validate_index.add_argument("--execute-remote", action="store_true")
    validate_index.add_argument("--confirm-staging-only")
    validate_index.add_argument("--database-url")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "plan-ingestion":
        result = build_ingestion_plan()
    elif args.command == "ingest":
        result = execute_ingestion(
            execute=args.execute,
            confirmation=args.confirm_staging_only,
            validation_confirmation=args.confirm_pdf_validation,
            database_url=args.database_url,
        )
    elif args.command == "plan-alignment":
        result = build_alignment_plan()
    elif args.command == "validate-alignment":
        result = validate_pdf_sql_alignment(
            execute_remote=args.execute_remote,
            confirmation=args.confirm_staging_only,
            database_url=args.database_url,
        )
    elif args.command == "plan-index-alignment":
        result = build_index_alignment_plan()
    elif args.command == "validate-index-alignment":
        result = validate_index_sql_alignment(
            execute_remote=args.execute_remote,
            confirmation=args.confirm_staging_only,
            database_url=args.database_url,
        )
    else:
        raise PilotDocumentPhaseError(f"Unsupported command: {args.command}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
