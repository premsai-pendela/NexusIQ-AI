"""
NexusIQ ingestion orchestration.

This module wraps the existing synthetic SQL generator and PDF-to-Chroma
pipeline with production-minded commands: status, dry-run, SQL rebuild,
RAG rebuild, and runtime cache cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config.company_data import NEXUSIQ_METRICS
from config.settings import settings
from database.setup import init_database
from database.setup_rag_pipeline import CATEGORIES, CHROMA_DIR, PDF_BASE_DIR, RAGPipelineSetup, bump_ingestion_version


CACHE_FILES = (
    Path("data/web_cache.json"),
    Path("data/quota_tracker.json"),
)

RAG_MANIFEST_FILE = CHROMA_DIR / "pdf_manifest.json"


@dataclass
class PdfInventory:
    base_dir: str
    total_pdfs: int
    by_category: Dict[str, int]
    missing_categories: List[str]


@dataclass
class SqlInventory:
    database_url: str
    available: bool
    rows: Optional[int] = None
    revenue: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ChromaInventory:
    persist_directory: str
    available: bool
    collection: str = "nexusiq_docs"
    documents: Optional[int] = None
    error: Optional[str] = None


@dataclass
class IngestionStatus:
    sql: SqlInventory
    pdfs: PdfInventory
    chroma: ChromaInventory
    caches: Dict[str, bool]


def discover_pdfs(base_dir: Path = PDF_BASE_DIR, categories: Iterable[str] = CATEGORIES) -> PdfInventory:
    """Return PDF counts by expected category without reading document contents."""
    base_dir = Path(base_dir)
    by_category: Dict[str, int] = {}
    missing_categories: List[str] = []

    for category in categories:
        category_dir = base_dir / category
        if not category_dir.exists():
            by_category[category] = 0
            missing_categories.append(category)
            continue
        by_category[category] = len(sorted(category_dir.glob("*.pdf")))

    return PdfInventory(
        base_dir=str(base_dir),
        total_pdfs=sum(by_category.values()),
        by_category=by_category,
        missing_categories=missing_categories,
    )


def inspect_sql(database_url: str = settings.database_url) -> SqlInventory:
    """Inspect the structured sales table, reporting errors instead of raising."""
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS rows, SUM(total_amount) AS revenue FROM sales_transactions")
            ).fetchone()
        engine.dispose()
        return SqlInventory(
            database_url=redact_database_url(database_url),
            available=True,
            rows=int(row[0] or 0),
            revenue=float(row[1] or 0),
        )
    except Exception as exc:
        return SqlInventory(database_url=redact_database_url(database_url), available=False, error=str(exc))


def redact_database_url(database_url: str) -> str:
    """Return a display-safe database URL for CLI output."""
    try:
        url = make_url(database_url)
        if url.host and (url.username or url.password):
            url = url.set(username="redacted", password="redacted")
        return url.render_as_string(hide_password=True)
    except Exception:
        return "[unparseable database url]"


def inspect_chroma(
    persist_directory: Path = CHROMA_DIR,
    collection_name: str = "nexusiq_docs",
) -> ChromaInventory:
    """Inspect the Chroma collection without mutating the vector store."""
    persist_directory = Path(persist_directory)
    if not persist_directory.exists():
        return ChromaInventory(
            persist_directory=str(persist_directory),
            available=False,
            collection=collection_name,
            error="Persist directory does not exist",
        )

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        collection = client.get_collection(collection_name)
        return ChromaInventory(
            persist_directory=str(persist_directory),
            available=True,
            collection=collection_name,
            documents=collection.count(),
        )
    except Exception as exc:
        return ChromaInventory(
            persist_directory=str(persist_directory),
            available=False,
            collection=collection_name,
            error=str(exc),
        )


def build_status() -> IngestionStatus:
    """Collect the current ingestion state across SQL, PDFs, Chroma, and caches."""
    return IngestionStatus(
        sql=inspect_sql(),
        pdfs=discover_pdfs(),
        chroma=inspect_chroma(),
        caches={str(path): path.exists() for path in CACHE_FILES},
    )


def print_json(payload) -> None:
    print(json.dumps(asdict(payload) if hasattr(payload, "__dataclass_fields__") else payload, indent=2))


def expected_sql_targets() -> Dict[str, float]:
    return {
        "expected_rows": NEXUSIQ_METRICS["ANNUAL_2024"]["total_transactions"],
        "expected_revenue": NEXUSIQ_METRICS["ANNUAL_2024"]["total_revenue"],
    }


def hash_file(path: Path) -> str:
    """Return a stable SHA-256 hash for change detection."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_manifest_key(pdf_path: Path, base_dir: Optional[Path] = None) -> str:
    """Return a stable manifest key, relative to the PDF base dir when possible."""
    pdf_path = Path(pdf_path)
    base_dir = Path(base_dir or PDF_BASE_DIR)
    try:
        return str(pdf_path.relative_to(base_dir))
    except ValueError:
        return str(pdf_path)


