"""
NexusIQ AI — Input Validators and Helpers
Context-aware validation with auto-correction
"""

from difflib import get_close_matches
from typing import List, Optional, Tuple, Dict
from datetime import datetime
import re

# ═══════════════════════════════════════════════════════════
#  VALID VALUES
# ═══════════════════════════════════════════════════════════

VALID_REGIONS = ['East', 'West', 'North', 'South', 'Central']
VALID_CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports']
VALID_PAYMENT_METHODS = ['Credit Card', 'Debit Card', 'Cash', 'Digital Wallet']

DATA_START_DATE = datetime(2024, 1, 1)
DATA_END_DATE = datetime(2024, 12, 31)


# ═══════════════════════════════════════════════════════════
#  FUZZY MATCHING (Must be defined FIRST)
# ═══════════════════════════════════════════════════════════

def find_closest_match(
    value: str,
    valid_options: List[str],
    threshold: float = 0.7
) -> Optional[str]:
    """Find closest match using fuzzy matching"""
    
    # Exact match check first
    for option in valid_options:
        if value.lower() == option.lower():
            return None  # Already correct, no suggestion needed

    matches = get_close_matches(value, valid_options, n=1, cutoff=threshold)
    return matches[0] if matches else None


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
#  TYPO CHECKERS
# ═══════════════════════════════════════════════════════════

def check_region_typo(question: str) -> Optional[dict]:
    """Check for region typos ONLY if question has region context"""

    # Skip if no region context
    if not has_region_context(question):
        return None

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
            match = find_closest_match(word_cap, VALID_REGIONS, threshold=0.6)
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
        
        # Skip common words — include any word that fuzzy-matches a category
        # by accident (e.g. "reports" → "Sports", "sorting" → "Sports")
        skip_words = [
            'in', 'the', 'for', 'and', 'or', 'by', 'to', 'of',
            'category', 'type', 'sales', 'revenue', 'total', 'show',
            'what', 'how', 'best', 'top', 'product', 'products',
            'reports', 'report', 'against', 'validate', 'validation',
            'sorting', 'sorted', 'importing', 'exports', 'supports',
            'efforts', 'results', 'metrics', 'targets', 'formats',
        ]
        if word.lower() in skip_words:
            continue

        if word_cap not in VALID_CATEGORIES:
            # Raised from 0.6 → 0.75 to avoid false positives like "reports" → "Sports"
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

    # Match years that are clearly outside 2024
    year_pattern = r'\b(19\d{2}|20[0-1]\d|202[0-3]|202[5-9])\b'
    years = re.findall(year_pattern, question)

    if not years:
        return None

    mentioned_year = int(years[0])

    if mentioned_year < DATA_START_DATE.year or mentioned_year > DATA_END_DATE.year:
        return {
            "issue": f"Data not available for {mentioned_year}",
            "mentioned_year": mentioned_year,
            "data_range": f"{DATA_START_DATE.strftime('%b %Y')} to {DATA_END_DATE.strftime('%b %Y')}",
            "suggestion": f"Try '2024' or a quarter like 'Q4 2024' instead"
        }

    return None


# ═══════════════════════════════════════════════════════════
#  AMBIGUITY DETECTION
# ═══════════════════════════════════════════════════════════

def detect_ambiguity(question: str) -> Optional[dict]:
    """Detect ambiguous questions needing clarification"""

    question_lower = question.lower()

    # "Best/Top product" without metric - NOW RETURNS NONE (auto-defaulted)
    # We handle this in auto_correct_question() instead
    
    # "Performance" without clarity (still flagged)
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
#  ✅ AUTO-CORRECTION ENGINE
# ═══════════════════════════════════════════════════════════

