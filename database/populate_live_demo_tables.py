"""
Populate live public-schema demo tables derived from existing sales_transactions.

Creates/fills: customers, products, inventory, returns, support_cases in the
public schema. All data is consistent with the 100K live sales_transactions rows
(same customer_ids, product names, store_ids, regions). Never touches
sales_transactions or any staging schema.

Run dry-run (plan only):
    python -m database.populate_live_demo_tables plan

Execute:
    python -m database.populate_live_demo_tables load --confirm POPULATE_LIVE_DEMO_TABLES
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

CONFIRMATION_TOKEN = "POPULATE_LIVE_DEMO_TABLES"

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Emily", "Paul", "Dorothy", "Andrew", "Kimberly", "Joshua", "Helen",
    "Kevin", "Donna", "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa",
    "Ronald", "Deborah", "Edward", "Stephanie", "Jason", "Rebecca", "Jeffrey", "Sharon",
    "Ryan", "Laura", "Jacob", "Cynthia", "Gary", "Kathleen", "Nicholas", "Amy",
    "Eric", "Angela", "Jonathan", "Shirley", "Stephen", "Emma", "Larry", "Brenda",
    "Justin", "Pamela", "Scott", "Emma", "Brandon", "Anna", "Frank", "Christine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]

REGION_TO_PREFIX = {
    "North": "N",
    "South": "S",
    "East": "E",
    "West": "W",
    "Central": "C",
}

SUPPORT_SUBJECTS = [
    "Order not received",
    "Wrong item delivered",
    "Return request",
    "Billing discrepancy",
    "Product defect",
    "Late delivery",
    "Account access issue",
    "Refund status inquiry",
    "Price match request",
    "Damaged packaging",
    "Missing item from order",
    "Subscription cancellation",
    "Loyalty points not credited",
    "Store credit inquiry",
    "Product availability question",
]

SUPPORT_STATUSES = ["open", "in_progress", "resolved", "closed"]
SUPPORT_PRIORITIES = ["low", "medium", "high", "urgent"]
RETURN_REASONS = [
    "Changed mind",
    "Defective product",
    "Wrong size",
    "Not as described",
    "Better price found",
    "Duplicate order",
    "Quality not satisfactory",
]
RETURN_STATUSES = ["pending", "approved", "received", "refunded", "rejected"]

PRODUCT_DESCRIPTIONS = {
    "Jacket": "Premium outerwear for all seasons, water-resistant with thermal lining",
    "Jeans": "Classic denim jeans, straight cut, available in multiple washes",
    "Shoes": "Comfortable all-day footwear with ergonomic sole support",
    "T-Shirt": "100% cotton casual tee, pre-shrunk, available in 12 colors",
    "Headphones": "Over-ear wireless headphones, 30hr battery, active noise cancellation",
    "Laptop": "High-performance laptop, Intel Core i7, 16GB RAM, 512GB SSD",
    "Phone": "Latest smartphone, 5G capable, 128GB storage, triple camera system",
    "Tablet": "10-inch display tablet, lightweight, ideal for work and entertainment",
    "Drinks": "Assorted beverage selection including sparkling water and juice",
    "Frozen": "Flash-frozen meal kit, chef-prepared, ready in under 15 minutes",
    "Produce": "Fresh seasonal produce sourced from local certified farms",
    "Snacks": "Curated snack variety pack, mix of sweet and savory options",
    "Bedding": "400-thread-count Egyptian cotton bedding set, hypoallergenic",
    "Decor": "Modern home accent piece, handcrafted ceramic with matte finish",
    "Furniture": "Solid wood accent furniture, natural finish, easy assembly",
    "Kitchen": "Stainless steel kitchen essentials set, dishwasher safe",
    "Accessories": "Multi-sport accessories bundle for training and competition",
    "Apparel": "Moisture-wicking athletic wear, four-way stretch fabric",
    "Equipment": "Professional-grade training equipment, adjustable resistance",
    "Footwear": "High-traction sports footwear, breathable mesh upper",
}

_rng = random.Random(42)  # deterministic for reproducibility


def _random_name() -> tuple[str, str]:
    return _rng.choice(FIRST_NAMES), _rng.choice(LAST_NAMES)


def _random_email(first: str, last: str, customer_id: str) -> str:
    domain = _rng.choice(EMAIL_DOMAINS)
    suffix = customer_id[-4:]
    return f"{first.lower()}.{last.lower()}{suffix}@{domain}"


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=_rng.randint(0, delta))


def _fetch_customer_aggregates(cur) -> list[dict]:
    # dominant region = mode; ties broken by region name alphabetically
    cur.execute("""
        WITH ranked AS (
            SELECT
                customer_id,
                region,
                ROUND(SUM(total_amount)::numeric, 2) AS total_purchases,
                MIN(transaction_date::date) AS first_purchase,
                COUNT(*) AS txn_count,
                ROW_NUMBER() OVER (
                    PARTITION BY customer_id
                    ORDER BY COUNT(*) DESC, region
                ) AS rn
            FROM sales_transactions
            GROUP BY customer_id, region
        )
        SELECT customer_id, region, total_purchases, first_purchase
        FROM (
            SELECT
                customer_id,
                region,
                SUM(total_purchases) OVER (PARTITION BY customer_id) AS total_purchases,
                MIN(first_purchase) OVER (PARTITION BY customer_id) AS first_purchase,
                rn
            FROM ranked
        ) t
        WHERE rn = 1
        ORDER BY customer_id
    """)
    return [
        {
            "customer_id": row[0],
            "region": row[1],
            "total_purchases": float(row[2]),
            "first_purchase": row[3],
        }
        for row in cur.fetchall()
    ]


def _fetch_product_prices(cur) -> dict[str, dict]:
    cur.execute("""
        SELECT
            product_name,
            product_category,
            ROUND(AVG(unit_price)::numeric, 2) AS avg_price,
            ROUND(MIN(unit_price)::numeric, 2) AS min_price,
            ROUND(MAX(unit_price)::numeric, 2) AS max_price
        FROM sales_transactions
        GROUP BY product_name, product_category
        ORDER BY product_category, product_name
    """)
    return {
        row[0]: {
            "category": row[1],
            "avg_price": float(row[2]),
            "min_price": float(row[3]),
            "max_price": float(row[4]),
        }
        for row in cur.fetchall()
    }


def _fetch_stores(cur) -> list[str]:
    cur.execute("SELECT DISTINCT store_id FROM sales_transactions ORDER BY store_id")
    return [row[0] for row in cur.fetchall()]


def _fetch_sample_transactions(cur, n: int) -> list[dict]:
    cur.execute(f"""
        SELECT id, customer_id, product_name, total_amount, transaction_date, store_id
        FROM sales_transactions
        ORDER BY RANDOM()
        LIMIT {n}
    """)
    cols = ["id", "customer_id", "product_name", "total_amount", "transaction_date", "store_id"]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _create_missing_tables(cur) -> None:
    # Ensure customers.customer_id has a unique constraint (table pre-exists but may lack it)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'public.customers'::regclass
                AND contype = 'u'
                AND conname = 'customers_customer_id_key'
            ) THEN
                ALTER TABLE public.customers ADD CONSTRAINT customers_customer_id_key UNIQUE (customer_id);
            END IF;
        END $$
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.products (
            id SERIAL PRIMARY KEY,
            product_name VARCHAR(100) NOT NULL UNIQUE,
            category VARCHAR(50) NOT NULL,
            avg_unit_price DOUBLE PRECISION,
            min_unit_price DOUBLE PRECISION,
            max_unit_price DOUBLE PRECISION,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.returns (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER,
            customer_id VARCHAR(20),
            product_name VARCHAR(100),
            return_date TIMESTAMP,
            reason VARCHAR(100),
            refund_amount DOUBLE PRECISION,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.support_cases (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(20),
            subject VARCHAR(200),
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP
        )
    """)


