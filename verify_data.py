"""
Verify what data actually exists in the database
"""

from sqlalchemy import create_engine, text
from config.settings import settings
import pandas as pd

engine = create_engine(settings.database_url)

print("\n" + "="*60)
print("DATABASE DATA VERIFICATION")
print("="*60 + "\n")

# 1. Check date range
print("1️⃣  DATE RANGE CHECK")
print("-" * 60)

query = """
SELECT 
    MIN(transaction_date) as earliest_date,
    MAX(transaction_date) as latest_date,
    COUNT(*) as total_transactions
FROM sales_transactions;
"""

df = pd.read_sql(query, engine)
print(df.to_string(index=False))
print()

# 2. Check quarterly data
print("2️⃣  QUARTERLY DATA CHECK")
print("-" * 60)

query = """
SELECT 
    CASE 
        WHEN EXTRACT(MONTH FROM transaction_date) BETWEEN 1 AND 3 THEN 'Q1 2024'
        WHEN EXTRACT(MONTH FROM transaction_date) BETWEEN 4 AND 6 THEN 'Q2 2024'
        WHEN EXTRACT(MONTH FROM transaction_date) BETWEEN 7 AND 9 THEN 'Q3 2024'
        WHEN EXTRACT(MONTH FROM transaction_date) BETWEEN 10 AND 12 THEN 'Q4 2024'
    END as quarter,
    COUNT(*) as transactions,
    ROUND(SUM(total_amount)::numeric, 2) as total_revenue
FROM sales_transactions
GROUP BY quarter
ORDER BY quarter;
"""

df = pd.read_sql(query, engine)
print(df.to_string(index=False))
print()

# 3. Check regions
print("3️⃣  REGIONS CHECK")
print("-" * 60)

query = """
SELECT 
    region,
    COUNT(*) as transactions,
    ROUND(SUM(total_amount)::numeric, 2) as revenue
FROM sales_transactions
GROUP BY region
ORDER BY revenue DESC;
"""

df = pd.read_sql(query, engine)
print(df.to_string(index=False))
print()

# 4. Check categories
print("4️⃣  CATEGORIES CHECK")
print("-" * 60)

query = """
SELECT 
    product_category,
    COUNT(*) as transactions,
    ROUND(SUM(total_amount)::numeric, 2) as revenue
FROM sales_transactions
GROUP BY product_category
ORDER BY revenue DESC;
"""

df = pd.read_sql(query, engine)
print(df.to_string(index=False))
print()

# 5. Top products
print("5️⃣  TOP 10 PRODUCTS BY REVENUE")
print("-" * 60)

query = """
SELECT 
    product_name,
    COUNT(*) as transactions,
    SUM(quantity) as total_quantity,
    ROUND(SUM(total_amount)::numeric, 2) as total_revenue
FROM sales_transactions
GROUP BY product_name
ORDER BY total_revenue DESC
LIMIT 10;
"""

df = pd.read_sql(query, engine)
print(df.to_string(index=False))
print()

print("✅ Verification complete!\n")

engine.dispose()