def auto_correct_question(question: str) -> dict:
    """
    Attempt to auto-correct common issues
    
    Returns:
        {
            "corrected": bool,
            "original": str,
            "corrected_question": str,
            "corrections": [{"type": str, "from": str, "to": str}]
        }
    """
    
    corrections = []
    corrected_q = question
    
    # ─────────────────────────────────────────────────
    # 1. Fix region typos (wset → West)
    # ─────────────────────────────────────────────────
    
    region_typo = check_region_typo(question)
    if region_typo:
        corrected_q = re.sub(
            rf'\b{re.escape(region_typo["typo"])}\b',
            region_typo["suggestion"],
            corrected_q,
            flags=re.IGNORECASE
        )
        corrections.append({
            "type": "region_typo",
            "from": region_typo["typo"],
            "to": region_typo["suggestion"]
        })
    
    # ─────────────────────────────────────────────────
    # 2. Fix category typos (Electrnics → Electronics)
    # ─────────────────────────────────────────────────
    
    category_typo = check_category_typo(question)
    if category_typo:
        corrected_q = re.sub(
            rf'\b{re.escape(category_typo["typo"])}\b',
            category_typo["suggestion"],
            corrected_q,
            flags=re.IGNORECASE
        )
        corrections.append({
            "type": "category_typo",
            "from": category_typo["typo"],
            "to": category_typo["suggestion"]
        })
    
    # ─────────────────────────────────────────────────
    # 3. Resolve ambiguous "top/best" by defaulting to revenue
    # ─────────────────────────────────────────────────

    if re.search(r'\b(top|best)\s+(product|item|selling)', corrected_q, re.IGNORECASE):
        metric_words = ['revenue', 'sales', 'quantity', 'volume', 'units', 'amount', 'sold']
        if not any(metric in corrected_q.lower() for metric in metric_words):
            corrected_q = re.sub(
                r'\b(top|best)\s+(product|item|selling)(\s|$|\.|\?)',
                r'\1 \2 by revenue\3',
                corrected_q,
                flags=re.IGNORECASE
            )
            corrections.append({
                "type": "ambiguity_resolved",
                "from": "top/best product",
                "to": "top/best product by revenue",
                "note": "Defaulted to revenue metric"
            })

    # ─────────────────────────────────────────────────
    # 4. Resolve ambiguous "performance" in store/region/category context
    #    → default to revenue as the performance metric
    # ─────────────────────────────────────────────────

    if re.search(r'\bperformance\b', corrected_q, re.IGNORECASE):
        metric_words = ['revenue', 'sales', 'quantity', 'volume', 'units', 'amount', 'sold', 'growth']
        context_words = ['store', 'region', 'category', 'product', 'area', 'store_id', 'q1', 'q2', 'q3', 'q4', 'quarter']
        has_context = any(w in corrected_q.lower() for w in context_words)
        has_metric = any(w in corrected_q.lower() for w in metric_words)
        if has_context and not has_metric:
            corrected_q = re.sub(
                r'\bperformance\b',
                'revenue performance',
                corrected_q,
                flags=re.IGNORECASE
            )
            corrections.append({
                "type": "ambiguity_resolved",
                "from": "performance",
                "to": "revenue performance",
                "note": "Defaulted to revenue as performance metric"
            })
    
    return {
        "corrected": len(corrections) > 0,
        "original": question,
        "corrected_question": corrected_q,
        "corrections": corrections
    }


# ═══════════════════════════════════════════════════════════
#  MAIN VALIDATION (ENHANCED)
# ═══════════════════════════════════════════════════════════

def validate_question(question: str, auto_fix: bool = True) -> dict:
    """
    ✅ ENHANCED: Run context-aware validations with auto-correction
    
    Args:
        question: User question
        auto_fix: Attempt to auto-correct issues (default: True)
    
    Returns:
        {
            "valid": bool,
            "issues": list,
            "suggestions": list,
            "auto_corrected": bool,
            "corrected_question": str (if auto-corrected)
        }
    """
    
    # ─────────────────────────────────────────────────
    # Step 1: Try auto-correction first
    # ─────────────────────────────────────────────────
    
    if auto_fix:
        correction_result = auto_correct_question(question)
        if correction_result["corrected"]:
            # Return the corrected question as valid
            return {
                "valid": True,
                "issues": [],
                "suggestions": [],
                "auto_corrected": True,
                "corrected_question": correction_result["corrected_question"],
                "corrections": correction_result["corrections"]
            }
    
    # ─────────────────────────────────────────────────
    # Step 2: If no auto-correction, run normal validation
    # ─────────────────────────────────────────────────
    
    issues = []
    suggestions = []
    
    # Check date range
    date_issue = check_date_range(question)
    if date_issue:
        issues.append({
            "type": "date_range",
            "details": date_issue
        })
        suggestions.append(date_issue["suggestion"])
    
    # Check ambiguity (only for non-auto-fixed cases)
    ambiguity = detect_ambiguity(question)
    if ambiguity:
        issues.append({
            "type": "ambiguous",
            "details": ambiguity
        })
        suggestions.append("Please specify the metric")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "auto_corrected": False
    }


# ═══════════════════════════════════════════════════════════
#  TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_questions = [
        "Show me the top product",           # Should auto-correct to "by revenue"
        "wset region revenue",               # Should auto-correct to "West"
        "Electrnics sales",                  # Should auto-correct to "Electronics"
        "Revenue in 2020",                   # Should fail (date out of range)
        "What was Q4 2024 revenue?",         # Should pass
        "Best performing region",            # Should flag ambiguity (performance)
        "Top 5 products by quantity",        # Should pass (metric specified)
    ]
    
    print("\n" + "="*60)
    print("VALIDATORS TEST (WITH AUTO-CORRECTION)")
    print("="*60 + "\n")
    
    for q in test_questions:
        print(f"Q: {q}")
        result = validate_question(q, auto_fix=True)
        print(f"   Valid: {result['valid']}")
        
        if result.get('auto_corrected'):
            print(f"   ✨ Auto-corrected: {result['corrected_question']}")
            for c in result.get('corrections', []):
                print(f"      • {c['type']}: {c['from']} → {c['to']}")
        
        if result.get('issues'):
            for issue in result['issues']:
                print(f"   ❌ Issue: {issue['type']}")
        
        print()