"""
Safely plan and load validated NexusIQ enterprise extracts into staging.

This module does not alter the production data tables. It validates a generated
CSV package before rendering SQL, creates only isolated staging objects, and
requires an explicit acknowledgement before any remote connection is opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from database.generate_enterprise_expansion import STAGING_NAMESPACE, validate_staging_dataset


EXECUTION_CONFIRMATION = "LOAD_INTO_NEXUSIQ_EXPANSION_STAGING_ONLY"
COMBINED_VIEW_PREFIX = "combined_sales_transactions"
DATASET_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class StagingLoadError(RuntimeError):
    """Raised when a staging-load safety or dataset contract is not satisfied."""


@dataclass(frozen=True)
class CsvLoadSpec:
    """CSV to staging-table mapping in foreign-key-safe load order."""

    name: str
    columns: Sequence[str]

    @property
    def filename(self) -> str:
        return f"{self.name}.csv"


CSV_LOAD_SPECS = (
    CsvLoadSpec("business_events", ("event_id", "start_date", "end_date", "event_type", "title", "impact_area")),
    CsvLoadSpec("stores", ("store_id", "region", "state_code", "format", "opened_date")),
    CsvLoadSpec("vendors", ("vendor_id", "vendor_name", "primary_category", "lead_time_days", "risk_tier")),
    CsvLoadSpec(
        "products",
        ("product_id", "product_name", "category", "vendor_id", "list_price", "unit_cost", "launch_date"),
    ),
    CsvLoadSpec("customers", ("customer_id", "home_region", "loyalty_tier", "signup_date", "preferred_channel")),
    CsvLoadSpec(
        "promotions",
        ("promotion_id", "campaign_name", "category", "start_date", "end_date", "discount_pct", "channel"),
    ),
    CsvLoadSpec(
        "sales_transactions",
        (
            "transaction_id",
            "transaction_date",
            "customer_id",
            "store_id",
            "channel",
            "product_id",
            "product_category",
            "quantity",
            "unit_price",
            "discount_pct",
            "total_amount",
            "gross_margin_amount",
            "payment_method",
            "promotion_id",
            "event_id",
        ),
    ),
    CsvLoadSpec(
        "returns",
        ("return_id", "transaction_id", "product_id", "return_date", "return_reason", "refund_amount"),
    ),
    CsvLoadSpec(
        "inventory_snapshots",
        ("snapshot_id", "snapshot_date", "store_id", "product_id", "stock_level", "reorder_point", "stockout_flag"),
    ),
    CsvLoadSpec(
        "support_cases",
        ("case_id", "opened_date", "customer_id", "category", "issue_type", "sentiment", "summary"),
    ),
)


def _qualified(name: str) -> str:
    return f'"{STAGING_NAMESPACE}"."{name}"'


def combined_view_name(dataset_id: str) -> str:
    """Return a unique, SQL-safe view name for an immutable staged dataset."""
    if not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise StagingLoadError(f"Invalid dataset_id for staging view: {dataset_id!r}")
    identifier = re.sub(r"[^a-z0-9_]", "_", dataset_id)
    digest = hashlib.sha256(dataset_id.encode()).hexdigest()[:8]
    return f"{COMBINED_VIEW_PREFIX}_{identifier}_{digest}"


def _read_manifest(dataset_dir: Path) -> Dict[str, object]:
    manifest_path = Path(dataset_dir) / "manifest.json"
    try:
        return json.loads(manifest_path.read_text())
    except FileNotFoundError as exc:
        raise StagingLoadError(f"Missing staging manifest: {manifest_path}") from exc


def _validate_dataset_contract(dataset_dir: Path, manifest: Dict[str, object]) -> None:
    dataset_id = str(manifest.get("dataset_id", ""))
    if not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise StagingLoadError(f"Invalid dataset_id for staging load: {dataset_id!r}")
    if manifest.get("staging_namespace") != STAGING_NAMESPACE:
        raise StagingLoadError(
            f"Manifest staging namespace must be {STAGING_NAMESPACE!r}; "
            f"received {manifest.get('staging_namespace')!r}"
        )
    for spec in CSV_LOAD_SPECS:
        csv_path = Path(dataset_dir) / spec.filename
        try:
            with csv_path.open(newline="") as handle:
                observed_columns = tuple(csv.DictReader(handle).fieldnames or ())
        except FileNotFoundError as exc:
            raise StagingLoadError(f"Missing staged CSV file: {csv_path}") from exc
        if observed_columns != tuple(spec.columns):
            raise StagingLoadError(
                f"{spec.filename} columns do not match loader contract: "
                f"expected {list(spec.columns)}, received {list(observed_columns)}"
            )


def build_load_plan(dataset_dir: Path) -> Dict[str, object]:
    """Validate an extract package and return a non-executing staging load plan."""
    dataset_dir = Path(dataset_dir)
    validation = validate_staging_dataset(dataset_dir)
    if not validation["valid"]:
        raise StagingLoadError(
            "Staged CSV validation failed; refusing to plan a load: "
            + "; ".join(validation["errors"][:5])
        )
    manifest = _read_manifest(dataset_dir)
    _validate_dataset_contract(dataset_dir, manifest)
    if manifest["dataset_id"] != validation["dataset_id"]:
        raise StagingLoadError("Manifest and validation dataset identifiers disagree")
    return {
        "action": "enterprise_staging_load",
        "dry_run": True,
        "dataset_id": manifest["dataset_id"],
        "dataset_dir": str(dataset_dir),
        "staging_namespace": STAGING_NAMESPACE,
        "combined_view": combined_view_name(str(manifest["dataset_id"])),
        "production_policy": "read_public_sales_transactions_in_combined_view_only",
        "rerun_policy": "dataset_id_is_immutable_use_a_new_dataset_id_for_another_load",
        "csv_load_order": [spec.name for spec in CSV_LOAD_SPECS],
        "row_counts": validation["row_counts"],
        "total_revenue": validation["total_revenue"],
    }


def render_staging_ddl() -> str:
    """Render PostgreSQL DDL that owns data only inside the staging schema."""
    schema = f'"{STAGING_NAMESPACE}"'
    dataset_default = "DEFAULT current_setting('nexusiq.dataset_id')"
    return f"""CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {_qualified("loaded_datasets")} (
    dataset_id TEXT PRIMARY KEY,
    manifest_path TEXT NOT NULL,
    generated_sales_rows BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {_qualified("business_events")} (
    dataset_id TEXT NOT NULL {dataset_default},
    event_id TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    impact_area TEXT NOT NULL,
    PRIMARY KEY (dataset_id, event_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("stores")} (
    dataset_id TEXT NOT NULL {dataset_default},
    store_id TEXT NOT NULL,
    region TEXT NOT NULL,
    state_code TEXT NOT NULL,
    format TEXT NOT NULL,
    opened_date DATE NOT NULL,
    PRIMARY KEY (dataset_id, store_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("vendors")} (
    dataset_id TEXT NOT NULL {dataset_default},
    vendor_id TEXT NOT NULL,
    vendor_name TEXT NOT NULL,
    primary_category TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL,
    risk_tier TEXT NOT NULL,
    PRIMARY KEY (dataset_id, vendor_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("products")} (
    dataset_id TEXT NOT NULL {dataset_default},
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    list_price NUMERIC(12, 2) NOT NULL,
    unit_cost NUMERIC(12, 2) NOT NULL,
    launch_date DATE NOT NULL,
    PRIMARY KEY (dataset_id, product_id),
    FOREIGN KEY (dataset_id, vendor_id) REFERENCES {_qualified("vendors")} (dataset_id, vendor_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("customers")} (
    dataset_id TEXT NOT NULL {dataset_default},
    customer_id TEXT NOT NULL,
    home_region TEXT NOT NULL,
    loyalty_tier TEXT NOT NULL,
    signup_date DATE NOT NULL,
    preferred_channel TEXT NOT NULL,
    PRIMARY KEY (dataset_id, customer_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("promotions")} (
    dataset_id TEXT NOT NULL {dataset_default},
    promotion_id TEXT NOT NULL,
    campaign_name TEXT NOT NULL,
    category TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    discount_pct NUMERIC(5, 2) NOT NULL,
    channel TEXT NOT NULL,
    PRIMARY KEY (dataset_id, promotion_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("sales_transactions")} (
    dataset_id TEXT NOT NULL {dataset_default},
    transaction_id TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    customer_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_category TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    discount_pct NUMERIC(5, 2) NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL,
    gross_margin_amount NUMERIC(14, 2) NOT NULL,
    payment_method TEXT NOT NULL,
    promotion_id TEXT,
    event_id TEXT,
    PRIMARY KEY (dataset_id, transaction_id),
    FOREIGN KEY (dataset_id, customer_id) REFERENCES {_qualified("customers")} (dataset_id, customer_id),
    FOREIGN KEY (dataset_id, store_id) REFERENCES {_qualified("stores")} (dataset_id, store_id),
    FOREIGN KEY (dataset_id, product_id) REFERENCES {_qualified("products")} (dataset_id, product_id),
    FOREIGN KEY (dataset_id, promotion_id) REFERENCES {_qualified("promotions")} (dataset_id, promotion_id),
    FOREIGN KEY (dataset_id, event_id) REFERENCES {_qualified("business_events")} (dataset_id, event_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("returns")} (
    dataset_id TEXT NOT NULL {dataset_default},
    return_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    return_date DATE NOT NULL,
    return_reason TEXT NOT NULL,
    refund_amount NUMERIC(14, 2) NOT NULL,
    PRIMARY KEY (dataset_id, return_id),
    FOREIGN KEY (dataset_id, transaction_id) REFERENCES {_qualified("sales_transactions")} (dataset_id, transaction_id),
    FOREIGN KEY (dataset_id, product_id) REFERENCES {_qualified("products")} (dataset_id, product_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("inventory_snapshots")} (
    dataset_id TEXT NOT NULL {dataset_default},
    snapshot_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    store_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    stock_level INTEGER NOT NULL,
    reorder_point INTEGER NOT NULL,
    stockout_flag BOOLEAN NOT NULL,
    PRIMARY KEY (dataset_id, snapshot_id),
    FOREIGN KEY (dataset_id, store_id) REFERENCES {_qualified("stores")} (dataset_id, store_id),
    FOREIGN KEY (dataset_id, product_id) REFERENCES {_qualified("products")} (dataset_id, product_id)
);

CREATE TABLE IF NOT EXISTS {_qualified("support_cases")} (
    dataset_id TEXT NOT NULL {dataset_default},
    case_id TEXT NOT NULL,
    opened_date DATE NOT NULL,
    customer_id TEXT NOT NULL,
    category TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    summary TEXT NOT NULL,
    PRIMARY KEY (dataset_id, case_id),
    FOREIGN KEY (dataset_id, customer_id) REFERENCES {_qualified("customers")} (dataset_id, customer_id)
);"""


def render_combined_view_ddl(dataset_id: str) -> str:
    """Render a staged analytics view that reads but never modifies live sales."""
    view_name = combined_view_name(dataset_id)
    return f"""CREATE OR REPLACE VIEW {_qualified(view_name)} (
    data_source,
    dataset_id,
    transaction_id,
    transaction_date,
    region,
    store_id,
    product_category,
    product_name,
    quantity,
    unit_price,
    total_amount,
    customer_id,
    payment_method
) AS
SELECT
    'live'::TEXT AS data_source,
    NULL::TEXT AS dataset_id,
    live.id::TEXT AS transaction_id,
    live.transaction_date,
    live.region,
    live.store_id,
    live.product_category,
    live.product_name,
    live.quantity,
    live.unit_price,
    live.total_amount,
    live.customer_id,
    live.payment_method
FROM public.sales_transactions AS live
UNION ALL
SELECT
    'generated'::TEXT AS data_source,
    sale.dataset_id,
    sale.transaction_id,
    sale.transaction_date::TIMESTAMP AS transaction_date,
    store.region,
    sale.store_id,
    sale.product_category,
    product.product_name,
    sale.quantity,
    sale.unit_price,
    sale.total_amount,
    sale.customer_id,
    sale.payment_method
FROM {_qualified("sales_transactions")} AS sale
JOIN {_qualified("stores")} AS store
  ON store.dataset_id = sale.dataset_id AND store.store_id = sale.store_id
JOIN {_qualified("products")} AS product
  ON product.dataset_id = sale.dataset_id AND product.product_id = sale.product_id
WHERE sale.dataset_id = '{dataset_id}';"""


def render_copy_sql(spec: CsvLoadSpec) -> str:
    """Render a COPY statement; dataset_id is supplied by the staging default."""
    columns = ", ".join(f'"{column}"' for column in spec.columns)
    return (
        f"COPY {_qualified(spec.name)} ({columns}) "
        "FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    )


def render_execution_sql(dataset_id: str) -> str:
    """Return all schema/view SQL for human review without opening a database."""
    return render_staging_ddl() + "\n\n" + render_combined_view_ddl(dataset_id)


def _require_execution_confirmation(execute: bool, confirmation: Optional[str]) -> None:
    if not execute or confirmation != EXECUTION_CONFIRMATION:
        raise StagingLoadError(
            "Remote staging execution is disabled by default. To load only the isolated staging schema, "
            f"provide --execute --confirm-staging-only {EXECUTION_CONFIRMATION}."
        )


def execute_staging_load(
    dataset_dir: Path,
    *,
    execute: bool = False,
    confirmation: Optional[str] = None,
    database_url: Optional[str] = None,
) -> Dict[str, object]:
    """Load one validated dataset atomically after explicit staging-only consent."""
    plan = build_load_plan(dataset_dir)
    _require_execution_confirmation(execute, confirmation)
    if database_url is None:
        from config.settings import settings

        database_url = settings.database_url

    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(render_execution_sql(str(plan["dataset_id"])))
        cursor.execute("SELECT set_config('nexusiq.dataset_id', %s, true)", (plan["dataset_id"],))
        cursor.execute(
            f"INSERT INTO {_qualified('loaded_datasets')} "
            "(dataset_id, manifest_path, generated_sales_rows) VALUES (%s, %s, %s)",
            (
                plan["dataset_id"],
                str(Path(dataset_dir) / "manifest.json"),
                plan["row_counts"]["sales_transactions"],
            ),
        )
        for spec in CSV_LOAD_SPECS:
            with (Path(dataset_dir) / spec.filename).open(newline="") as handle:
                cursor.copy_expert(render_copy_sql(spec), handle)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        engine.dispose()
    return {**plan, "dry_run": False, "loaded": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or execute isolated NexusIQ enterprise staging loads")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "dry-run", "ddl"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--dataset-dir", type=Path, required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--dataset-dir", type=Path, required=True)
    execute.add_argument("--execute", action="store_true")
    execute.add_argument("--confirm-staging-only")
    execute.add_argument("--database-url")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command in {"plan", "dry-run"}:
        result = build_load_plan(args.dataset_dir)
        print(json.dumps(result, indent=2))
    elif args.command == "ddl":
        plan = build_load_plan(args.dataset_dir)
        print(render_execution_sql(str(plan["dataset_id"])))
    elif args.command == "execute":
        result = execute_staging_load(
            args.dataset_dir,
            execute=args.execute,
            confirmation=args.confirm_staging_only,
            database_url=args.database_url,
        )
        print(json.dumps(result, indent=2))
    else:
        raise StagingLoadError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
