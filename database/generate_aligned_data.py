"""
Generate SQL data that EXACTLY matches PDF report numbers
Uses config/company_data.py as single source of truth
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config.settings import settings
from config.company_data import NEXUSIQ_METRICS
import numpy as np


class AlignedDataGenerator:
    """Generate transactions that sum to exact targets"""
    
    def __init__(self):
        self.engine = create_engine(settings.database_url)
        self.products = NEXUSIQ_METRICS["products"]
        
    def generate_quarter_transactions(self, quarter_key: str):
        """
        Generate transactions for a quarter that sum to EXACT targets
        
        Strategy:
        1. Calculate target totals from config
        2. Distribute across categories/regions using percentages
        3. Generate individual transactions that sum correctly
        4. Use statistical distribution for realistic amounts
        """
        
        quarter = NEXUSIQ_METRICS[quarter_key]
        print(f"\n{'='*60}")
        print(f"Generating {quarter_key}")
        print(f"{'='*60}")
        
        target_revenue = quarter["total_revenue"]
        target_count = quarter["total_transactions"]
        
        print(f"Target Revenue: ${target_revenue:,.2f}")
        print(f"Target Transactions: {target_count:,}")
        
        # Parse dates
        start_date = datetime.strptime(quarter["date_range"][0], "%Y-%m-%d")
        end_date = datetime.strptime(quarter["date_range"][1], "%Y-%m-%d")
        
        transactions = []
        
        # Generate transactions per category
        for category, cat_data in quarter["categories"].items():
            if isinstance(cat_data, dict):
                cat_revenue = cat_data["revenue"]
                cat_pct = cat_data["percentage"]
            else:  # Q1/Q2 have percentages only
                cat_pct = cat_data
                cat_revenue = target_revenue * cat_pct
            
            cat_txn_count = int(target_count * cat_pct)
            
            print(f"  {category}: ${cat_revenue:,.0f} ({cat_txn_count} txns)")
            
            # Generate transactions for this category
            category_txns = self._generate_category_transactions(
                category=category,
                target_revenue=cat_revenue,
                target_count=cat_txn_count,
                start_date=start_date,
                end_date=end_date,
                regions=quarter["regions"],
                payment_methods=quarter["payment_methods"]
            )
            
            transactions.extend(category_txns)
        
        # Adjust to hit exact total (rounding errors)
        actual_total = sum(t["total_amount"] for t in transactions)
        difference = target_revenue - actual_total
        
        if abs(difference) > 0.01:
            # Add difference to largest transaction
            largest_txn = max(transactions, key=lambda x: x["total_amount"])
            largest_txn["total_amount"] += difference
            print(f"  Adjusted by ${difference:.2f} to hit exact total")
        
        # Verify
        final_total = sum(t["total_amount"] for t in transactions)
        print(f"\n✅ Generated {len(transactions)} transactions")
        print(f"   Total: ${final_total:,.2f} (Target: ${target_revenue:,.2f})")
        print(f"   Difference: ${abs(final_total - target_revenue):.2f}")
        
        return transactions
    
    def _generate_category_transactions(
        self, 
        category: str,
        target_revenue: float,
        target_count: int,
        start_date: datetime,
        end_date: datetime,
        regions: dict,
        payment_methods: dict
    ):
        """Generate transactions for a category that sum to target"""
        
        transactions = []
        
        # Average transaction value
        avg_value = target_revenue / target_count
        
        # Use log-normal distribution for realistic transaction sizes
        # (most transactions are small, few are large)
        mu = np.log(avg_value)
        sigma = 0.5  # Controls spread
        
        amounts = np.random.lognormal(mu, sigma, target_count - 1)
        
        # Adjust so they sum to target (minus one transaction)
        amounts = amounts * (target_revenue * 0.99) / amounts.sum()
        
        # Last transaction fills the gap
        amounts = list(amounts) + [target_revenue - sum(amounts)]
        
        # Generate transaction records
        product_list = self.products[category]
        region_list = list(regions.keys())
        region_weights = [regions[r] if isinstance(regions[r], float) else regions[r]["percentage"] 
                         for r in region_list]
        payment_list = list(payment_methods.keys())
        payment_weights = list(payment_methods.values())
        
        for i, amount in enumerate(amounts):
            # Random date in quarter
            days_in_quarter = (end_date - start_date).days
            random_day = random.randint(0, days_in_quarter)
            txn_date = start_date + timedelta(days=random_day)
            
            # Random region (weighted)
            region = random.choices(region_list, weights=region_weights)[0]
            
            # Random payment method (weighted)
            payment = random.choices(payment_list, weights=payment_weights)[0]
            
            # Random product
            product = random.choice(product_list)
            
            # Quantity and unit price
            quantity = random.randint(1, 5)
            unit_price = amount / quantity
            
            # Store ID based on region
            store_prefix = region[0]  # E, W, N, S, C
            store_num = random.randint(1, 20)
            store_id = f"{store_prefix}{store_num:03d}"
            
            # Customer ID
            customer_id = f"CUST{random.randint(1000, 9999)}"
            
            transactions.append({
                "transaction_date": txn_date,
                "region": region,
                "store_id": store_id,
                "product_category": category,
                "product_name": product,
                "quantity": quantity,
                "unit_price": round(unit_price, 2),
                "total_amount": round(amount, 2),
                "customer_id": customer_id,
                "payment_method": payment
            })
        
        return transactions
    
    def clear_existing_data(self):
        """Delete all existing transactions"""
        print("\n🗑️  Clearing existing data...")
        with self.engine.connect() as conn:
            conn.execute(text("DELETE FROM sales_transactions"))
            conn.commit()
        print("✅ Database cleared")
    
    def insert_transactions(self, transactions):
        """Bulk insert transactions"""
        print(f"\n💾 Inserting {len(transactions)} transactions...")
        
        with self.engine.connect() as conn:
            for txn in transactions:
                conn.execute(text("""
                    INSERT INTO sales_transactions (
                        transaction_date, region, store_id,
                        product_category, product_name, quantity,
                        unit_price, total_amount, customer_id, payment_method
                    ) VALUES (
                        :transaction_date, :region, :store_id,
                        :product_category, :product_name, :quantity,
                        :unit_price, :total_amount, :customer_id, :payment_method
                    )
                """), txn)
            
            conn.commit()
        
        print("✅ Data inserted")
    
    def verify_alignment(self):
        """Verify database matches PDF targets"""
        print(f"\n{'='*60}")
        print("VERIFICATION: Database vs PDF Targets")
        print(f"{'='*60}")
        
        with self.engine.connect() as conn:
            # Q4 2024 Total
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as count,
                    SUM(total_amount) as revenue
                FROM sales_transactions
                WHERE transaction_date >= '2024-10-01'
                AND transaction_date <= '2024-12-31'
            """))
            row = result.fetchone()
            
            target_count = NEXUSIQ_METRICS["Q4_2024"]["total_transactions"]
            target_revenue = NEXUSIQ_METRICS["Q4_2024"]["total_revenue"]
            
            print(f"\nQ4 2024 Total:")
            print(f"  Transactions: {row[0]:,} (Target: {target_count:,}) "
                  f"{'✅' if abs(row[0] - target_count) < 100 else '⚠️'}")
            print(f"  Revenue: ${row[1]:,.2f} (Target: ${target_revenue:,.2f}) "
                  f"{'✅' if abs(row[1] - target_revenue) < 1000 else '⚠️'}")
            
            # Q4 Electronics
            result = conn.execute(text("""
                SELECT SUM(total_amount) as revenue
                FROM sales_transactions
                WHERE transaction_date >= '2024-10-01'
                AND product_category = 'Electronics'
            """))
            row = result.fetchone()
            
            target_elec = NEXUSIQ_METRICS["Q4_2024"]["categories"]["Electronics"]["revenue"]
            
            print(f"\nQ4 Electronics:")
            print(f"  Revenue: ${row[0]:,.2f} (Target: ${target_elec:,.2f}) "
                  f"{'✅' if abs(row[0] - target_elec) < 100000 else '⚠️'}")
            
            # Q3 2024 Total
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as count,
                    SUM(total_amount) as revenue
                FROM sales_transactions
                WHERE transaction_date >= '2024-07-01'
                AND transaction_date < '2024-10-01'
            """))
            row = result.fetchone()
            
            target_q3_count = NEXUSIQ_METRICS["Q3_2024"]["total_transactions"]
            target_q3_revenue = NEXUSIQ_METRICS["Q3_2024"]["total_revenue"]
            
            print(f"\nQ3 2024 Total:")
            print(f"  Transactions: {row[0]:,} (Target: {target_q3_count:,}) "
                  f"{'✅' if abs(row[0] - target_q3_count) < 100 else '⚠️'}")
            print(f"  Revenue: ${row[1]:,.2f} (Target: ${target_q3_revenue:,.2f}) "
                  f"{'✅' if abs(row[1] - target_q3_revenue) < 1000 else '⚠️'}")
            
            # Annual total
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as count,
                    SUM(total_amount) as revenue
                FROM sales_transactions
                WHERE transaction_date >= '2024-01-01'
                AND transaction_date < '2025-01-01'
            """))
            row = result.fetchone()
            
            print(f"\n2024 Annual Total:")
            print(f"  Transactions: {row[0]:,}")
            print(f"  Revenue: ${row[1]:,.2f}")
            
        print(f"\n{'='*60}")
        print("✅ Data alignment complete!")
        print(f"{'='*60}\n")


def main():
    """Main execution"""
    generator = AlignedDataGenerator()
    
    # Clear existing data
    generator.clear_existing_data()
    
    # Generate all quarters
    all_transactions = []
    
    for quarter in ["Q1_2024", "Q2_2024", "Q3_2024", "Q4_2024"]:
        quarter_txns = generator.generate_quarter_transactions(quarter)
        all_transactions.extend(quarter_txns)
    
    # Insert all at once
    generator.insert_transactions(all_transactions)
    
    # Verify alignment
    generator.verify_alignment()
    
    print("\n✅ Aligned data generation complete!")
    print(f"Total transactions: {len(all_transactions):,}")
    print(f"Total revenue: ${sum(t['total_amount'] for t in all_transactions):,.2f}")


if __name__ == "__main__":
    main()
