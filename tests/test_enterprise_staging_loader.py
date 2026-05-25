import csv
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from database.generate_enterprise_expansion import ExpansionProfile, generate_staging_dataset
from database.load_enterprise_staging import (
    CSV_LOAD_SPECS,
    EXECUTION_CONFIRMATION,
    StagingLoadError,
    build_load_plan,
    execute_staging_load,
    render_combined_view_ddl,
    render_copy_sql,
    render_execution_sql,
)


class EnterpriseStagingLoaderTests(unittest.TestCase):
    def _generate_dataset(self, root: Path) -> Path:
        profile = ExpansionProfile(
            name="loader-test",
            start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31),
            transactions=12,
            customers=8,
            products=5,
            stores=2,
            vendors=2,
            promotions=2,
            inventory_snapshots=5,
            support_cases=3,
            preserved_live_transactions=2,
        )
        manifest = generate_staging_dataset(profile, root, seed=29)
        return Path(manifest["output_directory"])

    def test_plan_validates_extract_and_lists_dimension_first_load_order(self):
        with TemporaryDirectory() as tmp:
            plan = build_load_plan(self._generate_dataset(Path(tmp)))

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["dataset_id"], "enterprise_loader-test_v1")
        self.assertEqual(
            plan["csv_load_order"],
            [
                "business_events",
                "stores",
                "vendors",
                "products",
                "customers",
                "promotions",
                "sales_transactions",
                "returns",
                "inventory_snapshots",
                "support_cases",
            ],
        )
        self.assertEqual(plan["row_counts"]["sales_transactions"], 10)
        self.assertIn("immutable", plan["rerun_policy"])

    def test_rendered_sql_writes_only_to_staging_and_reads_public_sales_in_view(self):
        dataset_id = "enterprise_loader-test_v1"
        sql = render_execution_sql(dataset_id).lower()
        view_sql = render_combined_view_ddl(dataset_id).lower()

        self.assertIn('create schema if not exists "nexusiq_expansion_staging"', sql)
        self.assertIn("from public.sales_transactions as live", view_sql)
        self.assertIn("'live'::text as data_source", view_sql)
        self.assertIn("'generated'::text as data_source", view_sql)
        self.assertIn(f"where sale.dataset_id = '{dataset_id}'", view_sql)
        self.assertIn("product_category,\n    product_name,\n    quantity", view_sql)
        for operation in ("insert into", "update", "delete from", "truncate", "drop table"):
            for table in ("public.sales_transactions", "public.customers", "public.inventory"):
                self.assertNotIn(f"{operation} {table}", sql)

    def test_invalid_dataset_blocks_plan_before_sql_or_execution(self):
        with TemporaryDirectory() as tmp:
            dataset_dir = self._generate_dataset(Path(tmp))
            sales_path = dataset_dir / "sales_transactions.csv"
            with sales_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fields = list(rows[0])
            rows[0]["transaction_date"] = "2024-05-01"
            with sales_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaisesRegex(StagingLoadError, "validation failed"):
                build_load_plan(dataset_dir)

    def test_remote_execution_requires_exact_staging_only_acknowledgement(self):
        with TemporaryDirectory() as tmp:
            dataset_dir = self._generate_dataset(Path(tmp))
            with self.assertRaisesRegex(StagingLoadError, EXECUTION_CONFIRMATION):
                execute_staging_load(dataset_dir)
            with self.assertRaisesRegex(StagingLoadError, EXECUTION_CONFIRMATION):
                execute_staging_load(dataset_dir, execute=True, confirmation="LOAD_ANYWHERE")

    def test_csv_mapping_and_copy_statements_never_target_public_schema(self):
        names = [spec.name for spec in CSV_LOAD_SPECS]

        self.assertEqual(names[0:6], ["business_events", "stores", "vendors", "products", "customers", "promotions"])
        self.assertEqual(names[6:], ["sales_transactions", "returns", "inventory_snapshots", "support_cases"])
        for spec in CSV_LOAD_SPECS:
            copy_sql = render_copy_sql(spec)
            self.assertIn(f'"nexusiq_expansion_staging"."{spec.name}"', copy_sql)
            self.assertNotIn("public.", copy_sql.lower())
            self.assertIn("NULL ''", copy_sql)

    def test_dataset_registry_primary_key_prevents_same_dataset_overwrite(self):
        sql = render_execution_sql("enterprise_loader-test_v1")

        self.assertIn('"loaded_datasets"', sql)
        self.assertIn("dataset_id TEXT PRIMARY KEY", sql)
        self.assertNotIn("ON CONFLICT", sql)
        self.assertNotIn("TRUNCATE", sql)


if __name__ == "__main__":
    unittest.main()
