import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from database.generate_pilot_financial_pdfs import EVIDENCE_VERSION, REPORTING_PERIODS
from database.pilot_document_phase import (
    INDEX_VALIDATION_CONFIRMATION,
    INGESTION_CONFIRMATION,
    PILOT_COLLECTION_NAME,
    PILOT_STAGING_SALES_TABLE,
    VALIDATION_CONFIRMATION,
    PilotDocumentPhaseError,
    build_alignment_plan,
    build_index_alignment_plan,
    build_ingestion_plan,
    execute_ingestion,
    render_alignment_query,
    validate_index_sql_alignment,
    validate_pdf_sql_alignment,
)


class _FakePipeline:
    def __init__(self):
        self.seen = []

    def extract_text_from_pdf(self, pdf_path):
        self.seen.append(pdf_path.name)
        return ([{"page_num": 1, "text": "summary content"}], {"filename": pdf_path.name})

    def chunk_text(self, pages_data, metadata):
        return [{"text": pages_data[0]["text"], "metadata": metadata}]

    def embed_and_store(self, chunks):
        return None


class _FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []

    def execute(self, query, parameters):
        self.executions.append((query, parameters))

    def fetchone(self):
        return next(self.rows)


class _FakeConnection:
    def __init__(self, rows):
        self.cursor_value = _FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


class _FakeCollection:
    def __init__(self, revenue_by_filename=None):
        self.revenue_by_filename = revenue_by_filename or {}
        self.get_calls = []

    def get(self, *, where, include):
        filename = where["filename"]
        self.get_calls.append((where, include))
        period = next(period for period in REPORTING_PERIODS if period.filename == filename)
        revenue = self.revenue_by_filename.get(filename, "12,345.67")
        return {
            "documents": [
                f"{period.label} generated sales contain 100 transactions "
                f"with total revenue of ${revenue} and average transaction value of $123.46."
            ],
            "metadatas": [{"filename": filename}],
        }


