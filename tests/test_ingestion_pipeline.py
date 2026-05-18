import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import create_engine, text

from database.ingestion_pipeline import (
    add_single_pdf,
    clear_runtime_caches,
    discover_pdfs,
    expected_sql_targets,
    inspect_sql,
    redact_database_url,
    rebuild_rag,
    rebuild_sql,
    save_rag_manifest,
    sync_rag,
)
from database.setup_rag_pipeline import INGESTION_VERSION_FILE, bump_ingestion_version


class IngestionPipelineTests(unittest.TestCase):
    def test_discover_pdfs_counts_expected_categories(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "financial").mkdir()
            (base / "financial" / "report.pdf").write_bytes(b"%PDF-1.4")
            (base / "financial" / "notes.txt").write_text("ignore me")

            inventory = discover_pdfs(base, ["financial", "missing"])

        self.assertEqual(inventory.total_pdfs, 1)
        self.assertEqual(inventory.by_category["financial"], 1)
        self.assertEqual(inventory.by_category["missing"], 0)
        self.assertEqual(inventory.missing_categories, ["missing"])

    def test_inspect_sql_reports_rows_and_revenue_for_sqlite(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sales.db"
            engine = create_engine(f"sqlite:///{db_path}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE sales_transactions (total_amount REAL)"))
                conn.execute(text("INSERT INTO sales_transactions VALUES (10.50), (20.25)"))
            engine.dispose()

            inventory = inspect_sql(f"sqlite:///{db_path}")

        self.assertTrue(inventory.available)
        self.assertEqual(inventory.rows, 2)
        self.assertAlmostEqual(inventory.revenue, 30.75)

    def test_sql_dry_run_uses_company_targets_without_writing(self):
        result = rebuild_sql(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "rebuild_sql")
        self.assertEqual(result["expected_rows"], expected_sql_targets()["expected_rows"])
        self.assertIn("redacted", result["database_url"])

    def test_redact_database_url_hides_credentials(self):
        url = "postgresql://user:secret@example.com:5432/postgres"

        redacted = redact_database_url(url)

        self.assertNotIn("user", redacted)
        self.assertNotIn("secret", redacted)
        self.assertIn("redacted", redacted)

    def test_rag_dry_run_reports_pdf_inventory_without_chroma_write(self):
        result = rebuild_rag(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "rebuild_rag")
        self.assertIn("pdfs", result)
        self.assertIn("collection", result)

    def test_clear_caches_dry_run_does_not_delete_files(self):
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "web_cache.json"
            cache_path.write_text(json.dumps({"cached": True}))

            with patch("database.ingestion_pipeline.CACHE_FILES", (cache_path,)):
                result = clear_runtime_caches(dry_run=True)

            self.assertTrue(cache_path.exists())
            self.assertEqual(result["present"], [str(cache_path)])
            self.assertEqual(result["removed"], [])

    def test_add_single_pdf_dry_run_does_not_embed(self):
        with TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "report.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fake")

            result = add_single_pdf(pdf_path, category="financial", dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "add_pdf")
        self.assertEqual(result["pdf"], str(pdf_path))
        self.assertEqual(result["category"], "financial")
        self.assertIn("collection", result)

    def test_add_single_pdf_dry_run_missing_file_returns_error(self):
        result = add_single_pdf(Path("/nonexistent/file.pdf"), category="financial", dry_run=True)

        self.assertIn("error", result)
        self.assertEqual(result["action"], "add_pdf")

    def test_rebuild_rag_dry_run_does_not_bump_version(self):
        with TemporaryDirectory() as tmp:
            version_file = Path(tmp) / "ingestion_version.json"
            version_file.write_text(json.dumps({"version": 5}))

            with patch("database.setup_rag_pipeline.INGESTION_VERSION_FILE", version_file):
                result = rebuild_rag(dry_run=True)

            self.assertTrue(result["dry_run"])
            # dry-run must not write the version file
            self.assertEqual(json.loads(version_file.read_text())["version"], 5)

    def test_bump_ingestion_version_increments_from_zero(self):
        with TemporaryDirectory() as tmp:
            version_file = Path(tmp) / "ingestion_version.json"

            with patch("database.setup_rag_pipeline.INGESTION_VERSION_FILE", version_file):
                v1 = bump_ingestion_version()
                v2 = bump_ingestion_version()

            self.assertEqual(v1, 1)
            self.assertEqual(v2, 2)

    def test_sync_rag_dry_run_reports_added_changed_and_removed(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "pdfs"
            financial = base / "01_financial"
            financial.mkdir(parents=True)
            unchanged = financial / "unchanged.pdf"
            changed = financial / "changed.pdf"
            added = financial / "added.pdf"
            unchanged.write_bytes(b"same")
            changed.write_bytes(b"new content")
            added.write_bytes(b"new file")

            manifest_path = Path(tmp) / "manifest.json"
            save_rag_manifest(
                {
                    "01_financial/unchanged.pdf": {
                        "path": "01_financial/unchanged.pdf",
                        "filename": "unchanged.pdf",
                        "category": "01_financial",
                        "sha256": "0967115f2813a3541eaef77de9d9d5773f1c0c04314b0bbfe4ff3b3b1c55b5d5",
                        "size_bytes": 4,
                    },
                    "01_financial/changed.pdf": {
                        "path": "01_financial/changed.pdf",
                        "filename": "changed.pdf",
                        "category": "01_financial",
                        "sha256": "old-hash",
                        "size_bytes": 3,
                    },
                    "01_financial/removed.pdf": {
                        "path": "01_financial/removed.pdf",
                        "filename": "removed.pdf",
                        "category": "01_financial",
                        "sha256": "removed-hash",
                        "size_bytes": 7,
                    },
                },
                manifest_path,
            )

            with patch("database.ingestion_pipeline.PDF_BASE_DIR", base), \
                 patch("database.ingestion_pipeline.CATEGORIES", ["01_financial"]), \
                 patch("database.ingestion_pipeline.RAG_MANIFEST_FILE", manifest_path):
                result = sync_rag(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "sync_rag")
        self.assertEqual(result["added"], ["01_financial/added.pdf"])
        self.assertEqual(result["changed"], ["01_financial/changed.pdf"])
        self.assertEqual(result["removed"], ["01_financial/removed.pdf"])
        self.assertEqual(result["unchanged_count"], 1)
        self.assertTrue(result["will_bump_version"])

    def test_sync_rag_noop_does_not_load_pipeline_or_bump_version(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "pdfs"
            financial = base / "01_financial"
            financial.mkdir(parents=True)
            pdf_path = financial / "unchanged.pdf"
            pdf_path.write_bytes(b"same")

            manifest_path = Path(tmp) / "manifest.json"
            version_file = Path(tmp) / "ingestion_version.json"
            version_file.write_text(json.dumps({"version": 4}))

            save_rag_manifest(
                {
                    "01_financial/unchanged.pdf": {
                        "path": "01_financial/unchanged.pdf",
                        "filename": "unchanged.pdf",
                        "category": "01_financial",
                        "sha256": "0967115f2813a3541eaef77de9d9d5773f1c0c04314b0bbfe4ff3b3b1c55b5d5",
                        "size_bytes": 4,
                    }
                },
                manifest_path,
            )

            with patch("database.ingestion_pipeline.PDF_BASE_DIR", base), \
                 patch("database.ingestion_pipeline.CATEGORIES", ["01_financial"]), \
                 patch("database.ingestion_pipeline.RAG_MANIFEST_FILE", manifest_path), \
                 patch("database.setup_rag_pipeline.INGESTION_VERSION_FILE", version_file), \
                 patch("database.ingestion_pipeline.RAGPipelineSetup") as pipeline_cls:
                result = sync_rag(dry_run=False)

            pipeline_cls.assert_not_called()
            self.assertEqual(json.loads(version_file.read_text())["version"], 4)

        self.assertEqual(result["message"], "RAG index already matches source PDFs")
        self.assertIsNone(result["ingestion_version"])


if __name__ == "__main__":
    unittest.main()
