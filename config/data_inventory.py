"""
NexusIQ AI — Data Inventory
Maps what data exists in SQL, RAG, and Web sources
"""

from datetime import datetime

# ═══════════════════════════════════════════════════════
#  SQL DATABASE INVENTORY
# ═══════════════════════════════════════════════════════

SQL_INVENTORY = {
    "date_range": {
        "start": datetime(2024, 1, 1),
        "end": datetime(2024, 12, 31),
        "quarters": {
            "Q1": ("2024-01-01", "2024-03-31"),
            "Q2": ("2024-04-01", "2024-06-30"),
            "Q3": ("2024-07-01", "2024-09-30"),
            "Q4": ("2024-10-01", "2024-12-31"),
        },
        "note": "All transaction data is 2024 only"
    },
    
    "tables": {
        "sales_transactions": {
            "columns": [
                "transaction_date", "region", "store_id", 
                "product_category", "product_name", "quantity",
                "unit_price", "total_amount", "customer_id", "payment_method"
            ],
            "row_count": 100000,
            "can_answer": [
                "revenue", "sales", "transactions", "quantity",
                "products", "regions", "stores", "payment methods",
                "trends", "rankings", "aggregations", "daily/monthly data"
            ]
        },
        "customers": {
            "columns": ["customer_id", "name", "email", "region", "signup_date", "total_purchases"],
            "row_count": 0,
            "can_answer": [],
            "note": "Schema exists in Supabase, but no dimension records are currently populated."
        },
        "inventory": {
            "columns": ["store_id", "product_name", "stock_level", "reorder_point", "last_restocked"],
            "row_count": 0,
            "can_answer": [],
            "note": "Schema exists in Supabase, but no inventory records are currently populated."
        }
    },
    
    "regions": ["East", "West", "North", "South", "Central"],
    "categories": ["Electronics", "Clothing", "Food", "Home", "Sports"],
    "payment_methods": ["Credit Card", "Debit Card", "Cash", "Digital Wallet"],
    
    "cannot_answer": [
        "Future data (2025+)",
        "Historical data (pre-2024)",
        "Policies", "Strategies", "Plans",
        "Competitor data", "Industry trends",
        "Employee information", "Contracts"
    ]
}

# ═══════════════════════════════════════════════════════
#  RAG DOCUMENT INVENTORY
# ═══════════════════════════════════════════════════════

RAG_INVENTORY = {
    "total_documents": 25,
    "categories": {
        "financial": {
            "count": 7,
            "files": [
                "01_Q4_2024_Financial_Report.pdf",
                "02_Q3_2024_Financial_Report.pdf",
                "03_Annual_Report_2023.pdf",
                "04_Budget_Forecast_2025.pdf",
                "05_Investor_Presentation_Dec2024.pdf",
                "06_Q1_2024_Financial_Report.pdf",
                "07_Q2_2024_Financial_Report.pdf"
            ],
            "can_answer": [
                "quarterly revenue (reported numbers)",
                "strategic initiatives", "performance metrics",
                "growth rates", "Digital Wallet adoption",
                "regional performance summaries"
            ],
            "date_coverage": "Q1-Q4 2024"
        },
        
        "products_operations": {
            "count": 4,
            "files": [
                "Inventory_Management_Policy.pdf",
                "Product_Catalog_Electronics_2024.pdf",
                "Returns_Refunds_Policy.pdf",
                "Store_Operations_Manual.pdf"
            ],
            "can_answer": [
                "return policies", "inventory policy", "product catalog",
                "store operations"
            ]
        },

        "market_intelligence": {
            "count": 5,
            "files": [
                "Brand_Perception_Study.pdf",
                "Competitor_Pricing_Strategy.pdf",
                "Customer_Satisfaction_Survey_2024.pdf",
                "Industry_Trends_Retail_2024.pdf",
                "Market_Analysis_Electronics_2024.pdf"
            ],
            "can_answer": [
                "market studies", "competitor pricing strategy",
                "customer satisfaction", "industry trends"
            ]
        },
        
        "strategic_plans": {
            "count": 3,
            "files": [
                "Digital_Transformation_Roadmap.pdf",
                "Expansion_Feasibility_Study.pdf",
                "Strategic_Plan_2025.pdf"
            ],
            "can_answer": [
                "expansion plans", "budget allocations",
                "strategic initiatives", "roadmaps",
                "competitive analysis", "future plans"
            ]
        },
        
        "contracts": {
            "count": 4,
            "can_answer": ["vendor agreements", "partnerships", "contracts"]
        },

        "hr_compliance": {
            "count": 2,
            "files": [
                "Compliance_Training_Materials.pdf",
                "Employee_Handbook_2024.pdf"
            ],
            "can_answer": ["employee guidelines", "compliance requirements"]
        }
    },
    
    "cannot_answer": [
        "Real-time transaction data",
        "Granular daily/store-level data",
        "Current competitor pricing (uses web scraping)",
        "Data not in the 25 PDFs"
    ]
}

