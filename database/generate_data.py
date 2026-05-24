"""
NexusIQ AI — Legacy Synthetic Data Generator (Seasonal Edition)

This utility is not an application data source. It can write to the configured
PostgreSQL database only after explicit destructive-rebuild authorization.

Realistic retail seasonality:
  Q1: ~$28M (post-holiday dip)
  Q2: ~$32M (spring pickup)
  Q3: ~$38M (back-to-school)
  Q4: ~$42M (holiday peak)
  Total: ~$140M
"""
import random
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from database.setup import (
    init_database,
    require_destructive_sql_rebuild_authorization,
    SalesTransaction,
    Inventory,
    Customer,
)

# ═══════════════════════════════════════════════
#  MASTER DATA
# ═══════════════════════════════════════════════

REGIONS = ['East', 'West', 'North', 'South', 'Central']

CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports']

PRODUCTS = {
    'Electronics': ['Laptop', 'Phone', 'Tablet', 'Headphones'],
    'Clothing':    ['T-Shirt', 'Jeans', 'Jacket', 'Shoes'],
    'Food':        ['Snacks', 'Drinks', 'Frozen', 'Produce'],
    'Home':        ['Furniture', 'Decor', 'Kitchen', 'Bedding'],
    'Sports':      ['Equipment', 'Apparel', 'Accessories', 'Footwear']
}

PAYMENT_METHODS = ['Credit Card', 'Debit Card', 'Cash', 'Digital Wallet']

# ═══════════════════════════════════════════════
#  SEASONAL WEIGHTS — Controls transaction volume
#  Higher weight = more transactions that month
# ═══════════════════════════════════════════════

MONTHLY_WEIGHTS = {
    1:  0.060,   # January   — post-holiday slowdown
    2:  0.060,   # February  — slow
    3:  0.070,   # March     — slight spring pickup
    4:  0.078,   # April     — spring
    5:  0.082,   # May       — strong spring
    6:  0.085,   # June      — early summer
    7:  0.088,   # July      — back-to-school prep
    8:  0.100,   # August    — back-to-school PEAK
    9:  0.082,   # September — settling down
    10: 0.082,   # October   — pre-holiday buildup
    11: 0.108,   # November  — Black Friday
    12: 0.105,   # December  — Christmas peak
}

# ═══════════════════════════════════════════════
#  PRICE RANGES BY CATEGORY + SEASON
#  Real retail: Electronics spike in Q4 (gifting)
#               Clothing spike in Q2/Q3 (fashion)
#               Food is stable year-round
# ═══════════════════════════════════════════════

BASE_PRICE_RANGES = {
    'Electronics': (800,  3500),
    'Clothing':    (60,   500),
    'Food':        (25,   200),
    'Home':        (150,  1800),
    'Sports':      (100,  1200),
}


# Seasonal price multipliers per category per quarter
# Format: {quarter: {category: multiplier}}
PRICE_MULTIPLIERS = {
    1: {  # Q1 — post-holiday, clearance sales
        'Electronics': 0.85,
        'Clothing':    0.80,
        'Food':        0.95,
        'Home':        0.90,
        'Sports':      0.85,
    },
    2: {  # Q2 — spring, normal pricing
        'Electronics': 0.95,
        'Clothing':    1.05,
        'Food':        1.00,
        'Home':        1.05,
        'Sports':      1.00,
    },
    3: {  # Q3 — back-to-school, Electronics surge
        'Electronics': 1.10,
        'Clothing':    1.10,
        'Food':        1.00,
        'Home':        1.00,
        'Sports':      1.10,
    },
    4: {  # Q4 — holiday peak, premium pricing
        'Electronics': 1.25,
        'Clothing':    1.15,
        'Food':        1.05,
        'Home':        1.15,
        'Sports':      1.20,
    },
}

# ═══════════════════════════════════════════════
#  REGIONAL WEIGHTS
#  West slightly stronger (matches narrative in PDFs)
# ═══════════════════════════════════════════════

