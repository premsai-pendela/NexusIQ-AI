"""
NexusIQ AI — Synthetic Data Generator
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from database.setup import init_database, SalesTransaction, Inventory, Customer
import random

def generate_sales_data(num_records=100000):
    """Generate synthetic sales transactions"""
    
    print(f"🔄 Generating {num_records:,} sales transactions...")
    
    regions = ['East', 'West', 'North', 'South', 'Central']
    categories = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports']
    products = {
        'Electronics': ['Laptop', 'Phone', 'Tablet', 'Headphones'],
        'Clothing': ['T-Shirt', 'Jeans', 'Jacket', 'Shoes'],
        'Food': ['Snacks', 'Drinks', 'Frozen', 'Produce'],
        'Home': ['Furniture', 'Decor', 'Kitchen', 'Bedding'],
        'Sports': ['Equipment', 'Apparel', 'Accessories', 'Footwear']
    }
    payment_methods = ['Credit Card', 'Debit Card', 'Cash', 'Digital Wallet']
    
    # Generate transactions
    transactions = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    date_range_days = (end_date - start_date).days

    for i in range(num_records):
        region = random.choice(regions)
        category = random.choice(categories)
        product = random.choice(products[category])

        transaction = {
            'transaction_date': start_date + timedelta(days=random.randint(0, date_range_days)),
            'region': region,
            'store_id': f"{region[:1]}{random.randint(1, 20):03d}",
            'product_category': category,
            'product_name': product,
            'quantity': random.randint(1, 10),
            'unit_price': round(random.uniform(10, 500), 2),
            'customer_id': f"CUST{random.randint(1, 5000):05d}",
            'payment_method': random.choice(payment_methods)
        }
        transaction['total_amount'] = round(
            transaction['quantity'] * transaction['unit_price'], 2
        )
        transactions.append(transaction)
        
        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1:,} records...")
    
    return transactions

def load_to_database(transactions):
    """Load data into PostgreSQL"""
    engine = init_database()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("🔄 Loading data into PostgreSQL...")
    
    # Bulk insert
    session.bulk_insert_mappings(SalesTransaction, transactions)
    session.commit()
    session.close()
    
    print(f"✅ Loaded {len(transactions):,} transactions into database!")

if __name__ == "__main__":
    transactions = generate_sales_data(100000)
    load_to_database(transactions)