# ═══════════════════════════════════════════════════════
#  WEB SCRAPING INVENTORY
# ═══════════════════════════════════════════════════════

WEB_INVENTORY = {
    "categories": {
        "electronics": {
            "sources": ["Newegg (BeautifulSoup)", "Mock Data"],
            "can_answer": ["laptop prices", "headphone prices", "TV prices", "gaming gear"]
        },
        "home": {
            "sources": ["IKEA (Selenium)", "Mock Data"],
            "can_answer": ["furniture prices", "home goods", "decor"]
        },
        "sports": {
            "sources": ["Campmor (Shopify API)", "Mock Data"],
            "can_answer": ["camping gear", "outdoor equipment", "sports gear"]
        },
        "food": {
            "sources": ["Swanson Vitamins (Shopify API)", "Mock Data"],
            "can_answer": ["supplements", "vitamins", "health products"]
        },
        "clothing": {
            "sources": ["Mock Data Only"],
            "can_answer": ["clothing prices (limited to mock data)"]
        }
    },
    
    "cache_ttl": "24 hours",
    
    "cannot_answer": [
        "Historical competitor pricing",
        "Our own pricing (use SQL)",
        "Non-competitor data"
    ]
}

# ═══════════════════════════════════════════════════════
#  CROSS-VALIDATION MAP
# ═══════════════════════════════════════════════════════

CROSS_VALIDATION_MAP = {
    # Topics that can be validated across SQL + RAG
    "validatable": {
        "Q1_2024_revenue": {
            "sql": "SUM(total_amount) WHERE transaction_date Q1 2024",
            "rag": "06_Q1_2024_Financial_Report.pdf"
        },
        "Q2_2024_revenue": {
            "sql": "SUM(total_amount) WHERE transaction_date Q2 2024",
            "rag": "07_Q2_2024_Financial_Report.pdf"
        },
        "Q3_2024_revenue": {
            "sql": "SUM(total_amount) WHERE transaction_date Q3 2024",
            "rag": "02_Q3_2024_Financial_Report.pdf"
        },
        "Q4_2024_revenue": {
            "sql": "SUM(total_amount) WHERE transaction_date Q4 2024",
            "rag": "01_Q4_2024_Financial_Report.pdf"
        },
        "electronics_revenue": {
            "sql": "SUM(total_amount) WHERE product_category = 'Electronics'",
            "rag": "Category reports in quarterly PDFs"
        },
        "digital_wallet_adoption": {
            "sql": "COUNT(*) WHERE payment_method = 'Digital Wallet'",
            "rag": "Digital_Wallet_Initiative.pdf + Quarterly reports"
        }
    },
    
    # Topics that exist in only one source
    "sql_only": [
        "daily/monthly granular data",
        "store-level data",
        "transaction details",
        "customer records"
    ],
    
    "rag_only": [
        "policies",
        "strategic plans",
        "contracts",
        "future projections"
    ],
    
    "web_only": [
        "live competitor pricing"
    ]
}


# ═══════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════

