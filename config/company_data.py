"""
NexusIQ Corporation - Single Source of Truth
All numbers referenced across SQL database and PDF reports
"""

NEXUSIQ_METRICS = {
    "company_name": "NexusIQ Corporation",
    "fiscal_year": 2024,
    
    # ════════════════════════════════════════════════════════
    # Q4 2024 (Oct 1 - Dec 31, 2024)
    # ════════════════════════════════════════════════════════
    "Q4_2024": {
        "date_range": ("2024-10-01", "2024-12-31"),
        "total_revenue": 45_200_000,  # $45.2M
        "total_transactions": 25_000,
        "avg_transaction_value": 1808,  # $1,808
        
        "categories": {
            "Electronics": {
                "revenue": 15_400_000,  # $15.4M (34.1%)
                "percentage": 0.341,
                "yoy_growth": 0.27
            },
            "Home": {
                "revenue": 11_200_000,  # $11.2M (24.8%)
                "percentage": 0.248,
                "yoy_growth": 0.19
            },
            "Clothing": {
                "revenue": 9_800_000,   # $9.8M (21.7%)
                "percentage": 0.217,
                "yoy_growth": 0.15
            },
            "Food": {
                "revenue": 5_600_000,   # $5.6M (12.4%)
                "percentage": 0.124,
                "yoy_growth": 0.08
            },
            "Sports": {
                "revenue": 3_200_000,   # $3.2M (7.1%)
                "percentage": 0.071,
                "yoy_growth": 0.22
            }
        },
        
        "regions": {
            "West": {
                "revenue": 12_800_000,  # $12.8M (28.3%)
                "percentage": 0.283
            },
            "East": {
                "revenue": 10_500_000,  # $10.5M (23.2%)
                "percentage": 0.232
            },
            "Central": {
                "revenue": 9_200_000,   # $9.2M (20.4%)
                "percentage": 0.204
            },
            "South": {
                "revenue": 7_800_000,   # $7.8M (17.3%)
                "percentage": 0.173
            },
            "North": {
                "revenue": 4_900_000,   # $4.9M (10.8%)
                "percentage": 0.108
            }
        },
        
        "payment_methods": {
            "Digital Wallet": 0.31,
            "Credit Card": 0.28,
            "Debit Card": 0.26,
            "Cash": 0.15
        }
    },
    
    # ════════════════════════════════════════════════════════
    # Q3 2024 (Jul 1 - Sep 30, 2024)
    # ════════════════════════════════════════════════════════
    "Q3_2024": {
        "date_range": ("2024-07-01", "2024-09-30"),
        "total_revenue": 38_700_000,  # $38.7M
        "total_transactions": 23_500,
        "avg_transaction_value": 1647,  # $1,647
        
        "categories": {
            "Electronics": {
                "revenue": 12_000_000,  # $12.0M (31.0%)
                "percentage": 0.310
            },
            "Clothing": {
                "revenue": 9_300_000,   # $9.3M (24.0%)
                "percentage": 0.240
            },
            "Home": {
                "revenue": 9_100_000,   # $9.1M (23.5%)
                "percentage": 0.235
            },
            "Food": {
                "revenue": 5_200_000,   # $5.2M (13.4%)
                "percentage": 0.134
            },
            "Sports": {
                "revenue": 3_100_000,   # $3.1M (8.0%)
                "percentage": 0.080
            }
        },
        
        "regions": {
            "West": {
                "revenue": 10_200_000,  # $10.2M (26.4%)
                "percentage": 0.264
            },
            "East": {
                "revenue": 9_100_000,   # $9.1M (23.5%)
                "percentage": 0.235
            },
            "Central": {
                "revenue": 8_500_000,   # $8.5M (22.0%)
                "percentage": 0.220
            },
            "South": {
                "revenue": 7_200_000,   # $7.2M (18.6%)
                "percentage": 0.186
            },
            "North": {
                "revenue": 3_700_000,   # $3.7M (9.6%)
                "percentage": 0.096
            }
        },
        
        "payment_methods": {
            "Debit Card": 0.30,
            "Credit Card": 0.29,
            "Digital Wallet": 0.24,
            "Cash": 0.17
        }
    },
    
    # ════════════════════════════════════════════════════════
    # Q2 2024 (Apr 1 - Jun 30, 2024) - For rest of year data
    # ════════════════════════════════════════════════════════
    "Q2_2024": {
        "date_range": ("2024-04-01", "2024-06-30"),
        "total_revenue": 35_000_000,  # ~$35M
        "total_transactions": 22_000,
        
        "categories": {
            "Electronics": 0.28,
            "Home": 0.25,
            "Clothing": 0.22,
            "Food": 0.15,
            "Sports": 0.10
        },
        
        "regions": {
            "West": 0.27,
            "East": 0.24,
            "Central": 0.21,
            "South": 0.18,
            "North": 0.10
        },
        
        "payment_methods": {
            "Credit Card": 0.32,
            "Debit Card": 0.30,
            "Digital Wallet": 0.20,
            "Cash": 0.18
        }
    },
    
    # ════════════════════════════════════════════════════════
    # Q1 2024 (Jan 1 - Mar 31, 2024)
    # ════════════════════════════════════════════════════════
    "Q1_2024": {
        "date_range": ("2024-01-01", "2024-03-31"),
        "total_revenue": 32_000_000,  # ~$32M
        "total_transactions": 20_000,
        
        "categories": {
            "Electronics": 0.26,
            "Clothing": 0.24,
            "Home": 0.23,
            "Food": 0.17,
            "Sports": 0.10
        },
        
        "regions": {
            "East": 0.26,
            "West": 0.25,
            "Central": 0.21,
            "South": 0.18,
            "North": 0.10
        },
        
        "payment_methods": {
            "Credit Card": 0.35,
            "Debit Card": 0.32,
            "Cash": 0.20,
            "Digital Wallet": 0.13
        }
    },
    
    # ════════════════════════════════════════════════════════
    # Reference Data (Product names, stores, etc.)
    # ════════════════════════════════════════════════════════
    "products": {
        "Electronics": [
            "Laptop Pro 15\"", "Wireless Headphones", "4K Monitor 27\"",
            "Smartphone X12", "Tablet Air 10\"", "Gaming Console",
            "Smart Watch Series 5", "Bluetooth Speaker", "Webcam HD",
            "USB-C Hub", "Wireless Mouse", "Mechanical Keyboard"
        ],
        "Home": [
            "Coffee Maker Deluxe", "Vacuum Robot", "Air Purifier",
            "Smart Thermostat", "LED Desk Lamp", "Blender Pro",
            "Toaster Oven", "Electric Kettle", "Rice Cooker",
            "Food Processor", "Stand Mixer"
        ],
        "Clothing": [
            "Designer Jeans", "Cotton T-Shirt", "Wool Sweater",
            "Running Shoes", "Leather Jacket", "Casual Sneakers",
            "Winter Coat", "Summer Dress", "Formal Shirt",
            "Athletic Shorts", "Yoga Pants"
        ],
        "Food": [
            "Organic Snack Box", "Premium Coffee Beans", "Artisan Chocolate",
            "Gourmet Pasta Set", "Olive Oil Extra Virgin", "Tea Collection",
            "Protein Bars Box", "Honey Organic", "Spice Set",
            "Granola Mix", "Dried Fruit Pack"
        ],
        "Sports": [
            "Yoga Mat Premium", "Dumbbell Set 20lb", "Resistance Bands",
            "Jump Rope Pro", "Foam Roller", "Gym Bag",
            "Water Bottle 32oz", "Fitness Tracker", "Exercise Ball",
            "Kettlebell 15lb"
        ]
    }
}

# Calculate annual totals
NEXUSIQ_METRICS["ANNUAL_2024"] = {
    "total_revenue": sum([
        NEXUSIQ_METRICS["Q1_2024"]["total_revenue"],
        NEXUSIQ_METRICS["Q2_2024"]["total_revenue"],
        NEXUSIQ_METRICS["Q3_2024"]["total_revenue"],
        NEXUSIQ_METRICS["Q4_2024"]["total_revenue"]
    ]),  # $150.9M
    "total_transactions": sum([
        NEXUSIQ_METRICS["Q1_2024"]["total_transactions"],
        NEXUSIQ_METRICS["Q2_2024"]["total_transactions"],
        NEXUSIQ_METRICS["Q3_2024"]["total_transactions"],
        NEXUSIQ_METRICS["Q4_2024"]["total_transactions"]
    ])  # 90,500 (we'll generate 100K for full year including some outside Q boundaries)
}
