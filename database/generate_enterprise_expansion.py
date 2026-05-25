"""
Generate versioned enterprise-scale staging extracts for NexusIQ.

This generator never connects to DATABASE_URL and never mutates deployed
Supabase tables. It writes linked CSV extracts plus a KPI manifest that can be
validated before a separate, reviewed staging-load workflow is introduced.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, TextIO


OUTPUT_ROOT = Path("data/expansion")
STAGING_NAMESPACE = "nexusiq_expansion_staging"
DATASET_VERSION = "v1"
PRESERVED_BASELINE_START = date(2024, 1, 1)
PRESERVED_BASELINE_END = date(2024, 12, 31)

REGIONS = ("Northeast", "Southeast", "Midwest", "Southwest", "West")
CATEGORIES = ("Electronics", "Home", "Appliances", "Fitness", "Office")
CHANNELS = ("Store", "Ecommerce", "Marketplace")
PAYMENT_METHODS = ("Credit Card", "Debit Card", "Digital Wallet", "Store Card")

CATEGORY_PRICE_RANGES = {
    "Electronics": (49.0, 1599.0),
    "Home": (19.0, 499.0),
    "Appliances": (79.0, 1899.0),
    "Fitness": (24.0, 899.0),
    "Office": (15.0, 799.0),
}
CATEGORY_WEIGHTS = (34, 19, 18, 13, 16)
CATEGORY_RETURN_RATES = {
    "Electronics": 0.105,
    "Home": 0.045,
    "Appliances": 0.072,
    "Fitness": 0.058,
    "Office": 0.038,
}

TIMELINE_EVENTS = (
    {
        "event_id": "EVT-2021-01",
        "start_date": "2021-01-01",
        "end_date": "2021-12-31",
        "event_type": "expansion",
        "title": "National ecommerce rollout",
        "impact_area": "digital_channel",
    },
    {
        "event_id": "EVT-2022-01",
        "start_date": "2022-04-01",
        "end_date": "2022-10-31",
        "event_type": "supply_chain",
        "title": "Appliance supplier delays",
        "impact_area": "inventory_and_margin",
    },
    {
        "event_id": "EVT-2023-01",
        "start_date": "2023-08-01",
        "end_date": "2023-12-31",
        "event_type": "promotion",
        "title": "Loyalty program launch",
        "impact_area": "customer_retention",
    },
    {
        "event_id": "EVT-2024-01",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "event_type": "baseline",
        "title": "Current validated demo year",
        "impact_area": "cross_validation",
    },
    {
        "event_id": "EVT-2025-01",
        "start_date": "2025-05-01",
        "end_date": "2025-09-30",
        "event_type": "competition",
        "title": "Competitor electronics price campaign",
        "impact_area": "electronics_margin",
    },
    {
        "event_id": "EVT-2026-01",
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "event_type": "ai_operations",
        "title": "Demand forecasting pilot",
        "impact_area": "stockouts_and_service",
    },
)


@dataclass(frozen=True)
class ExpansionProfile:
    """A fixed row-volume contract for a generated staging dataset."""

    name: str
    start_date: date
    end_date: date
    transactions: int
    customers: int
    products: int
    stores: int
    vendors: int
    promotions: int
    inventory_snapshots: int
    support_cases: int
    preserved_live_transactions: int = 0

    @property
    def dataset_id(self) -> str:
        return f"enterprise_{self.name}_{DATASET_VERSION}"

    def __post_init__(self) -> None:
        if self.preserved_live_transactions < 0 or self.preserved_live_transactions > self.transactions:
            raise ValueError("preserved_live_transactions must be within the transaction target")
        if (
            self.preserved_live_transactions < self.transactions
            and self.preserved_live_transactions > 0
            and PRESERVED_BASELINE_START <= self.start_date <= self.end_date <= PRESERVED_BASELINE_END
        ):
            raise ValueError("An extension profile must include dates outside the preserved 2024 baseline")


PROFILES = {
    "pilot": ExpansionProfile(
        name="pilot",
        start_date=date(2021, 1, 1),
        end_date=date(2026, 6, 30),
        transactions=250_000,
        customers=25_000,
        products=500,
        stores=25,
        vendors=30,
        promotions=50,
        inventory_snapshots=60_000,
        support_cases=4_000,
        preserved_live_transactions=100_000,
    ),
    "portfolio": ExpansionProfile(
        name="portfolio",
        start_date=date(2021, 1, 1),
        end_date=date(2026, 6, 30),
        transactions=5_000_000,
        customers=250_000,
        products=5_000,
        stores=100,
        vendors=250,
        promotions=240,
        inventory_snapshots=1_200_000,
        support_cases=80_000,
        preserved_live_transactions=100_000,
    ),
}


def build_expansion_plan(profile: ExpansionProfile) -> Dict[str, object]:
    """Return the intended data scope without generating files or touching SQL."""
    generated_transactions = profile.transactions - profile.preserved_live_transactions
    planned_rows = {
        "business_events": len(TIMELINE_EVENTS),
        "stores": profile.stores,
        "vendors": profile.vendors,
        "products": profile.products,
        "customers": profile.customers,
        "promotions": profile.promotions,
        "sales_transactions": profile.transactions,
        "returns": "derived from transactions using category-specific rates",
        "inventory_snapshots": profile.inventory_snapshots,
        "support_cases": profile.support_cases,
    }
    return {
        "dataset_id": profile.dataset_id,
        "profile": profile.name,
        "date_range": {
            "start": profile.start_date.isoformat(),
            "end": profile.end_date.isoformat(),
        },
        "staging_namespace": STAGING_NAMESPACE,
        "live_table_policy": "never_write_or_replace_live_tables_from_generator",
        "promotion_policy": "validate_staging_then_use_reviewed_promotion_workflow",
        "planned_rows": planned_rows,
        "sales_transaction_composition": {
            "unified_target_rows": profile.transactions,
            "preserved_live_2024_rows": profile.preserved_live_transactions,
            "generated_extension_rows": generated_transactions,
            "preserved_date_range": {
                "start": PRESERVED_BASELINE_START.isoformat(),
                "end": PRESERVED_BASELINE_END.isoformat(),
            },
            "policy": "copy_live_2024_rows_unchanged_during_reviewed_staging_load",
        },
        "ai_use_cases": [
            "revenue trend and seasonal anomaly analysis",
            "customer segmentation and churn feature engineering",
            "inventory shortage forecasting",
            "promotion uplift and margin leakage analysis",
            "return root-cause and support sentiment analysis",
            "SQL and document evidence cross-validation",
        ],
        "timeline_events": list(TIMELINE_EVENTS),
    }


def _date_between(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _extension_transaction_date(rng: random.Random, profile: ExpansionProfile) -> date:
    if profile.preserved_live_transactions == 0:
        return _date_between(rng, profile.start_date, profile.end_date)
    while True:
        transaction_date = _date_between(rng, profile.start_date, profile.end_date)
        if not PRESERVED_BASELINE_START <= transaction_date <= PRESERVED_BASELINE_END:
            return transaction_date


def _csv_writer(handle: TextIO, fields: List[str]) -> csv.DictWriter:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    return writer


def _event_for_date(transaction_date: date) -> str:
    for event in reversed(TIMELINE_EVENTS):
        if event["start_date"] <= transaction_date.isoformat() <= event["end_date"]:
            return event["event_id"]
    return ""


def _stores(profile: ExpansionProfile) -> List[Dict[str, object]]:
    stores = []
    for index in range(1, profile.stores + 1):
        region = REGIONS[(index - 1) % len(REGIONS)]
        stores.append(
            {
                "store_id": f"STR{index:04d}",
                "region": region,
                "state_code": ("NY", "GA", "IL", "TX", "CA")[(index - 1) % len(REGIONS)],
                "format": ("Urban", "Suburban", "Outlet")[(index - 1) % 3],
                "opened_date": date(2016 + index % 6, index % 12 + 1, 1).isoformat(),
            }
        )
    return stores


def _vendors(profile: ExpansionProfile) -> List[Dict[str, object]]:
    rows = []
    for index in range(1, profile.vendors + 1):
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        rows.append(
            {
                "vendor_id": f"VEN{index:04d}",
                "vendor_name": f"{category} Supplier {index:04d}",
                "primary_category": category,
                "lead_time_days": 5 + index % 36,
                "risk_tier": ("Low", "Medium", "High")[index % 3],
            }
        )
    return rows


def _products(profile: ExpansionProfile, rng: random.Random) -> List[Dict[str, object]]:
    rows = []
    first_category_product = set()
    for index in range(1, profile.products + 1):
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        low, high = CATEGORY_PRICE_RANGES[category]
        list_price = round(rng.uniform(low, high), 2)
        if category in first_category_product:
            launch_date = _date_between(rng, profile.start_date, profile.end_date)
        else:
            launch_date = profile.start_date
            first_category_product.add(category)
        rows.append(
            {
                "product_id": f"SKU{index:06d}",
                "product_name": f"{category} Product {index:06d}",
                "category": category,
                "vendor_id": f"VEN{((index - 1) % profile.vendors) + 1:04d}",
                "list_price": list_price,
                "unit_cost": round(list_price * rng.uniform(0.47, 0.72), 2),
                "launch_date": launch_date.isoformat(),
            }
        )
    return rows


def _customer_rows(profile: ExpansionProfile, rng: random.Random) -> Iterator[Dict[str, object]]:
    for index in range(1, profile.customers + 1):
        region = rng.choice(REGIONS)
        yield {
            "customer_id": f"CUST{index:07d}",
            "home_region": region,
            "loyalty_tier": rng.choices(("Standard", "Silver", "Gold", "Platinum"), (60, 24, 12, 4))[0],
            "signup_date": _date_between(rng, profile.start_date, profile.end_date).isoformat(),
            "preferred_channel": rng.choices(CHANNELS, (41, 50, 9))[0],
        }


def _promotion_rows(profile: ExpansionProfile) -> Iterator[Dict[str, object]]:
    total_days = max((profile.end_date - profile.start_date).days, 1)
    for index in range(1, profile.promotions + 1):
        start = profile.start_date + timedelta(days=(index * 19) % total_days)
        end = min(start + timedelta(days=14 + index % 30), profile.end_date)
        yield {
            "promotion_id": f"PROMO{index:04d}",
            "campaign_name": f"Campaign {index:04d}",
            "category": CATEGORIES[(index - 1) % len(CATEGORIES)],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "discount_pct": (5, 10, 15, 20, 25)[index % 5],
            "channel": CHANNELS[index % len(CHANNELS)],
        }


def _write_rows(path: Path, fields: List[str], rows: Iterable[Dict[str, object]]) -> int:
    count = 0
    with path.open("w", newline="") as handle:
        writer = _csv_writer(handle, fields)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _generate_sales_and_related(
    profile: ExpansionProfile,
    output_dir: Path,
    rng: random.Random,
    stores: List[Dict[str, object]],
    products: List[Dict[str, object]],
    promotions: List[Dict[str, object]],
) -> Dict[str, object]:
    products_by_category: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for product in products:
        products_by_category[str(product["category"])].append(product)
    product_launch_dates: Dict[str, List[str]] = {}
    for category in CATEGORIES:
        products_by_category[category].sort(key=lambda item: str(item["launch_date"]))
        product_launch_dates[category] = [str(item["launch_date"]) for item in products_by_category[category]]

    active_promotions: Dict[tuple, Dict[str, object]] = {}
    for promotion in promotions:
        current_date = date.fromisoformat(str(promotion["start_date"]))
        end_date = date.fromisoformat(str(promotion["end_date"]))
        while current_date <= end_date:
            active_promotions[(promotion["category"], current_date.isoformat())] = promotion
            current_date += timedelta(days=1)

    sales_fields = [
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
    ]
    return_fields = [
        "return_id",
        "transaction_id",
        "product_id",
        "return_date",
        "return_reason",
        "refund_amount",
    ]
    yearly_revenue: Counter = Counter()
    category_revenue: Counter = Counter()
    return_count = 0
    total_revenue = 0.0
    generated_transaction_count = profile.transactions - profile.preserved_live_transactions

    with (output_dir / "sales_transactions.csv").open("w", newline="") as sales_handle, \
         (output_dir / "returns.csv").open("w", newline="") as returns_handle:
        sales_writer = _csv_writer(sales_handle, sales_fields)
        returns_writer = _csv_writer(returns_handle, return_fields)
        for index in range(1, generated_transaction_count + 1):
            transaction_date = _extension_transaction_date(rng, profile)
            category = rng.choices(CATEGORIES, CATEGORY_WEIGHTS)[0]
            eligible_count = bisect_right(product_launch_dates[category], transaction_date.isoformat())
            product = products_by_category[category][rng.randrange(eligible_count)]
            store = rng.choice(stores)
            channel = rng.choices(CHANNELS, (43, 49, 8))[0]
            quantity = rng.choices((1, 2, 3, 4), (56, 28, 12, 4))[0]
            season_factor = 1.14 if transaction_date.month in (11, 12) else 1.0
            event_id = _event_for_date(transaction_date)
            event_factor = 0.96 if event_id == "EVT-2025-01" and category == "Electronics" else 1.0
            promotion = active_promotions.get((category, transaction_date.isoformat()))
            apply_promotion = promotion is not None and rng.random() < 0.7
            discount_pct = int(promotion["discount_pct"]) if apply_promotion else 0
            unit_price = round(float(product["list_price"]) * season_factor * event_factor, 2)
            total_amount = round(quantity * unit_price * (1 - discount_pct / 100), 2)
            gross_margin = round(total_amount - quantity * float(product["unit_cost"]), 2)
            transaction_id = f"GEN-TXN{index:09d}"
            sales_writer.writerow(
                {
                    "transaction_id": transaction_id,
                    "transaction_date": transaction_date.isoformat(),
                    "customer_id": f"CUST{rng.randint(1, profile.customers):07d}",
                    "store_id": store["store_id"],
                    "channel": channel,
                    "product_id": product["product_id"],
                    "product_category": category,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_pct": discount_pct,
                    "total_amount": total_amount,
                    "gross_margin_amount": gross_margin,
                    "payment_method": rng.choice(PAYMENT_METHODS),
                    "promotion_id": promotion["promotion_id"] if apply_promotion else "",
                    "event_id": event_id,
                }
            )
            yearly_revenue[str(transaction_date.year)] += total_amount
            category_revenue[category] += total_amount
            total_revenue += total_amount

            if rng.random() < CATEGORY_RETURN_RATES[category]:
                return_count += 1
                returns_writer.writerow(
                    {
                        "return_id": f"RET{return_count:08d}",
                        "transaction_id": transaction_id,
                        "product_id": product["product_id"],
                        "return_date": min(
                            transaction_date + timedelta(days=rng.randint(1, 30)),
                            profile.end_date,
                        ).isoformat(),
                        "return_reason": rng.choice(
                            ("Defective", "Changed Mind", "Damaged", "Wrong Item", "Late Delivery")
                        ),
                        "refund_amount": total_amount,
                    }
                )

    return {
        "sales_transactions": generated_transaction_count,
        "returns": return_count,
        "total_revenue": round(total_revenue, 2),
        "revenue_by_year": {key: round(value, 2) for key, value in sorted(yearly_revenue.items())},
        "revenue_by_category": {key: round(value, 2) for key, value in sorted(category_revenue.items())},
    }


def _inventory_rows(
    profile: ExpansionProfile,
    rng: random.Random,
    stores: List[Dict[str, object]],
    products: List[Dict[str, object]],
) -> Iterator[Dict[str, object]]:
    for index in range(1, profile.inventory_snapshots + 1):
        product = rng.choice(products)
        store = rng.choice(stores)
        reorder_point = rng.randint(8, 80)
        stock_level = rng.randint(0, reorder_point * 5)
        yield {
            "snapshot_id": f"INV{index:09d}",
            "snapshot_date": _date_between(rng, profile.start_date, profile.end_date).isoformat(),
            "store_id": store["store_id"],
            "product_id": product["product_id"],
            "stock_level": stock_level,
            "reorder_point": reorder_point,
            "stockout_flag": "true" if stock_level == 0 else "false",
        }


def _support_rows(profile: ExpansionProfile, rng: random.Random) -> Iterator[Dict[str, object]]:
    for index in range(1, profile.support_cases + 1):
        category = rng.choice(CATEGORIES)
        issue_type = rng.choice(("Return", "Delivery", "Product Quality", "Billing", "Availability"))
        sentiment = rng.choices(("negative", "neutral", "positive"), (57, 31, 12))[0]
        yield {
            "case_id": f"CASE{index:08d}",
            "opened_date": _date_between(rng, profile.start_date, profile.end_date).isoformat(),
            "customer_id": f"CUST{rng.randint(1, profile.customers):07d}",
            "category": category,
            "issue_type": issue_type,
            "sentiment": sentiment,
            "summary": f"{sentiment} {issue_type.lower()} feedback for {category.lower()} purchase",
        }


def generate_staging_dataset(
    profile: ExpansionProfile,
    output_root: Path = OUTPUT_ROOT,
    seed: int = 20260524,
    overwrite: bool = False,
) -> Dict[str, object]:
    """Write a deterministic, linked CSV dataset to a non-production directory."""
    output_dir = Path(output_root) / profile.dataset_id
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"{output_dir} already exists. Refusing to overwrite a staged dataset without --overwrite."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    rng = random.Random(seed)
    stores = _stores(profile)
    vendors = _vendors(profile)
    products = _products(profile, rng)
    promotions = list(_promotion_rows(profile))
    generated_rows = {
        "business_events": _write_rows(
            output_dir / "business_events.csv",
            ["event_id", "start_date", "end_date", "event_type", "title", "impact_area"],
            TIMELINE_EVENTS,
        ),
        "stores": _write_rows(
            output_dir / "stores.csv",
            ["store_id", "region", "state_code", "format", "opened_date"],
            stores,
        ),
        "vendors": _write_rows(
            output_dir / "vendors.csv",
            ["vendor_id", "vendor_name", "primary_category", "lead_time_days", "risk_tier"],
            vendors,
        ),
        "products": _write_rows(
            output_dir / "products.csv",
            ["product_id", "product_name", "category", "vendor_id", "list_price", "unit_cost", "launch_date"],
            products,
        ),
        "customers": _write_rows(
            output_dir / "customers.csv",
            ["customer_id", "home_region", "loyalty_tier", "signup_date", "preferred_channel"],
            _customer_rows(profile, rng),
        ),
        "promotions": _write_rows(
            output_dir / "promotions.csv",
            ["promotion_id", "campaign_name", "category", "start_date", "end_date", "discount_pct", "channel"],
            promotions,
        ),
    }
    facts = _generate_sales_and_related(profile, output_dir, rng, stores, products, promotions)
    generated_rows["sales_transactions"] = int(facts["sales_transactions"])
    generated_rows["returns"] = int(facts["returns"])
    generated_rows["inventory_snapshots"] = _write_rows(
        output_dir / "inventory_snapshots.csv",
        ["snapshot_id", "snapshot_date", "store_id", "product_id", "stock_level", "reorder_point", "stockout_flag"],
        _inventory_rows(profile, rng, stores, products),
    )
    generated_rows["support_cases"] = _write_rows(
        output_dir / "support_cases.csv",
        ["case_id", "opened_date", "customer_id", "category", "issue_type", "sentiment", "summary"],
        _support_rows(profile, rng),
    )
    manifest = {
        **build_expansion_plan(profile),
        "seed": seed,
        "output_directory": str(output_dir),
        "generated_rows": generated_rows,
        "validation_scope": "generated_extension_only_live_2024_is_preserved_separately",
        "validation_kpis": {
            "total_revenue": facts["total_revenue"],
            "revenue_by_year": facts["revenue_by_year"],
            "revenue_by_category": facts["revenue_by_category"],
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _read_rows(path: Path) -> Iterator[Dict[str, str]]:
    with path.open(newline="") as handle:
        yield from csv.DictReader(handle)


def validate_staging_dataset(dataset_dir: Path) -> Dict[str, object]:
    """Validate staged files and their links without requiring a database."""
    dataset_dir = Path(dataset_dir)
    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    expected = manifest["generated_rows"]
    composition = manifest.get("sales_transaction_composition", {})
    preserved_rows = int(composition.get("preserved_live_2024_rows", 0))
    preserved_period = composition.get("preserved_date_range", {})
    preserved_start = preserved_period.get("start")
    preserved_end = preserved_period.get("end")
    errors: List[str] = []
    error_count = 0
    observed: Dict[str, int] = {}

    def record_error(message: str) -> None:
        nonlocal error_count
        error_count += 1
        if len(errors) < 50:
            errors.append(message)

    stores = {row["store_id"] for row in _read_rows(dataset_dir / "stores.csv")}
    vendors = {row["vendor_id"] for row in _read_rows(dataset_dir / "vendors.csv")}
    customers = {row["customer_id"] for row in _read_rows(dataset_dir / "customers.csv")}
    products = {row["product_id"]: row for row in _read_rows(dataset_dir / "products.csv")}
    promotions = {row["promotion_id"]: row for row in _read_rows(dataset_dir / "promotions.csv")}
    events = {row["event_id"] for row in _read_rows(dataset_dir / "business_events.csv")}
    observed.update(
        {
            "business_events": len(events),
            "stores": len(stores),
            "vendors": len(vendors),
            "products": len(products),
            "customers": len(customers),
            "promotions": len(promotions),
        }
    )
    for product in products.values():
        if product["vendor_id"] not in vendors:
            record_error(f"Product {product['product_id']} references missing vendor {product['vendor_id']}")

    revenue = Decimal("0.00")
    transaction_count = 0
    for row in _read_rows(dataset_dir / "sales_transactions.csv"):
        transaction_count += 1
        if (
            preserved_rows
            and preserved_start
            and preserved_end
            and preserved_start <= row["transaction_date"] <= preserved_end
        ):
            record_error(
                f"Transaction {row['transaction_id']} overlaps protected live baseline period "
                f"{preserved_start} through {preserved_end}"
            )
        product = products.get(row["product_id"])
        if row["customer_id"] not in customers:
            record_error(f"Transaction {row['transaction_id']} references missing customer")
        if row["store_id"] not in stores:
            record_error(f"Transaction {row['transaction_id']} references missing store")
        if product is None:
            record_error(f"Transaction {row['transaction_id']} references missing product")
        elif product["launch_date"] > row["transaction_date"]:
            record_error(f"Transaction {row['transaction_id']} occurs before product launch")
        if row["event_id"] and row["event_id"] not in events:
            record_error(f"Transaction {row['transaction_id']} references missing event")
        if row["promotion_id"]:
            promotion = promotions.get(row["promotion_id"])
            if promotion is None:
                record_error(f"Transaction {row['transaction_id']} references missing promotion")
            elif (
                promotion["category"] != row["product_category"]
                or not promotion["start_date"] <= row["transaction_date"] <= promotion["end_date"]
                or promotion["discount_pct"] != row["discount_pct"]
            ):
                record_error(f"Transaction {row['transaction_id']} has invalid promotion linkage")
        revenue += Decimal(row["total_amount"])
    observed["sales_transactions"] = transaction_count

    returns_count = 0
    for row in _read_rows(dataset_dir / "returns.csv"):
        returns_count += 1
        if row["product_id"] not in products:
            record_error(f"Return {row['return_id']} references missing product")
        try:
            transaction_number = int(row["transaction_id"].removeprefix("GEN-TXN"))
        except ValueError:
            transaction_number = 0
        if not 1 <= transaction_number <= transaction_count:
            record_error(f"Return {row['return_id']} references invalid transaction")
    observed["returns"] = returns_count

    inventory_count = 0
    for row in _read_rows(dataset_dir / "inventory_snapshots.csv"):
        inventory_count += 1
        if row["store_id"] not in stores or row["product_id"] not in products:
            record_error(f"Inventory snapshot {row['snapshot_id']} has missing dimension linkage")
    observed["inventory_snapshots"] = inventory_count

    support_count = 0
    for row in _read_rows(dataset_dir / "support_cases.csv"):
        support_count += 1
        if row["customer_id"] not in customers:
            record_error(f"Support case {row['case_id']} references missing customer")
    observed["support_cases"] = support_count

    for table, actual_rows in observed.items():
        if actual_rows != expected.get(table):
            record_error(f"{table} row count {actual_rows} does not match manifest {expected.get(table)}")

    expected_revenue = Decimal(str(manifest["validation_kpis"]["total_revenue"]))
    if revenue.quantize(Decimal("0.01")) != expected_revenue.quantize(Decimal("0.01")):
        record_error(f"Revenue {revenue} does not match manifest {expected_revenue}")

    return {
        "dataset_id": manifest["dataset_id"],
        "valid": error_count == 0,
        "staging_namespace": manifest["staging_namespace"],
        "row_counts": observed,
        "total_revenue": float(revenue),
        "errors": errors,
        "error_count": error_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate safe NexusIQ enterprise staging extracts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="Print the planned row volumes without writing files")
    plan.add_argument("--profile", choices=sorted(PROFILES), default="portfolio")
    generate = subparsers.add_parser("generate", help="Write linked staging CSV files and a KPI manifest")
    generate.add_argument("--profile", choices=sorted(PROFILES), default="pilot")
    generate.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    generate.add_argument("--seed", type=int, default=20260524)
    generate.add_argument("--overwrite", action="store_true")
    validate = subparsers.add_parser("validate", help="Validate staged CSV links and manifest KPIs")
    validate.add_argument("--dataset-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "plan":
        profile = PROFILES[args.profile]
        result = build_expansion_plan(profile)
    elif args.command == "generate":
        profile = PROFILES[args.profile]
        result = generate_staging_dataset(profile, args.output_root, args.seed, args.overwrite)
    elif args.command == "validate":
        result = validate_staging_dataset(args.dataset_dir)
    else:
        raise ValueError(f"Unsupported command: {args.command}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
