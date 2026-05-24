"""
NexusIQ AI — Database Schema Setup
"""
import os

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config.settings import settings

Base = declarative_base()


def require_destructive_sql_rebuild_authorization() -> None:
    """Require an explicit operator opt-in before deleting relational facts."""
    enabled = os.getenv("NEXUSIQ_ALLOW_SQL_REBUILD", "").strip().lower()
    if enabled not in {"1", "true", "yes"}:
        raise RuntimeError(
            "Refusing to delete or repopulate the configured PostgreSQL database. "
            "NexusIQ uses Supabase as its relational source. Set "
            "NEXUSIQ_ALLOW_SQL_REBUILD=true only for an intentional, reviewed rebuild."
        )

# ═══════════════════════════════════════════════
#  SCHEMA DESIGN
# ═══════════════════════════════════════════════

class SalesTransaction(Base):
    """Sales transactions table"""
    __tablename__ = 'sales_transactions'
    
    id = Column(Integer, primary_key=True)
    transaction_date = Column(DateTime, nullable=False)
    region = Column(String(50), nullable=False)
    store_id = Column(String(20), nullable=False)
    product_category = Column(String(50))
    product_name = Column(String(200))
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_amount = Column(Float)
    customer_id = Column(String(50))
    payment_method = Column(String(30))

class Inventory(Base):
    """Inventory levels table"""
    __tablename__ = 'inventory'
    
    id = Column(Integer, primary_key=True)
    store_id = Column(String(20), nullable=False)
    product_name = Column(String(200), nullable=False)
    stock_level = Column(Integer)
    reorder_point = Column(Integer)
    last_restocked = Column(DateTime)

class Customer(Base):
    """Customer information table"""
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(200))
    email = Column(String(200))
    region = Column(String(50))
    signup_date = Column(DateTime)
    total_purchases = Column(Float, default=0.0)
    
# ═══════════════════════════════════════════════
#  DATABASE INITIALIZATION
# ═══════════════════════════════════════════════

def init_database():
    """Create all tables"""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    print("✅ Database schema created successfully!")
    return engine

if __name__ == "__main__":
    init_database()