def pdf_category(pdf_path: Path, base_dir: Optional[Path] = None) -> str:
    """Infer the category label from the PDF path."""
    pdf_path = Path(pdf_path)
    base_dir = Path(base_dir or PDF_BASE_DIR)
    try:
        relative = pdf_path.relative_to(base_dir)
        return relative.parts[0] if len(relative.parts) > 1 else pdf_path.parent.name
    except ValueError:
        return pdf_path.parent.name


def list_source_pdfs(base_dir: Optional[Path] = None, categories: Optional[Iterable[str]] = None) -> List[Path]:
    """List PDFs under the expected source categories."""
    base_dir = Path(base_dir or PDF_BASE_DIR)
    categories = categories or CATEGORIES
    files: List[Path] = []
    for category in categories:
        category_dir = base_dir / category
        if category_dir.exists():
            files.extend(sorted(category_dir.glob("*.pdf")))
    return sorted(files)


def build_pdf_manifest_entry(pdf_path: Path, base_dir: Optional[Path] = None) -> Dict[str, object]:
    """Build one manifest record for a source PDF."""
    pdf_path = Path(pdf_path)
    base_dir = Path(base_dir or PDF_BASE_DIR)
    return {
        "path": pdf_manifest_key(pdf_path, base_dir),
        "filename": pdf_path.name,
        "category": pdf_category(pdf_path, base_dir),
        "sha256": hash_file(pdf_path),
        "size_bytes": pdf_path.stat().st_size,
    }


def load_rag_manifest(path: Optional[Path] = None) -> Dict[str, Dict[str, object]]:
    """Load the PDF ingestion manifest."""
    path = Path(path or RAG_MANIFEST_FILE)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}

    if isinstance(payload, dict) and isinstance(payload.get("pdfs"), dict):
        return payload["pdfs"]
    if isinstance(payload, dict):
        return payload
    return {}