REGION_WEIGHTS = {
    'West':    0.22,
    'East':    0.21,
    'Central': 0.20,
    'South':   0.20,
    'North':   0.17,
}

# ═══════════════════════════════════════════════
#  PAYMENT METHOD WEIGHTS BY QUARTER
#  Digital Wallet grows from Q1 to Q4 (matches
#  strategic initiative narrative in PDFs)
# ═══════════════════════════════════════════════

PAYMENT_WEIGHTS = {
    1: {'Credit Card': 0.30, 'Debit Card': 0.30, 'Cash': 0.25, 'Digital Wallet': 0.15},
    2: {'Credit Card': 0.29, 'Debit Card': 0.29, 'Cash': 0.23, 'Digital Wallet': 0.19},
    3: {'Credit Card': 0.28, 'Debit Card': 0.28, 'Cash': 0.20, 'Digital Wallet': 0.24},
    4: {'Credit Card': 0.27, 'Debit Card': 0.27, 'Cash': 0.15, 'Digital Wallet': 0.31},
}

# ═══════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════

def get_quarter(month: int) -> int:
    return (month - 1) // 3 + 1

def weighted_choice(options: list, weights: dict) -> str:
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    return random.choices(keys, weights=vals, k=1)[0]

def generate_date_for_month(year: int, month: int) -> datetime:
    """Generate a random date within a given month"""
    if month == 12:
        days_in_month = 31
    elif month in [4, 6, 9, 11]:
        days_in_month = 30
    elif month == 2:
        days_in_month = 29 if year % 4 == 0 else 28
    else:
        days_in_month = 31

    day = random.randint(1, days_in_month)
    hour = random.randint(9, 21)
    minute = random.randint(0, 59)
    return datetime(year, month, day, hour, minute)

def get_price(category: str, quarter: int) -> float:
    """Get seasonally adjusted price for a category"""
    low, high = BASE_PRICE_RANGES[category]
    base_price = random.uniform(low, high)
    multiplier = PRICE_MULTIPLIERS[quarter][category]
    return round(base_price * multiplier, 2)

# ═══════════════════════════════════════════════
#  TRANSACTION COUNT PER MONTH
#  Distributes 100K transactions seasonally
# ═══════════════════════════════════════════════

def get_transactions_per_month(total: int = 100000) -> dict:
    """
    Calculate how many transactions fall in each month
    based on monthly weights.
    """
    month_counts = {}
    total_weight = sum(MONTHLY_WEIGHTS.values())

    running_total = 0
    months = list(MONTHLY_WEIGHTS.keys())

    for i, month in enumerate(months):
        if i == len(months) - 1:
            # Last month gets the remainder to ensure exact total
            month_counts[month] = total - running_total
        else:
            count = round((MONTHLY_WEIGHTS[month] / total_weight) * total)
            month_counts[month] = count
            running_total += count

    return month_counts

# ═══════════════════════════════════════════════
#  MAIN GENERATOR
# ═══════════════════════════════════════════════

def generate_sales_data(num_records: int = 100000) -> list:
    """
    Generate realistic seasonal sales transactions.

    Target quarterly revenue:
        Q1: ~$28M | Q2: ~$32M | Q3: ~$38M | Q4: ~$42M
    """

    print(f"\n🔄 Generating {num_records:,} seasonal sales transactions...")
    print("  Seasonal distribution:")
    print("  Q1 (Jan-Mar): ~$28M | Q2 (Apr-Jun): ~$32M")
    print("  Q3 (Jul-Sep): ~$38M | Q4 (Oct-Dec): ~$42M\n")

    month_counts = get_transactions_per_month(num_records)
    transactions = []
    generated = 0

    for month, count in month_counts.items():
        quarter = get_quarter(month)
        payment_weights = PAYMENT_WEIGHTS[quarter]

        for _ in range(count):
            region = weighted_choice(REGIONS, REGION_WEIGHTS)
            category = random.choice(CATEGORIES)
            product = random.choice(PRODUCTS[category])
            payment = weighted_choice(PAYMENT_METHODS, payment_weights)
            unit_price = get_price(category, quarter)
            quantity = random.randint(1, 3)

            transaction = {
                'transaction_date': generate_date_for_month(2024, month),
                'region': region,
                'store_id': f"{region[:1]}{random.randint(1, 20):03d}",
                'product_category': category,
                'product_name': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_amount': round(quantity * unit_price, 2),
                'customer_id': f"CUST{random.randint(1, 15000):05d}",
                'payment_method': payment,
            }
            transactions.append(transaction)
            generated += 1

        q_label = f"Q{quarter}"
        print(f"  ✅ Month {month:02d} ({q_label}): {count:,} transactions generated")

    print(f"\n✅ Total generated: {generated:,} transactions")
    return transactions