def build_plan(cur) -> dict:
    customers = _fetch_customer_aggregates(cur)
    products = _fetch_product_prices(cur)
    stores = _fetch_stores(cur)
    n_returns = 3000
    n_support = 2000
    return {
        "action": "populate_live_demo_tables",
        "dry_run": True,
        "tables": {
            "customers": {"rows": len(customers), "source": "aggregated from sales_transactions"},
            "products": {"rows": len(products), "source": "derived from sales_transactions"},
            "inventory": {"rows": len(stores) * len(products), "source": "stores × products cross-join"},
            "returns": {"rows": n_returns, "source": "random 3% sample of transactions"},
            "support_cases": {"rows": n_support, "source": "generated with customer_ids from sales"},
        },
        "estimated_size_mb": round(
            (len(customers) * 150 + len(products) * 300 + len(stores) * len(products) * 120
             + n_returns * 160 + n_support * 200) / 1024 / 1024,
            2,
        ),
        "safety": "public schema only — never touches nexusiq_expansion_staging or sales_transactions",
    }


def _execv(cur, sql: str, data: list, page_size: int = 200) -> None:
    """Bulk-insert using execute_values — one statement per page, fast over remote DB."""
    from psycopg2.extras import execute_values
    execute_values(cur, sql, data, page_size=page_size)


