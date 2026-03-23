"""
NexusIQ AI — Input Validators and Helpers
Context-aware validation for edge cases
"""

from difflib import get_close_matches
from typing import List, Optional, Tuple
from datetime import datetime
import re

# ═══════════════════════════════════════════════════════════
#  VALID VALUES
# ═══════════════════════════════════════════════════════════

VALID_REGIONS = ['East', 'West', 'North', 'South', 'Central']
VALID_CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports']
VALID_PAYMENT_METHODS = ['Credit Card', 'Debit Card', 'Cash', 'Digital Wallet']

DATA_START_DATE = datetime(2024, 3, 15)
DATA_END_DATE = datetime(2025, 3, 15)

# ═══════════════════════════════════════════════════════════
#  CONTEXT DETECTION
# ═══════════════════════════════════════════════════════════

def has_region_context(question: str) -> bool:
    """Check if question is asking about regions/locations"""
    region_keywords = [
        'region', 'area', 'location', 'zone', 'territory',
        'east', 'west', 'north', 'south', 'central',
        'store', 'branch', 'office'
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in region_keywords)


def has_category_context(question: str) -> bool:
    """Check if question is asking about product categories"""
    category_keywords = [
        'category', 'categories', 'type', 'types',
        'electronics', 'clothing', 'food', 'home', 'sports',
        'department', 'section'
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in category_keywords)


# ═══════════════════════════════════════════════════════════
#  FUZZY MATCHING (Context-Aware)
# ═══════════════════════════════════════════════════════════

def find_closest_match(
    value: str, 
    valid_options: List[str], 
    threshold: float = 0.7  # Increased threshold for less false positives
) -> Optional[str]:
    """Find closest match with higher threshold"""
    
    # Exact match check first
    for option in valid_options:
        if value.lower() == option.lower():
            return None  # Already correct, no suggestion needed
    
    matches = get_close_matches(value, valid_options, n=1, cutoff=threshold)
    return matches[0] if matches else None


def check_region_typo(question: str) -> Optional[dict]:
    """Check for region typos ONLY if question has region context"""
    
    # Skip if no region context
    if not has_region_context(question):
        return None
    
    question_lower = question.lower()
    words = re.findall(r'\b[a-zA-Z]+\b', question)
    
    for word in words:
        word_cap = word.capitalize()
        
        # Skip common words that aren't regions
        skip_words = ['in', 'the', 'for', 'and', 'or', 'by', 'to', 'of', 
                      'region', 'area', 'sales', 'revenue', 'total', 'show',
                      'what', 'how', 'best', 'top', 'product', 'products']
        if word.lower() in skip_words:
            continue
        
        # Only check if word is NOT already a valid region
        if word_cap not in VALID_REGIONS:
            match = find_closest_match(word_cap, VALID_REGIONS, threshold=0.75)
            if match:
                return {
                    "typo": word,
                    "suggestion": match,
                    "available": VALID_REGIONS
                }
    
    return None


def check_category_typo(question: str) -> Optional[dict]:
    """Check for category typos ONLY if question has category context"""
    
    # Skip if no category context
    if not has_category_context(question):
        return None
    
    words = re.findall(r'\b[a-zA-Z]+\b', question)
    
    for word in words:
        word_cap = word.capitalize()
        
        # Skip common words
        skip_words = ['in', 'the', 'for', 'and', 'or', 'by', 'to', 'of',
                      'category', 'type', 'sales', 'revenue', 'total', 'show',
                      'what', 'how', 'best', 'top', 'product', 'products']
        if word.lower() in skip_words:
            continue
        
        if word_cap not in VALID_CATEGORIES:
            match = find_closest_match(word_cap, VALID_CATEGORIES, threshold=0.75)
            if match:
                return {
                    "typo": word,
                    "suggestion": match,
                    "available": VALID_CATEGORIES
                }
    
    return None


# ═══════════════════════════════════════════════════════════
#  DATE VALIDATION
# ═══════════════════════════════════════════════════════════

