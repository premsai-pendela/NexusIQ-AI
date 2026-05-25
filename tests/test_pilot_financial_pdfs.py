import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from database.generate_pilot_financial_pdfs import (
    EXECUTION_CONFIRMATION,
    EVIDENCE_VERSION,
    PILOT_DATASET_ID,
    STAGED_PDF_ROOT,
    PilotPdfGenerationError,
    ReportingPeriod,
    build_pdf_plan,
    generate_pilot_pdfs,
    render_metric_queries,
    staging_source_tables,
)


class PilotFinancialPdfTests(unittest.TestCase):
    def test_plan_targets_distinct_staged_pilot_outputs_and_new_periods_only(self):
        plan = build_pdf_plan()

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["dataset_id"], PILOT_DATASET_ID)
        self.assertEqual(
            Path(plan["output_directory"]),
            STAGED_PDF_ROOT / "enterprise_pilot_v1" / EVIDENCE_VERSION / "01_financial",
        )
        self.assertEqual(len(plan["outputs"]), 5)
        self.assertTrue(all("2024" not in output for output in plan["outputs"]))
        self.assertIn("never_generate_or_overwrite_live_2024_pdfs", plan["protected_period_policy"])
        self.assertIn("direct_staged_generated_tables_only", plan["source_policy"])

    def test_queries_read_only_direct_staged_generated_tables(self):
        (sales_table,) = staging_source_tables()
        queries = render_metric_queries()

        self.assertIn("combined_sales_transactions_enterprise_pilot", sales_table)
        self.assertEqual(set(queries), {"summary"})
        for query in queries.values():
            lowered = query.lower()
            self.assertIn(f"from {sales_table}".lower(), lowered)
            self.assertIn("dataset_id = %s", lowered)
            self.assertNotIn("public.", lowered)
            self.assertNotIn("insert ", lowered)
            self.assertNotIn("update ", lowered)
            self.assertNotIn("delete ", lowered)
            self.assertIn("as sale", lowered)

    def test_plan_rejects_protected_2024_period_and_live_pdf_root(self):
        protected = ReportingPeriod(
            "Q4 2024",
            "Q4_2024_Pilot_Report.pdf",
            date(2024, 10, 1),
            date(2025, 1, 1),
        )

        with self.assertRaisesRegex(PilotPdfGenerationError, "protected 2024"):
            build_pdf_plan(periods=(protected,))
        with self.assertRaisesRegex(PilotPdfGenerationError, "live data/pdfs"):
            build_pdf_plan(_output_root_override=STAGED_PDF_ROOT.parent / "pdfs")

    def test_generator_requires_staging_confirmation_before_db_access_or_writes(self):
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "pilot_outputs"
            with self.assertRaisesRegex(PilotPdfGenerationError, EXECUTION_CONFIRMATION):
                generate_pilot_pdfs(_output_root_override=output_root)
            with self.assertRaisesRegex(PilotPdfGenerationError, EXECUTION_CONFIRMATION):
                generate_pilot_pdfs(
                    _output_root_override=output_root,
                    execute=True,
                    confirmation="GENERATE_ANY_PDFS",
                )

            self.assertFalse(output_root.exists())

    def test_existing_output_blocks_generation_before_database_connection(self):
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "pilot_outputs"
            plan = build_pdf_plan(_output_root_override=output_root)
            existing = Path(plan["outputs"][0])
            existing.parent.mkdir(parents=True)
            existing.write_text("reviewed output")

            with self.assertRaisesRegex(PilotPdfGenerationError, "destination"):
                generate_pilot_pdfs(
                    _output_root_override=output_root,
                    execute=True,
                    confirmation=EXECUTION_CONFIRMATION,
                    database_url="postgresql://connection-would-not-be-opened",
                )

            self.assertEqual(existing.read_text(), "reviewed output")

    def test_unsupported_dataset_cannot_select_another_view(self):
        with self.assertRaisesRegex(PilotPdfGenerationError, "locked"):
            build_pdf_plan(dataset_id="enterprise_portfolio_v1")

    @staticmethod
    def _metrics(transactions=10):
        return {
            "transactions": transactions,
            "revenue": Decimal("100.00"),
        }

    @staticmethod
    def _connection_factory(_database_url):
        class Connection:
            def cursor(self):
                return object()

            def close(self):
                pass

        return Connection()

    def test_later_zero_row_period_leaves_no_final_pdfs(self):
        periods = (
            ReportingPeriod("FY 2025", "first.pdf", date(2025, 1, 1), date(2026, 1, 1)),
            ReportingPeriod("H1 2026", "second.pdf", date(2026, 1, 1), date(2026, 7, 1)),
        )
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "pilot_outputs"
            with patch(
                "database.generate_pilot_financial_pdfs._query_period_metrics",
                side_effect=[self._metrics(), self._metrics(transactions=0)],
            ):
                with self.assertRaisesRegex(PilotPdfGenerationError, "H1 2026"):
                    generate_pilot_pdfs(
                        periods=periods,
                        execute=True,
                        confirmation=EXECUTION_CONFIRMATION,
                        database_url="postgresql://unused",
                        _output_root_override=output_root,
                        _connection_factory=self._connection_factory,
                    )

            self.assertEqual(list(output_root.rglob("*.pdf")), [])

    def test_render_failure_cleans_temporary_files_and_leaves_no_final_pdfs(self):
        periods = (
            ReportingPeriod("FY 2025", "first.pdf", date(2025, 1, 1), date(2026, 1, 1)),
            ReportingPeriod("H1 2026", "second.pdf", date(2026, 1, 1), date(2026, 7, 1)),
        )

        def failed_second_render(period, _metrics, out_path):
            out_path.write_bytes(b"%PDF-staged-temp")
            if period.label == "H1 2026":
                raise RuntimeError("render failed")

        with TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "pilot_outputs"
            with patch(
                "database.generate_pilot_financial_pdfs._query_period_metrics",
                side_effect=[self._metrics(), self._metrics()],
            ):
                with self.assertRaisesRegex(RuntimeError, "render failed"):
                    generate_pilot_pdfs(
                        periods=periods,
                        execute=True,
                        confirmation=EXECUTION_CONFIRMATION,
                        database_url="postgresql://unused",
                        _output_root_override=output_root,
                        _connection_factory=self._connection_factory,
                        _renderer=failed_second_render,
                    )

            self.assertEqual(list(output_root.rglob("*.pdf")), [])

    def test_execution_uses_configured_database_url_when_no_override_is_supplied(self):
        periods = (ReportingPeriod("FY 2025", "report.pdf", date(2025, 1, 1), date(2026, 1, 1)),)
        seen_urls = []

        def connection_factory(database_url):
            seen_urls.append(database_url)
            return self._connection_factory(database_url)

        def renderer(_period, _metrics, out_path):
            out_path.write_bytes(b"%PDF-generated")

        with TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "pilot_outputs"
            with patch("database.generate_pilot_financial_pdfs._query_period_metrics", return_value=self._metrics()), \
                 patch("config.settings.settings.database_url", "postgresql://configured/staging"):
                generate_pilot_pdfs(
                    periods=periods,
                    execute=True,
                    confirmation=EXECUTION_CONFIRMATION,
                    _output_root_override=output_root,
                    _connection_factory=connection_factory,
                    _renderer=renderer,
                )

        self.assertEqual(seen_urls, ["postgresql://configured/staging"])


if __name__ == "__main__":
    unittest.main()
