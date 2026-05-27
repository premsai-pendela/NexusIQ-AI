"""
RAG Retrieval Quality Evaluation for NexusIQ-AI.

Measures context precision and context recall without requiring the RAGAS
library (which needs an external LLM judge). Implements the same metrics:

  Context Precision   — correct documents appear in top-K retrieved chunks
  Context Recall      — all expected source documents are hit across top-K
  MRR                 — Mean Reciprocal Rank of first correct source
  Hit@K               — binary: correct source in top-K

40 golden queries cover all five RAG-relevant document categories:
  Returns/Refunds Policy, Inventory Reorder SOP, Customer Escalation Policy,
  Q4/Q3 Revenue Memos, Electronics Deep-Dive, Regional Analysis,
  Payment Methods, Operations Digests, Incident Reports, Annual Review,
  CLV Study, Supply Chain Risk.

Usage:
    python -m evals.rag_eval
    python -m evals.rag_eval --top-k 5
    python -m evals.rag_eval --quick          (first 10 queries only)
    python -m evals.rag_eval --no-rerank      (disable cross-encoder)
    python -m evals.rag_eval --report report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ─── Golden query set ─────────────────────────────────────────────────────────
# Each entry: id, question, expected_sources (list of filename substrings),
# notes (optional — explains what makes this query interesting for RAG eval).

GOLDEN_QUERIES: List[Dict] = [
    # ── Returns & Refunds Policy ──────────────────────────────────────────────
    {
        "id": "return_policy_general",
        "question": "What is the return policy?",
        "expected_sources": ["Returns_Refunds_Policy", "01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },
    {
        "id": "return_window_electronics",
        "question": "How many days do I have to return an electronics product?",
        "expected_sources": ["01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },
    {
        "id": "return_window_clothing",
        "question": "What is the return window for clothing and apparel?",
        "expected_sources": ["01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },
    {
        "id": "return_status_breakdown",
        "question": "How many returns were rejected versus refunded in 2024?",
        "expected_sources": ["01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },
    {
        "id": "high_return_products",
        "question": "Which products have the highest return rates?",
        "expected_sources": ["01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },
    {
        "id": "return_exception_policy",
        "question": "Can a rejected return be appealed?",
        "expected_sources": ["01_Returns_Refunds_Policy"],
        "category": "Returns Policy",
    },

    # ── Inventory Reorder SOP ─────────────────────────────────────────────────
    {
        "id": "inventory_below_reorder",
        "question": "Which stores have inventory below the reorder point?",
        "expected_sources": ["02_Inventory_Reorder_SOP"],
        "category": "Inventory SOP",
    },
    {
        "id": "inventory_reorder_formula",
        "question": "How is the reorder point calculated for inventory?",
        "expected_sources": ["02_Inventory_Reorder_SOP"],
        "category": "Inventory SOP",
    },
    {
        "id": "inventory_low_stock_count",
        "question": "How many SKUs are currently below the reorder threshold?",
        "expected_sources": ["02_Inventory_Reorder_SOP"],
        "category": "Inventory SOP",
    },
    {
        "id": "inventory_electronics_lead_time",
        "question": "What is the lead time for Electronics inventory reorders?",
        "expected_sources": ["02_Inventory_Reorder_SOP"],
        "category": "Inventory SOP",
    },
    {
        "id": "vendor_performance_scorecard",
        "question": "Which vendors are on performance notice for delivery issues?",
        "expected_sources": ["02_Inventory_Reorder_SOP"],
        "category": "Inventory SOP",
    },

    # ── Customer Escalation Policy ────────────────────────────────────────────
    {
        "id": "escalation_tiers",
        "question": "What are the customer support escalation tiers and their authority limits?",
        "expected_sources": ["03_Customer_Escalation_Policy"],
        "category": "Escalation Policy",
    },
    {
        "id": "escalation_sla_urgent",
        "question": "What is the SLA for urgent support cases?",
        "expected_sources": ["03_Customer_Escalation_Policy"],
        "category": "Escalation Policy",
    },
    {
        "id": "escalation_volume_2024",
        "question": "How many support cases were escalated to Tier 2 in FY 2024?",
        "expected_sources": ["03_Customer_Escalation_Policy"],
        "category": "Escalation Policy",
    },
    {
        "id": "escalation_high_value_customers",
        "question": "How are high-value Platinum and Diamond customers handled in support?",
        "expected_sources": ["03_Customer_Escalation_Policy"],
        "category": "Escalation Policy",
    },

    # ── Q4 2024 Revenue Performance Memo ─────────────────────────────────────
    {
        "id": "q4_revenue_total",
        "question": "What was total Q4 2024 revenue?",
        "expected_sources": ["04_Q4_2024_Revenue_Performance_Memo", "13_2024_Annual_Business_Review"],
        "category": "Q4 Revenue",
    },
    {
        "id": "q4_electronics_revenue_memo",
        "question": "What was Q4 2024 Electronics revenue?",
        "expected_sources": ["04_Q4_2024_Revenue_Performance_Memo", "06_Electronics_Category_Deep_Dive"],
        "category": "Q4 Revenue",
    },
    {
        "id": "q4_revenue_vs_forecast",
        "question": "How did Q4 2024 revenue compare to forecast?",
        "expected_sources": ["04_Q4_2024_Revenue_Performance_Memo"],
        "category": "Q4 Revenue",
    },
    {
        "id": "q4_december_revenue",
        "question": "What was December 2024 revenue and why was it the highest month?",
        "expected_sources": ["04_Q4_2024_Revenue_Performance_Memo"],
        "category": "Q4 Revenue",
    },

    # ── Q3 2024 Revenue Performance Memo ─────────────────────────────────────
    {
        "id": "q3_revenue_total",
        "question": "What was Q3 2024 revenue?",
        "expected_sources": ["05_Q3_2024_Revenue_Performance_Memo"],
        "category": "Q3 Revenue",
    },
    {
        "id": "q3_back_to_school",
        "question": "How did back-to-school demand affect Q3 2024 Electronics performance?",
        "expected_sources": ["05_Q3_2024_Revenue_Performance_Memo", "06_Electronics_Category_Deep_Dive"],
        "category": "Q3 Revenue",
    },

    # ── Electronics Category Deep-Dive ────────────────────────────────────────
    {
        "id": "electronics_full_year_revenue",
        "question": "What was total Electronics category revenue for FY 2024?",
        "expected_sources": ["06_Electronics_Category_Deep_Dive", "13_2024_Annual_Business_Review"],
        "category": "Electronics",
    },
    {
        "id": "electronics_product_breakdown",
        "question": "How is Electronics revenue broken down by product (Laptop, Phone, Tablet)?",
        "expected_sources": ["06_Electronics_Category_Deep_Dive"],
        "category": "Electronics",
    },
    {
        "id": "electronics_seasonality",
        "question": "How does Electronics revenue vary by quarter seasonally?",
        "expected_sources": ["06_Electronics_Category_Deep_Dive"],
        "category": "Electronics",
    },

    # ── Regional Performance Analysis ─────────────────────────────────────────
    {
        "id": "west_vs_south_revenue",
        "question": "Why did the West region outperform the South region in revenue in 2024?",
        "expected_sources": ["07_Regional_Performance_Analysis"],
        "category": "Regional Analysis",
    },
    {
        "id": "central_region_opportunity",
        "question": "Why does the Central region have the lowest revenue per customer despite having the largest customer base?",
        "expected_sources": ["07_Regional_Performance_Analysis"],
        "category": "Regional Analysis",
    },
    {
        "id": "region_revenue_ranking",
        "question": "What is the revenue ranking of all five regions in 2024?",
        "expected_sources": ["07_Regional_Performance_Analysis", "13_2024_Annual_Business_Review"],
        "category": "Regional Analysis",
    },
    {
        "id": "west_electronics_affinity",
        "question": "What explains the West region's higher per-customer spending?",
        "expected_sources": ["07_Regional_Performance_Analysis", "06_Electronics_Category_Deep_Dive"],
        "category": "Regional Analysis",
    },

    # ── Payment Method Adoption Report ────────────────────────────────────────
    {
        "id": "digital_wallet_trends",
        "question": "What are the payment method trends and digital wallet adoption rates?",
        "expected_sources": ["08_Payment_Method_Adoption_Report"],
        "category": "Payment Methods",
    },
    {
        "id": "digital_wallet_q4_share",
        "question": "What percentage of Q4 2024 transactions used digital wallets?",
        "expected_sources": ["08_Payment_Method_Adoption_Report"],
        "category": "Payment Methods",
    },
    {
        "id": "fraud_rate_by_payment",
        "question": "How does fraud rate differ between credit cards and digital wallets?",
        "expected_sources": ["08_Payment_Method_Adoption_Report"],
        "category": "Payment Methods",
    },

    # ── Weekly Operations Digests ─────────────────────────────────────────────
    {
        "id": "black_friday_revenue",
        "question": "How much revenue did NexusIQ generate during Black Friday week 2024?",
        "expected_sources": ["09_Weekly_Operations_Digest_Week48"],
        "category": "Operations Digest",
    },
    {
        "id": "week48_electronics_share",
        "question": "What share of Black Friday week revenue came from Electronics?",
        "expected_sources": ["09_Weekly_Operations_Digest_Week48"],
        "category": "Operations Digest",
    },
    {
        "id": "week12_normal_operations",
        "question": "What does a typical mid-March operating week look like for NexusIQ?",
        "expected_sources": ["10_Weekly_Operations_Digest_Week12"],
        "category": "Operations Digest",
    },

    # ── Seasonal Demand Incident Report ──────────────────────────────────────
    {
        "id": "q4_demand_surge_cause",
        "question": "What caused the Electronics inventory shortage in Q4 2024?",
        "expected_sources": ["11_Seasonal_Demand_Incident_Report", "12_Inventory_Shortage_Root_Cause_Analysis"],
        "category": "Incident Report",
    },
    {
        "id": "lost_sales_estimate",
        "question": "How much revenue was lost due to inventory stockouts in Q4 2024?",
        "expected_sources": ["11_Seasonal_Demand_Incident_Report", "12_Inventory_Shortage_Root_Cause_Analysis"],
        "category": "Incident Report",
    },

    # ── Annual Business Review ────────────────────────────────────────────────
    {
        "id": "full_year_total_revenue",
        "question": "What was NexusIQ total revenue for FY 2024?",
        "expected_sources": ["13_2024_Annual_Business_Review"],
        "category": "Annual Review",
    },
    {
        "id": "annual_kpi_summary",
        "question": "What were the key performance indicators for NexusIQ in 2024?",
        "expected_sources": ["13_2024_Annual_Business_Review"],
        "category": "Annual Review",
    },

    # ── Customer Lifetime Value Study ─────────────────────────────────────────
    {
        "id": "average_customer_value",
        "question": "What is the average customer lifetime value at NexusIQ?",
        "expected_sources": ["14_Customer_Lifetime_Value_Study"],
        "category": "CLV Study",
    },
    {
        "id": "customer_tier_distribution",
        "question": "How are customers distributed across Diamond, Platinum, Gold, Silver, Bronze tiers?",
        "expected_sources": ["14_Customer_Lifetime_Value_Study"],
        "category": "CLV Study",
    },
    {
        "id": "churn_risk_customers",
        "question": "How many customers are at churn risk and which region has the highest concentration?",
        "expected_sources": ["14_Customer_Lifetime_Value_Study"],
        "category": "CLV Study",
    },

    # ── Supply Chain Risk Assessment ──────────────────────────────────────────
    {
        "id": "supply_chain_primary_risk",
        "question": "What is the primary supply chain risk for NexusIQ in 2025?",
        "expected_sources": ["15_Supply_Chain_Risk_Assessment"],
        "category": "Supply Chain",
    },
    {
        "id": "techsource_vendor_issue",
        "question": "What problems has the TechSource Global vendor caused and what is the remediation plan?",
        "expected_sources": ["15_Supply_Chain_Risk_Assessment", "02_Inventory_Reorder_SOP"],
        "category": "Supply Chain",
    },
]


# ─── Evaluation engine ────────────────────────────────────────────────────────

def _sources_hit(retrieved_chunks: List[Dict], expected_sources: List[str]) -> List[str]:
    """Return which expected sources appear in retrieved chunks (substring match on filename)."""
    hit = set()
    for chunk in retrieved_chunks:
        fname = chunk.get("filename", "")
        for src in expected_sources:
            if src in fname:
                hit.add(src)
    return list(hit)


def _first_hit_rank(retrieved_chunks: List[Dict], expected_sources: List[str]) -> int:
    """Return 1-based rank of first correct chunk (0 if not found)."""
    for i, chunk in enumerate(retrieved_chunks, 1):
        fname = chunk.get("filename", "")
        if any(src in fname for src in expected_sources):
            return i
    return 0


def run_eval(
    top_k: int = 5,
    rerank: bool = True,
    quick: bool = False,
    report_path: str | None = None,
) -> Dict:
    from agents.rag_agent import RAGAgent

    print(f"\n{'='*60}")
    print(f"NexusIQ RAG Evaluation | top_k={top_k} rerank={rerank}")
    print(f"{'='*60}\n")

    agent = RAGAgent()
    queries = GOLDEN_QUERIES[:10] if quick else GOLDEN_QUERIES

    results = []
    category_stats: Dict[str, Dict] = {}

    for q in queries:
        t0 = time.time()
        chunks = agent.hybrid_search(
            q["question"],
            n_results=top_k,
            rerank=rerank,
            rerank_top_k=20 if rerank else top_k,
        )
        latency = time.time() - t0

        hit_sources = _sources_hit(chunks, q["expected_sources"])
        first_rank = _first_hit_rank(chunks, q["expected_sources"])
        n_expected = len(q["expected_sources"])
        precision = len(hit_sources) / min(top_k, len(chunks)) if chunks else 0.0
        recall = len(hit_sources) / n_expected if n_expected else 0.0
        hit_at_k = 1 if first_rank > 0 else 0
        mrr = 1.0 / first_rank if first_rank > 0 else 0.0

        r = {
            "id": q["id"],
            "question": q["question"],
            "category": q["category"],
            "expected_sources": q["expected_sources"],
            "hit_sources": hit_sources,
            "hit@k": hit_at_k,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "mrr": round(mrr, 3),
            "first_hit_rank": first_rank,
            "latency_s": round(latency, 2),
            "top_retrieved": [
                {"filename": c["filename"], "score": c.get("rerank_score", c.get("similarity"))}
                for c in chunks[:3]
            ],
        }
        results.append(r)

        cat = q["category"]
        if cat not in category_stats:
            category_stats[cat] = {"hit": 0, "total": 0, "precision": [], "recall": []}
        category_stats[cat]["total"] += 1
        category_stats[cat]["hit"] += hit_at_k
        category_stats[cat]["precision"].append(precision)
        category_stats[cat]["recall"].append(recall)

        status = "PASS" if hit_at_k else "MISS"
        print(f"[{status}] {q['id']}")
        print(f"       Q: {q['question'][:70]}")
        print(f"       Expected: {q['expected_sources']}")
        print(f"       Retrieved: {[c['filename'] for c in chunks[:3]]}")
        if first_rank > 0:
            print(f"       First hit: rank #{first_rank} | precision={precision:.2f} recall={recall:.2f}")
        else:
            print(f"       NO HIT in top-{top_k}")
        print()

    # ── Aggregate metrics ──────────────────────────────────────────────────────
    n = len(results)
    overall_hit_rate = sum(r["hit@k"] for r in results) / n
    overall_precision = sum(r["precision"] for r in results) / n
    overall_recall = sum(r["recall"] for r in results) / n
    overall_mrr = sum(r["mrr"] for r in results) / n
    avg_latency = sum(r["latency_s"] for r in results) / n

    print("=" * 60)
    print(f"OVERALL RESULTS (n={n} queries, top_k={top_k}, rerank={rerank})")
    print("=" * 60)
    print(f"  Hit@{top_k}:            {overall_hit_rate:.1%}  ({sum(r['hit@k'] for r in results)}/{n})")
    print(f"  Context Precision:  {overall_precision:.3f}")
    print(f"  Context Recall:     {overall_recall:.3f}")
    print(f"  MRR:                {overall_mrr:.3f}")
    print(f"  Avg Latency:        {avg_latency:.2f}s")
    print()

    print("BY CATEGORY:")
    for cat, stats in sorted(category_stats.items()):
        hr = stats["hit"] / stats["total"]
        avg_p = sum(stats["precision"]) / len(stats["precision"])
        avg_r = sum(stats["recall"]) / len(stats["recall"])
        print(f"  {cat:<28} hit={hr:.0%}  p={avg_p:.2f}  r={avg_r:.2f}  ({stats['hit']}/{stats['total']})")

    print()
    misses = [r for r in results if not r["hit@k"]]
    if misses:
        print(f"MISSES ({len(misses)}):")
        for m in misses:
            print(f"  - {m['id']}: expected {m['expected_sources']}")
            print(f"    got: {[c['filename'] for c in m['top_retrieved']]}")
    else:
        print("No misses — all queries hit expected sources in top-k.")

    summary = {
        "hit_rate": overall_hit_rate,
        "context_precision": overall_precision,
        "context_recall": overall_recall,
        "mrr": overall_mrr,
        "avg_latency_s": avg_latency,
        "top_k": top_k,
        "rerank": rerank,
        "n_queries": n,
        "misses": [r["id"] for r in misses],
        "results": results,
    }

    if report_path:
        import json
        Path(report_path).write_text(json.dumps(summary, indent=2))
        print(f"\nReport written: {report_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="NexusIQ RAG Retrieval Evaluation")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve per query")
    parser.add_argument("--quick", action="store_true", help="Run first 10 queries only")
    parser.add_argument("--no-rerank", action="store_true", help="Disable cross-encoder reranking")
    parser.add_argument("--report", type=str, default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    summary = run_eval(
        top_k=args.top_k,
        rerank=not args.no_rerank,
        quick=args.quick,
        report_path=args.report,
    )

    hit_rate = summary["hit_rate"]
    if hit_rate >= 0.80:
        print(f"\nRAG quality: GOOD ({hit_rate:.0%} hit rate)")
        sys.exit(0)
    elif hit_rate >= 0.60:
        print(f"\nRAG quality: ACCEPTABLE ({hit_rate:.0%} hit rate) — review misses")
        sys.exit(0)
    else:
        print(f"\nRAG quality: POOR ({hit_rate:.0%} hit rate) — investigate corpus and chunking")
        sys.exit(1)


if __name__ == "__main__":
    main()