def check_date_range(question: str) -> Optional[dict]:
    """Check if question mentions dates outside available range"""
    
    year_pattern = r'\b(19\d{2}|20[0-1]\d|202[0-3])\b'  # Years before 2024
    years = re.findall(year_pattern, question)
    
    if not years:
        return None
    
    mentioned_year = int(years[0])
    
    if mentioned_year < DATA_START_DATE.year:
        return {
            "issue": f"Data not available for {mentioned_year}",
            "mentioned_year": mentioned_year,
            "data_range": f"{DATA_START_DATE.strftime('%b %Y')} to {DATA_END_DATE.strftime('%b %Y')}",
            "suggestion": f"Try '{DATA_START_DATE.year}' or 'last month' instead"
        }
    
    return None


# ═══════════════════════════════════════════════════════════
#  AMBIGUITY DETECTION
# ═══════════════════════════════════════════════════════════

def detect_ambiguity(question: str) -> Optional[dict]:
    """Detect ambiguous questions needing clarification"""
    
    question_lower = question.lower()
    
    # "Best/Top product" without metric
    if ('best' in question_lower or 'top' in question_lower) and 'product' in question_lower:
        # Check if metric is already specified
        metric_words = ['revenue', 'sales', 'quantity', 'volume', 'units', 
                       'amount', 'profit', 'transactions', 'sold']
        if not any(word in question_lower for word in metric_words):
            return {
                "ambiguous_term": "best/top",
                "options": [
                    "By revenue (total sales amount)",
                    "By quantity (units sold)",
                    "By transactions (number of sales)"
                ],
                "question": "What metric should we use to rank products?"
            }
    
    # "Performance" without clarity
    if 'performance' in question_lower or 'performing' in question_lower:
        metric_words = ['revenue', 'sales', 'quantity', 'growth', 'profit']
        if not any(word in question_lower for word in metric_words):
            return {
                "ambiguous_term": "performance",
                "options": [
                    "By revenue",
                    "By growth rate",
                    "By transaction volume"
                ],
                "question": "How should we measure performance?"
            }
    
    return None


# ═══════════════════════════════════════════════════════════
#  MAIN VALIDATION
# ═══════════════════════════════════════════════════════════

def validate_question(question: str) -> dict:
    """Run context-aware validations"""
    
    issues = []
    suggestions = []
    
    # Check ambiguity FIRST (most common issue)
    ambiguity = detect_ambiguity(question)
    if ambiguity:
        issues.append({
            "type": "ambiguous",
            "details": ambiguity
        })
        suggestions.append("Please specify the metric")
    
    # Check date range
    date_issue = check_date_range(question)
    if date_issue:
        issues.append({
            "type": "date_range",
            "details": date_issue
        })
        suggestions.append(date_issue["suggestion"])
    
    # Check typos ONLY if context exists
    region_issue = check_region_typo(question)
    if region_issue:
        issues.append({
            "type": "typo",
            "field": "region",
            "details": region_issue
        })
        suggestions.append(f"Did you mean '{region_issue['suggestion']}'?")
    
    category_issue = check_category_typo(question)
    if category_issue:
        issues.append({
            "type": "typo",
            "field": "category",
            "details": category_issue
        })
        suggestions.append(f"Did you mean '{category_issue['suggestion']}'?")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions
    }


# ═══════════════════════════════════════════════════════════
#  TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_questions = [
        "Best product",                    # Ambiguous ONLY (no region check)
        "Show sales in Wset region",       # Typo (has region context)
        "Revenue in 2020",                 # Date range
        "Top products by revenue",         # Valid (metric specified)
        "Sales in West region",            # Valid
        "Best performing region",          # Ambiguous (performance)
    ]
    
    print("\n" + "="*60)
    print("TESTING CONTEXT-AWARE VALIDATORS")
    print("="*60 + "\n")
    
    for q in test_questions:
        print(f"Question: {q}")
        result = validate_question(q)
        print(f"Valid: {result['valid']}")
        if result['issues']:
            for issue in result['issues']:
                print(f"  → {issue['type']}: {issue.get('details', {})}")
        else:
            print("  → No issues")
        print()