def save_rag_manifest(manifest: Dict[str, Dict[str, object]], path: Optional[Path] = None) -> None:
    """Persist the PDF ingestion manifest."""
    path = Path(path or RAG_MANIFEST_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pdfs": manifest}, indent=2, sort_keys=True))


def update_manifest_entry(
    pdf_path: Path,
    category: str,
    manifest_path: Optional[Path] = None,
    base_dir: Path = PDF_BASE_DIR,
) -> None:
    """Update manifest state after a successful single-PDF ingest."""
    manifest = load_rag_manifest(manifest_path)
    entry = build_pdf_manifest_entry(pdf_path, base_dir)
    entry["category"] = category
    manifest[entry["path"]] = entry
    save_rag_manifest(manifest, manifest_path)


def _index_pdf_with_pipeline(pipeline: RAGPipelineSetup, pdf_path: Path, category: str) -> Dict[str, object]:
    """Delete stale chunks for one PDF, then embed and upsert its fresh chunks."""
    pages_data, metadata = pipeline.extract_text_from_pdf(pdf_path)
    if not pages_data:
        return {"error": "No text extracted from PDF", "pdf": str(pdf_path)}

    pipeline.collection.delete(where={"filename": pdf_path.name})

    metadata["category"] = category
    chunks = pipeline.chunk_text(pages_data, metadata)
    pipeline.embed_and_store(chunks)

    return {
        "pdf": str(pdf_path),
        "category": category,
        "chunks_added": len(chunks),
    }


def rebuild_sql(dry_run: bool = False) -> Dict[str, object]:
    """Rebuild the SQL tables from the company-data source of truth."""
    if dry_run:
        return {
            "dry_run": True,
            "action": "rebuild_sql",
            **expected_sql_targets(),
            "database_url": redact_database_url(settings.database_url),
        }

    init_database()
    from database.generate_aligned_data import AlignedDataGenerator

    generator = AlignedDataGenerator()
    generator.clear_existing_data()

    all_transactions = []
    for quarter in ["Q1_2024", "Q2_2024", "Q3_2024", "Q4_2024"]:
        all_transactions.extend(generator.generate_quarter_transactions(quarter))

    generator.insert_transactions(all_transactions)
    generator.verify_alignment()

    return {
        "dry_run": False,
        "action": "rebuild_sql",
        "rows_inserted": len(all_transactions),
        "revenue_inserted": round(sum(t["total_amount"] for t in all_transactions), 2),
    }


def rebuild_rag(dry_run: bool = False) -> Dict[str, object]:
    """Rebuild the Chroma vector index from PDFs."""
    pdfs = discover_pdfs()
    if dry_run:
        return {
            "dry_run": True,
            "action": "rebuild_rag",
            "pdfs": asdict(pdfs),
            "persist_directory": str(CHROMA_DIR),
            "collection": "nexusiq_docs",
        }

    pipeline = RAGPipelineSetup(
        pdf_base_dir=PDF_BASE_DIR,
        chroma_dir=CHROMA_DIR,
        categories=CATEGORIES,
        collection_name="nexusiq_docs",
        reset_collection=True,
    )
    pipeline.process_all_pdfs()
    manifest = {
        pdf_manifest_key(pdf_path): build_pdf_manifest_entry(pdf_path)
        for pdf_path in list_source_pdfs()
    }
    save_rag_manifest(manifest)
    version = bump_ingestion_version()
    return {
        "dry_run": False,
        "action": "rebuild_rag",
        "pdfs_processed": pipeline.stats["pdfs_processed"],
        "chunks_created": pipeline.stats["chunks_created"],
        "collection_documents": pipeline.collection.count(),
        "ingestion_version": version,
    }


def add_single_pdf(pdf_path: Path, category: str, dry_run: bool = False) -> Dict[str, object]:
    """Incrementally add one PDF to the Chroma collection without wiping existing documents."""
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        return {"error": f"File not found: {pdf_path}", "action": "add_pdf"}

    if dry_run:
        return {
            "dry_run": True,
            "action": "add_pdf",
            "pdf": str(pdf_path),
            "category": category,
            "persist_directory": str(CHROMA_DIR),
            "collection": "nexusiq_docs",
        }

    pipeline = RAGPipelineSetup(
        pdf_base_dir=pdf_path.parent,
        chroma_dir=CHROMA_DIR,
        categories=[],
        collection_name="nexusiq_docs",
        reset_collection=False,
    )

    indexed = _index_pdf_with_pipeline(pipeline, pdf_path, category)
    if "error" in indexed:
        return {"error": indexed["error"], "action": "add_pdf", "pdf": str(pdf_path)}

    update_manifest_entry(pdf_path, category)
    version = bump_ingestion_version()

    return {
        "dry_run": False,
        "action": "add_pdf",
        "pdf": str(pdf_path),
        "category": category,
        "chunks_added": indexed["chunks_added"],
        "collection_documents": pipeline.collection.count(),
        "ingestion_version": version,
    }


def plan_rag_sync() -> Dict[str, object]:
    """Compare source PDFs against the manifest and return sync work."""
    current = {
        pdf_manifest_key(pdf_path): build_pdf_manifest_entry(pdf_path)
        for pdf_path in list_source_pdfs()
    }
    previous = load_rag_manifest()

    added = sorted(key for key in current if key not in previous)
    removed = sorted(key for key in previous if key not in current)
    changed = sorted(
        key
        for key in current
        if key in previous and current[key].get("sha256") != previous[key].get("sha256")
    )
    unchanged = sorted(
        key
        for key in current
        if key in previous and current[key].get("sha256") == previous[key].get("sha256")
    )

    return {
        "current": current,
        "previous": previous,
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": unchanged,
    }


def sync_rag(dry_run: bool = False) -> Dict[str, object]:
    """Smart RAG sync: update only new/changed/deleted PDFs."""
    plan = plan_rag_sync()
    work_count = len(plan["added"]) + len(plan["changed"]) + len(plan["removed"])

    if dry_run:
        return {
            "dry_run": True,
            "action": "sync_rag",
            "added": plan["added"],
            "changed": plan["changed"],
            "removed": plan["removed"],
            "unchanged_count": len(plan["unchanged"]),
            "will_bump_version": work_count > 0,
        }

    if work_count == 0:
        return {
            "dry_run": False,
            "action": "sync_rag",
            "added": [],
            "changed": [],
            "removed": [],
            "unchanged_count": len(plan["unchanged"]),
            "updated_pdfs": [],
            "deleted_pdfs": [],
            "ingestion_version": None,
            "message": "RAG index already matches source PDFs",
        }

    pipeline = RAGPipelineSetup(
        pdf_base_dir=PDF_BASE_DIR,
        chroma_dir=CHROMA_DIR,
        categories=[],
        collection_name="nexusiq_docs",
        reset_collection=False,
    )

    updated = []
    for key in plan["added"] + plan["changed"]:
        entry = plan["current"][key]
        pdf_path = PDF_BASE_DIR / entry["path"]
        indexed = _index_pdf_with_pipeline(pipeline, pdf_path, entry["category"])
        if "error" in indexed:
            return {"error": indexed["error"], "action": "sync_rag", "pdf": str(pdf_path)}
        updated.append(indexed)

    deleted = []
    for key in plan["removed"]:
        entry = plan["previous"][key]
        pipeline.collection.delete(where={"filename": entry["filename"]})
        deleted.append(entry["path"])

    save_rag_manifest(plan["current"])
    version = bump_ingestion_version()

    return {
        "dry_run": False,
        "action": "sync_rag",
        "added": plan["added"],
        "changed": plan["changed"],
        "removed": plan["removed"],
        "unchanged_count": len(plan["unchanged"]),
        "updated_pdfs": updated,
        "deleted_pdfs": deleted,
        "collection_documents": pipeline.collection.count(),
        "ingestion_version": version,
    }


def clear_runtime_caches(dry_run: bool = False) -> Dict[str, object]:
    """Remove local runtime cache files that should not be committed."""
    removed = []
    present = []
    for path in CACHE_FILES:
        if path.exists():
            present.append(str(path))
            if not dry_run:
                path.unlink()
                removed.append(str(path))

    return {
        "dry_run": dry_run,
        "action": "clear_runtime_caches",
        "present": present,
        "removed": removed,
    }


def refresh_all(dry_run: bool = False) -> Dict[str, object]:
    """Refresh SQL data and the RAG index in dependency order."""
    return {
        "dry_run": dry_run,
        "sql": rebuild_sql(dry_run=dry_run),
        "rag": rebuild_rag(dry_run=dry_run),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NexusIQ ingestion pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Inspect SQL, PDFs, Chroma, and runtime caches")

    for name in ("rebuild-sql", "rebuild-rag", "sync-rag", "refresh-all", "clear-caches"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--dry-run", action="store_true", help="Print intended work without writing files")

    add_pdf_parser = subparsers.add_parser("add-pdf", help="Incrementally add one PDF to the vector index")
    add_pdf_parser.add_argument("--path", required=True, help="Path to the PDF file")
    add_pdf_parser.add_argument("--category", required=True, help="Category label for the document")
    add_pdf_parser.add_argument("--dry-run", action="store_true", help="Print intended work without writing files")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "status":
        print_json(build_status())
    elif args.command == "rebuild-sql":
        print_json(rebuild_sql(dry_run=args.dry_run))
    elif args.command == "rebuild-rag":
        print_json(rebuild_rag(dry_run=args.dry_run))
    elif args.command == "sync-rag":
        print_json(sync_rag(dry_run=args.dry_run))
    elif args.command == "refresh-all":
        print_json(refresh_all(dry_run=args.dry_run))
    elif args.command == "clear-caches":
        print_json(clear_runtime_caches(dry_run=args.dry_run))
    elif args.command == "add-pdf":
        result = add_single_pdf(Path(args.path), args.category, dry_run=args.dry_run)
        print_json(result)
        if not args.dry_run and "error" not in result:
            from agents.rag_agent import get_rag_agent
            get_rag_agent().refresh_bm25()
            print("BM25 index refreshed.")
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