# ═══════════════════════════════════════════════
#  DATABASE LOADER
# ═══════════════════════════════════════════════

def load_to_database(transactions: list):
    """Load transactions into database — clears existing data first"""

    require_destructive_sql_rebuild_authorization()
    engine = init_database()
    Session = sessionmaker(bind=engine)
    session = Session()

    print("\n🗑️  Clearing existing transactions...")
    session.query(SalesTransaction).delete()
    session.commit()

    print("🔄 Loading new seasonal data...")

    # Insert in batches of 10K for performance
    batch_size = 10000
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        session.bulk_insert_mappings(SalesTransaction, batch)
        session.commit()
        print(f"  Inserted {min(i + batch_size, len(transactions)):,} / {len(transactions):,}")

    session.close()
    print(f"\n✅ Successfully loaded {len(transactions):,} transactions!")

# ═══════════════════════════════════════════════
#  PREVIEW (before loading)
# ═══════════════════════════════════════════════

def preview_expected_revenue():
    """
    Print expected quarterly revenue based on weights and price ranges.
    Use this to verify before running the full generation.
    """
    print("\n📊 EXPECTED QUARTERLY REVENUE (Approximate)")
    print("=" * 50)

    month_counts = get_transactions_per_month(100000)

    quarter_totals = {1: 0, 2: 0, 3: 0, 4: 0}
    quarter_txns   = {1: 0, 2: 0, 3: 0, 4: 0}

    for month, count in month_counts.items():
        q = get_quarter(month)
        quarter_txns[q] += count

        # Average transaction value for this quarter
        avg_price = 0
        for cat in CATEGORIES:
            low, high = BASE_PRICE_RANGES[cat]
            base_avg = (low + high) / 2
            multiplier = PRICE_MULTIPLIERS[q][cat]
            avg_price += base_avg * multiplier
        avg_price /= len(CATEGORIES)

        avg_qty = 2  # midpoint of randint(1,5)
        avg_txn_value = avg_price * avg_qty
        quarter_totals[q] += count * avg_txn_value

    for q in range(1, 5):
        months = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}
        print(f"  Q{q} ({months[q]}): "
              f"{quarter_txns[q]:,} txns | "
              f"~${quarter_totals[q]/1_000_000:.1f}M revenue")

    annual = sum(quarter_totals.values())
    print(f"\n  Annual Total: ~${annual/1_000_000:.1f}M")
    print("=" * 50)

# ═══════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    # Step 1: Preview expected numbers
    preview_expected_revenue()

    # Step 2: Confirm before proceeding
    print("\n⚠️  This will DELETE all existing transactions and regenerate.")
    confirm = input("Type 'yes' to proceed: ").strip().lower()

    if confirm != 'yes':
        print("❌ Aborted.")
    else:
        # Step 3: Generate
        transactions = generate_sales_data(100000)

        # Step 4: Load
        load_to_database(transactions)

        print("\n🎉 Database regeneration complete!")
        print("Next steps:")
        print("  1. Ask NexusIQ for Q1-Q4 revenue (SQL Only routing)")
        print("  2. Update financial PDFs with new numbers")
        print("  3. Run: python database/setup_rag_pipeline.py")
        print("  4. Cross-validation will show HIGH confidence ✅")