def load_tables(
    *,
    confirmation: Optional[str],
    database_url: Optional[str] = None,
    _connection_factory=None,
) -> dict:
    if confirmation != CONFIRMATION_TOKEN:
        raise RuntimeError(
            f"Provide --confirm {CONFIRMATION_TOKEN} to execute."
        )

    if database_url is None:
        database_url = os.getenv("NEXUSIQ_FINANCIAL_DB_URL") or os.getenv("DATABASE_URL")
        if database_url is None:
            from config.settings import settings
            database_url = settings.database_url

    if _connection_factory is None:
        import psycopg2
        _connection_factory = psycopg2.connect

    conn = _connection_factory(database_url)
    results = {}
    try:
        cur = conn.cursor()

        _create_missing_tables(cur)
        conn.commit()

        # --- customers ---
        customer_rows = _fetch_customer_aggregates(cur)
        cur.execute("SELECT COUNT(*) FROM public.customers")
        existing = cur.fetchone()[0]
        if existing > 0:
            results["customers"] = f"skipped — {existing:,} rows already present"
        else:
            signup_end = date(2023, 12, 31)
            signup_start = date(2018, 1, 1)
            batch = []
            for i, c in enumerate(customer_rows):
                first, last = _random_name()
                email = _random_email(first, last, c["customer_id"])
                signup = _random_date(signup_start, c["first_purchase"] or signup_end)
                batch.append((
                    c["customer_id"], f"{first} {last}", email,
                    c["region"], signup, c["total_purchases"],
                ))
            conn.commit()
            _execv(
                cur,
                "INSERT INTO public.customers (customer_id, name, email, region, signup_date, total_purchases) "
                "VALUES %s ON CONFLICT (customer_id) DO NOTHING",
                batch,
                page_size=200,
            )
            conn.commit()
            results["customers"] = f"inserted {len(customer_rows):,} rows"

        # --- products ---
        product_data = _fetch_product_prices(cur)
        cur.execute("SELECT COUNT(*) FROM public.products")
        existing = cur.fetchone()[0]
        if existing > 0:
            results["products"] = f"skipped — {existing:,} rows already present"
        else:
            prod_batch = [
                (name, info["category"], info["avg_price"], info["min_price"], info["max_price"],
                 PRODUCT_DESCRIPTIONS.get(name, ""))
                for name, info in product_data.items()
            ]
            _execv(
                cur,
                "INSERT INTO public.products (product_name, category, avg_unit_price, min_unit_price, max_unit_price, description) "
                "VALUES %s ON CONFLICT (product_name) DO NOTHING",
                prod_batch,
            )
            conn.commit()
            results["products"] = f"inserted {len(product_data):,} rows"

        # --- inventory ---
        stores = _fetch_stores(cur)
        cur.execute("SELECT COUNT(*) FROM public.inventory")
        existing = cur.fetchone()[0]
        if existing > 0:
            results["inventory"] = f"skipped — {existing:,} rows already present"
        else:
            product_names = list(product_data.keys())
            inv_batch = []
            now = datetime.now()
            for store in stores:
                for product in product_names:
                    stock = _rng.randint(10, 500)
                    reorder = _rng.randint(5, 50)
                    last_restocked = now - timedelta(days=_rng.randint(1, 90))
                    inv_batch.append((store, product, stock, reorder, last_restocked))
            _execv(
                cur,
                "INSERT INTO public.inventory (store_id, product_name, stock_level, reorder_point, last_restocked) "
                "VALUES %s",
                inv_batch,
                page_size=200,
            )
            conn.commit()
            results["inventory"] = f"inserted {len(inv_batch):,} rows"

        # --- returns ---
        cur.execute("SELECT COUNT(*) FROM public.returns")
        existing = cur.fetchone()[0]
        if existing > 0:
            results["returns"] = f"skipped — {existing:,} rows already present"
        else:
            sample_txns = _fetch_sample_transactions(cur, 3000)
            returns_batch = []
            for txn in sample_txns:
                return_date = txn["transaction_date"] + timedelta(days=_rng.randint(1, 30))
                refund = round(txn["total_amount"] * _rng.uniform(0.8, 1.0), 2)
                returns_batch.append((
                    txn["id"], txn["customer_id"], txn["product_name"],
                    return_date, _rng.choice(RETURN_REASONS),
                    refund, _rng.choice(RETURN_STATUSES),
                ))
            _execv(
                cur,
                "INSERT INTO public.returns (transaction_id, customer_id, product_name, return_date, reason, refund_amount, status) "
                "VALUES %s",
                returns_batch,
                page_size=200,
            )
            conn.commit()
            results["returns"] = f"inserted {len(returns_batch):,} rows"

        # --- support_cases ---
        cur.execute("SELECT COUNT(*) FROM public.support_cases")
        existing = cur.fetchone()[0]
        if existing > 0:
            results["support_cases"] = f"skipped — {existing:,} rows already present"
        else:
            cur.execute("SELECT customer_id FROM sales_transactions GROUP BY customer_id ORDER BY RANDOM() LIMIT 2000")
            cust_sample = [row[0] for row in cur.fetchall()]
            cases_batch = []
            start_2024 = datetime(2024, 1, 1)
            end_2024 = datetime(2024, 12, 31)
            for cid in cust_sample:
                created = start_2024 + timedelta(
                    seconds=_rng.randint(0, int((end_2024 - start_2024).total_seconds()))
                )
                status = _rng.choice(SUPPORT_STATUSES)
                resolved_at = None
                if status in ("resolved", "closed"):
                    resolved_at = created + timedelta(days=_rng.randint(1, 14))
                cases_batch.append((
                    cid, _rng.choice(SUPPORT_SUBJECTS),
                    _rng.choice(SUPPORT_PRIORITIES), status,
                    created, resolved_at,
                ))
            _execv(
                cur,
                "INSERT INTO public.support_cases (customer_id, subject, priority, status, created_at, resolved_at) "
                "VALUES %s",
                cases_batch,
                page_size=200,
            )
            conn.commit()
            results["support_cases"] = f"inserted {len(cases_batch):,} rows"

        # final size report
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())), pg_database_size(current_database())")
        sz_pretty, sz_bytes = cur.fetchone()
        results["db_size_after"] = sz_pretty
        results["remaining_mb"] = round((500 * 1024 * 1024 - sz_bytes) / 1024 / 1024, 1)

    finally:
        conn.close()

    return {"dry_run": False, "tables_loaded": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate live demo tables from sales_transactions data")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("plan")

    load_cmd = sub.add_parser("load")
    load_cmd.add_argument("--confirm", required=True, help=f"Must be: {CONFIRMATION_TOKEN}")
    load_cmd.add_argument("--database-url")

    args = parser.parse_args()

    if args.command == "plan":
        import psycopg2
        from config.settings import settings
        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        plan = build_plan(cur)
        conn.close()
        print(json.dumps(plan, indent=2))
    elif args.command == "load":
        result = load_tables(
            confirmation=args.confirm,
            database_url=getattr(args, "database_url", None),
        )
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