class PilotDocumentPhaseTests(unittest.TestCase):
    def _paths(self, root: Path):
        pdf_directory = root / "data" / "pdfs_staging" / "enterprise_pilot_v1" / EVIDENCE_VERSION / "01_financial"
        chroma_directory = (
            root / "data" / "chroma_staging" / "enterprise_pilot_v1" / EVIDENCE_VERSION / "financial_documents"
        )
        return pdf_directory, chroma_directory

    def _create_staged_placeholders(self, pdf_directory: Path):
        pdf_directory.mkdir(parents=True)
        for period in REPORTING_PERIODS:
            (pdf_directory / period.filename).write_bytes(b"%PDF-1.4 mocked test input")

    @staticmethod
    def _text_loader(_path):
        for period in REPORTING_PERIODS:
            if period.filename == _path.name:
                return (
                    f"{period.label} generated sales contain 100 transactions "
                    "with total revenue of $12,345.67 and average transaction value of $123.46."
                )
        raise AssertionError(f"Unexpected document requested: {_path}")

    def test_ingestion_plan_is_staging_only_and_has_no_2024_or_live_target(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, chroma_directory = self._paths(Path(tmp))
            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                plan = build_ingestion_plan(
                    pdf_directory=pdf_directory,
                    chroma_directory=chroma_directory,
                )

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["collection"], PILOT_COLLECTION_NAME)
        self.assertEqual(len(plan["pdfs"]), 5)
        self.assertTrue(all("2024" not in path for path in plan["pdfs"]))
        self.assertNotIn("data/pdfs/01_financial", plan["pdf_directory"])
        self.assertNotIn("data/chroma_db", plan["chroma_directory"])
        self.assertNotEqual(plan["collection"], "nexusiq_docs")

    def test_alignment_query_reads_direct_staging_sales_table_only(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, _ = self._paths(Path(tmp))
            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory):
                plan = build_alignment_plan(pdf_directory=pdf_directory)

        query = render_alignment_query().lower()
        self.assertEqual(plan["sql_query"], render_alignment_query())
        self.assertIn(f"from {PILOT_STAGING_SALES_TABLE}".lower(), query)
        self.assertIn("where dataset_id = %s", query)
        for prohibited in ("combined_sales_transactions", "public.", "data_source", " insert ", " update ", " delete "):
            self.assertNotIn(prohibited, f" {query} ")
        self.assertIn("direct_staging_sales_table_only", plan["source_policy"])

    def test_execution_tokens_block_pipeline_and_database_initialization(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, chroma_directory = self._paths(Path(tmp))
            pipeline_factory = MagicMock()
            connection_factory = MagicMock()

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                with self.assertRaisesRegex(PilotDocumentPhaseError, INGESTION_CONFIRMATION):
                    execute_ingestion(
                        pdf_directory=pdf_directory,
                        chroma_directory=chroma_directory,
                        pipeline_factory=pipeline_factory,
                    )
                with self.assertRaisesRegex(PilotDocumentPhaseError, VALIDATION_CONFIRMATION):
                    validate_pdf_sql_alignment(
                        pdf_directory=pdf_directory,
                        database_url="postgresql://unused",
                        connection_factory=connection_factory,
                    )

        pipeline_factory.assert_not_called()
        connection_factory.assert_not_called()

    def test_index_plan_and_token_gate_reject_live_destination_before_opening_collection(self):
        with TemporaryDirectory() as tmp:
            _, chroma_directory = self._paths(Path(tmp))
            collection_factory = MagicMock()
            connection_factory = MagicMock()
            with patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                plan = build_index_alignment_plan(chroma_directory=chroma_directory)
                with self.assertRaisesRegex(PilotDocumentPhaseError, INDEX_VALIDATION_CONFIRMATION):
                    validate_index_sql_alignment(
                        chroma_directory=chroma_directory,
                        collection_factory=collection_factory,
                        connection_factory=connection_factory,
                    )

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["collection"], PILOT_COLLECTION_NAME)
        self.assertEqual(len(plan["filenames"]), 5)
        self.assertTrue(all("2024" not in filename for filename in plan["filenames"]))
        collection_factory.assert_not_called()
        connection_factory.assert_not_called()
        with self.assertRaisesRegex(PilotDocumentPhaseError, "live Chroma"):
            build_index_alignment_plan(
                chroma_directory=Path("data/chroma_db"),
                collection_name="nexusiq_docs",
            )

    def test_ingestion_validates_first_and_atomically_publishes_only_staging_destination(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, chroma_directory = self._paths(Path(tmp))
            self._create_staged_placeholders(pdf_directory)
            pipeline = _FakePipeline()
            factory = MagicMock(return_value=pipeline)
            connection = _FakeConnection([(100, Decimal("12345.67")) for _ in REPORTING_PERIODS])

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                result = execute_ingestion(
                    pdf_directory=pdf_directory,
                    chroma_directory=chroma_directory,
                    execute=True,
                    confirmation=INGESTION_CONFIRMATION,
                    validation_confirmation=VALIDATION_CONFIRMATION,
                    database_url="postgresql://mocked",
                    pipeline_factory=factory,
                    connection_factory=lambda _url: connection,
                    text_loader=self._text_loader,
                )
                published = chroma_directory.exists()

        kwargs = factory.call_args.kwargs
        self.assertNotEqual(kwargs["chroma_dir"], chroma_directory)
        self.assertEqual(Path(result["chroma_directory"]), chroma_directory)
        self.assertTrue(published)
        self.assertEqual(kwargs["collection_name"], PILOT_COLLECTION_NAME)
        self.assertFalse(kwargs["reset_collection"])
        self.assertTrue(result["pdf_sql_validation"])
        self.assertEqual(result["chunks_created"], 5)
        self.assertEqual(len(pipeline.seen), 5)

    def test_ingestion_does_not_write_index_when_pdf_sql_validation_fails(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, chroma_directory = self._paths(Path(tmp))
            self._create_staged_placeholders(pdf_directory)
            pipeline_factory = MagicMock()
            bad_rows = [(100, Decimal("12345.67")) for _ in REPORTING_PERIODS]
            bad_rows[0] = (100, Decimal("12345.68"))

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                with self.assertRaisesRegex(PilotDocumentPhaseError, "FY 2021"):
                    execute_ingestion(
                        pdf_directory=pdf_directory,
                        chroma_directory=chroma_directory,
                        execute=True,
                        confirmation=INGESTION_CONFIRMATION,
                        validation_confirmation=VALIDATION_CONFIRMATION,
                        database_url="postgresql://mocked",
                        pipeline_factory=pipeline_factory,
                        connection_factory=lambda _url: _FakeConnection(bad_rows),
                        text_loader=self._text_loader,
                    )

        pipeline_factory.assert_not_called()
        self.assertFalse(chroma_directory.exists())

    def test_metric_mismatch_fails_after_read_only_five_period_comparison(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, _ = self._paths(Path(tmp))
            self._create_staged_placeholders(pdf_directory)
            rows = [(100, Decimal("12345.67")) for _ in REPORTING_PERIODS]
            rows[2] = (100, Decimal("12345.68"))
            connection = _FakeConnection(rows)

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory):
                with self.assertRaisesRegex(PilotDocumentPhaseError, "FY 2023"):
                    validate_pdf_sql_alignment(
                        pdf_directory=pdf_directory,
                        execute_remote=True,
                        confirmation=VALIDATION_CONFIRMATION,
                        database_url="postgresql://mocked",
                        text_loader=self._text_loader,
                        connection_factory=lambda _url: connection,
                    )

        self.assertTrue(connection.closed)
        self.assertEqual(len(connection.cursor_value.executions), 5)
        for query, parameters in connection.cursor_value.executions:
            self.assertEqual(query, render_alignment_query())
            self.assertEqual(parameters[0], "enterprise_pilot_v1")

    def test_staged_index_alignment_reads_expected_documents_and_matches_sql(self):
        with TemporaryDirectory() as tmp:
            _, chroma_directory = self._paths(Path(tmp))
            collection = _FakeCollection()
            collection_factory = MagicMock(return_value=collection)
            connection = _FakeConnection([(100, Decimal("12345.67")) for _ in REPORTING_PERIODS])

            with patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                result = validate_index_sql_alignment(
                    chroma_directory=chroma_directory,
                    execute_remote=True,
                    confirmation=INDEX_VALIDATION_CONFIRMATION,
                    database_url="postgresql://mocked",
                    collection_factory=collection_factory,
                    connection_factory=lambda _url: connection,
                )

        collection_factory.assert_called_once_with(chroma_directory, PILOT_COLLECTION_NAME)
        self.assertTrue(result["aligned"])
        self.assertEqual(len(result["comparisons"]), 5)
        requested_names = [where["filename"] for where, _include in collection.get_calls]
        self.assertEqual(requested_names, [period.filename for period in REPORTING_PERIODS])
        self.assertTrue(all("2024" not in filename for filename in requested_names))
        self.assertTrue(connection.closed)

    def test_staged_index_metric_mismatch_fails_validation(self):
        with TemporaryDirectory() as tmp:
            _, chroma_directory = self._paths(Path(tmp))
            changed_filename = REPORTING_PERIODS[4].filename
            collection = _FakeCollection({changed_filename: "12,345.68"})
            connection = _FakeConnection([(100, Decimal("12345.67")) for _ in REPORTING_PERIODS])

            with patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                with self.assertRaisesRegex(PilotDocumentPhaseError, "index/SQL metric mismatch.*H1 2026"):
                    validate_index_sql_alignment(
                        chroma_directory=chroma_directory,
                        execute_remote=True,
                        confirmation=INDEX_VALIDATION_CONFIRMATION,
                        database_url="postgresql://mocked",
                        collection_factory=lambda _directory, _name: collection,
                        connection_factory=lambda _url: connection,
                    )

        self.assertEqual(len(collection.get_calls), 5)
        self.assertEqual(len(connection.cursor_value.executions), 5)

    def test_validation_uses_configured_database_url_when_no_override_is_supplied(self):
        with TemporaryDirectory() as tmp:
            pdf_directory, _ = self._paths(Path(tmp))
            self._create_staged_placeholders(pdf_directory)
            connection = _FakeConnection([(100, Decimal("12345.67")) for _ in REPORTING_PERIODS])
            seen_urls = []

            def connection_factory(database_url):
                seen_urls.append(database_url)
                return connection

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("config.settings.settings.database_url", "postgresql://configured/staging"):
                result = validate_pdf_sql_alignment(
                    pdf_directory=pdf_directory,
                    execute_remote=True,
                    confirmation=VALIDATION_CONFIRMATION,
                    text_loader=self._text_loader,
                    connection_factory=connection_factory,
                )

        self.assertTrue(result["aligned"])
        self.assertEqual(seen_urls, ["postgresql://configured/staging"])

    def test_live_source_and_extra_2024_staged_document_are_rejected(self):
        with self.assertRaisesRegex(PilotDocumentPhaseError, "live data/pdfs"):
            build_ingestion_plan(pdf_directory=Path("data/pdfs/01_financial"))

        with TemporaryDirectory() as tmp:
            pdf_directory, chroma_directory = self._paths(Path(tmp))
            self._create_staged_placeholders(pdf_directory)
            (pdf_directory / "Q4_2024_Live_Report.pdf").write_bytes(b"%PDF-1.4 not allowed")
            factory = MagicMock()

            with patch("database.pilot_document_phase.STAGED_FINANCIAL_DIRECTORY", pdf_directory), \
                 patch("database.pilot_document_phase.PILOT_CHROMA_DIRECTORY", chroma_directory):
                with self.assertRaisesRegex(PilotDocumentPhaseError, "outside the five-period"):
                    execute_ingestion(
                        pdf_directory=pdf_directory,
                        chroma_directory=chroma_directory,
                        execute=True,
                        confirmation=INGESTION_CONFIRMATION,
                        pipeline_factory=factory,
                    )

        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
