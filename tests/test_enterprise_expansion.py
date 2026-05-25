import csv
import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from database.generate_enterprise_expansion import (
    STAGING_NAMESPACE,
    ExpansionProfile,
    PROFILES,
    build_expansion_plan,
    generate_staging_dataset,
    validate_staging_dataset,
)


class EnterpriseExpansionTests(unittest.TestCase):
    def test_portfolio_plan_is_versioned_and_does_not_target_live_tables(self):
        plan = build_expansion_plan(PROFILES["portfolio"])

        self.assertEqual(plan["dataset_id"], "enterprise_portfolio_v1")
        self.assertEqual(plan["staging_namespace"], STAGING_NAMESPACE)
        self.assertEqual(plan["planned_rows"]["sales_transactions"], 5_000_000)
        self.assertEqual(plan["planned_rows"]["customers"], 250_000)
        self.assertEqual(plan["planned_rows"]["inventory_snapshots"], 1_200_000)
        self.assertEqual(plan["sales_transaction_composition"]["preserved_live_2024_rows"], 100_000)
        self.assertEqual(plan["sales_transaction_composition"]["generated_extension_rows"], 4_900_000)
        self.assertIn("never_write_or_replace_live_tables", plan["live_table_policy"])

    def test_generate_writes_linked_staging_files_and_manifest(self):
        profile = ExpansionProfile(
            name="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
            transactions=40,
            customers=12,
            products=10,
            stores=5,
            vendors=5,
            promotions=4,
            inventory_snapshots=20,
            support_cases=7,
        )
        with TemporaryDirectory() as tmp:
            manifest = generate_staging_dataset(profile, Path(tmp), seed=7)
            output_dir = Path(manifest["output_directory"])

            manifest_on_disk = json.loads((output_dir / "manifest.json").read_text())
            with (output_dir / "sales_transactions.csv").open(newline="") as handle:
                transactions = list(csv.DictReader(handle))
            with (output_dir / "customers.csv").open(newline="") as handle:
                customer_ids = {row["customer_id"] for row in csv.DictReader(handle)}
            with (output_dir / "products.csv").open(newline="") as handle:
                products = {row["product_id"]: row for row in csv.DictReader(handle)}
            with (output_dir / "promotions.csv").open(newline="") as handle:
                promotions = {row["promotion_id"]: row for row in csv.DictReader(handle)}
            validation = validate_staging_dataset(output_dir)

        self.assertEqual(manifest_on_disk["generated_rows"]["sales_transactions"], 40)
        self.assertEqual(len(transactions), 40)
        self.assertTrue({row["customer_id"] for row in transactions}.issubset(customer_ids))
        self.assertTrue({row["product_id"] for row in transactions}.issubset(products))
        self.assertTrue(
            all(products[row["product_id"]]["launch_date"] <= row["transaction_date"] for row in transactions)
        )
        for row in transactions:
            if row["promotion_id"]:
                promotion = promotions[row["promotion_id"]]
                self.assertEqual(promotion["category"], row["product_category"])
                self.assertLessEqual(promotion["start_date"], row["transaction_date"])
                self.assertGreaterEqual(promotion["end_date"], row["transaction_date"])
                self.assertEqual(promotion["discount_pct"], row["discount_pct"])
        self.assertGreater(manifest_on_disk["validation_kpis"]["total_revenue"], 0)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["error_count"], 0)

    def test_existing_stage_is_not_overwritten_without_explicit_flag(self):
        profile = ExpansionProfile(
            name="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            transactions=2,
            customers=2,
            products=5,
            stores=1,
            vendors=1,
            promotions=1,
            inventory_snapshots=2,
            support_cases=1,
        )
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            generate_staging_dataset(profile, output_root, seed=11)
            with self.assertRaises(FileExistsError):
                generate_staging_dataset(profile, output_root, seed=11)

    def test_validator_rejects_generated_transaction_in_preserved_live_year(self):
        profile = ExpansionProfile(
            name="protected-test",
            start_date=date(2023, 1, 1),
            end_date=date(2025, 12, 31),
            transactions=4,
            customers=4,
            products=5,
            stores=1,
            vendors=1,
            promotions=1,
            inventory_snapshots=1,
            support_cases=1,
            preserved_live_transactions=1,
        )
        with TemporaryDirectory() as tmp:
            output_dir = Path(generate_staging_dataset(profile, Path(tmp), seed=4)["output_directory"])
            sales_path = output_dir / "sales_transactions.csv"
            with sales_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
                fields = list(rows[0])
            rows[0]["transaction_date"] = "2024-06-01"
            with sales_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            validation = validate_staging_dataset(output_dir)

        self.assertFalse(validation["valid"])
        self.assertGreater(validation["error_count"], 0)
        self.assertIn("overlaps protected live baseline period", validation["errors"][0])


if __name__ == "__main__":
    unittest.main()