def can_sql_answer(question: str) -> dict:
    """
    Check if SQL database can answer this question
    
    Returns:
        {
            "can_answer": bool,
            "confidence": "high" | "medium" | "low",
            "reason": str,
            "suggested_query": str (optional)
        }
    """
    question_lower = question.lower()
    
    # Check for SQL-answerable patterns
    sql_patterns = [
        "revenue", "sales", "transactions", "quantity", "top", "best",
        "region", "category", "product", "payment", "store", "customer",
        "total", "count", "average", "sum", "monthly", "daily",
        # Analytical patterns computable from transaction data
        "quarter", "quarterly", "growth", "rate", "trend", "increase",
        "decrease", "change", "compare", "highest", "lowest", "ranking",
        # Store/region/performance patterns — clearly SQL territory
        "store_id", "store", "performance", "performing", "best", "worst"
    ]
    
    has_sql_pattern = any(p in question_lower for p in sql_patterns)
    
    # Check for date ranges
    has_valid_date = any(q in question_lower for q in ["2024", "q1", "q2", "q3", "q4"])
    has_invalid_date = any(year in question_lower for year in ["2020", "2021", "2022", "2023", "2025"])
    
    if has_invalid_date:
        return {
            "can_answer": False,
            "confidence": "none",
            "reason": f"SQL only has 2024 data. Question asks for data outside this range.",
            "date_range_available": "2024-01-01 to 2024-12-31"
        }
    
    if has_sql_pattern:
        return {
            "can_answer": True,
            "confidence": "high",
            "reason": "Question asks for quantitative data available in transactions table"
        }
    
    return {
        "can_answer": False,
        "confidence": "low",
        "reason": "Question doesn't match SQL data patterns"
    }


def can_rag_answer(question: str) -> dict:
    """Check if RAG documents can answer this question"""
    question_lower = question.lower()
    
    # Check for RAG-answerable patterns
    rag_patterns = {
        "products_operations": ["policy", "return", "refund", "conditions"],
        "strategic_plans": ["plan", "strategy", "initiative", "roadmap", "expansion"],
        "financial": ["q1", "q2", "q3", "q4", "quarter", "performance", "report"],
        "hr_compliance": ["compliance", "regulation", "guideline", "legal"]
    }
    
    for category, keywords in rag_patterns.items():
        if any(kw in question_lower for kw in keywords):
            return {
                "can_answer": True,
                "confidence": "high",
                "reason": f"Question asks about {category} information in documents",
                "likely_documents": RAG_INVENTORY["categories"].get(category, {}).get("files", [])
            }
    
    return {
        "can_answer": False,
        "confidence": "low",
        "reason": "Question doesn't match document topics"
    }


def can_web_answer(question: str) -> dict:
    """Check if web scraping can answer this question"""
    question_lower = question.lower()
    
    competitor_categories = {
        "newegg": "electronics",
        "goal zero": "electronics",
        "ikea": "home",
        "taylor stitch": "clothing",
        "chubbies": "clothing",
        "finisterre": "clothing",
        "swanson": "food",
        "nativepath": "food",
        "campmor": "sports",
    }
    competitor_keywords = ["competitor", "market", "pricing", "walmart", *competitor_categories]
    category_keywords = list(WEB_INVENTORY["categories"].keys())
    
    has_competitor = any(kw in question_lower for kw in competitor_keywords)
    has_category = any(cat in question_lower for cat in category_keywords)
    
    if has_competitor or (has_category and "price" in question_lower):
        suggested_category = next((cat for cat in category_keywords if cat in question_lower), None)
        if suggested_category is None:
            suggested_category = next(
                (category for competitor, category in competitor_categories.items() if competitor in question_lower),
                "electronics",
            )
        return {
            "can_answer": True,
            "confidence": "high",
            "reason": "Question asks for competitor/market pricing data",
            "suggested_category": suggested_category,
        }
    
    return {
        "can_answer": False,
        "confidence": "low",
        "reason": "Question doesn't ask for competitor data"
    }


def should_cross_validate(question: str) -> dict:
    """
    Determine if question should use cross-validation (SQL + RAG)
    
    Returns:
        {
            "should_validate": bool,
            "reason": str,
            "validation_topic": str
        }
    """
    question_lower = question.lower()
    
    # Check if question matches validatable topics
    for topic, sources in CROSS_VALIDATION_MAP["validatable"].items():
        topic_keywords = topic.lower().replace("_", " ").split()
        if all(kw in question_lower for kw in topic_keywords):
            return {
                "should_validate": True,
                "reason": f"Both SQL and RAG have data for {topic}",
                "validation_topic": topic,
                "sql_source": sources["sql"],
                "rag_source": sources["rag"]
            }
    
    return {
        "should_validate": False,
        "reason": "No overlapping data in SQL and RAG for this question"
    }
