"""
Generate 5 data-dense analytics PDFs for NexusIQ RAG stress-testing.

These are NOT executive summaries. Each PDF mirrors how a real company
actually stores operational data — row-level tables, monthly cadence,
per-store/per-product granularity, case logs with IDs.

Target: 80-200 chunks per PDF (vs 9 in the summary version).

Ground-truth DB values (live Supabase, pulled 2026-05-26):
  transactions: 100,000 | revenue: $175,595,178.16
  customers: 14,979 | avg_spend: $11,722.76 | max: $59,521.80
  customer_regions: Central(4599), East(3676), West(2351), South(2330), North(2023)
  returns: 6,000 | avg_refund: $1,618.61
  top_returns: Jeans(331), Bedding(325), Decor(322), Kitchen(315), Tablet(314)
  return_statuses: rejected(1242), refunded(1207), pending(1197), received(1181), approved(1173)
  support_priorities: low(520), high(502), urgent(497), medium(481)
  support_statuses: closed(530), in_progress(506), open(489), resolved(475)
  inventory_low_stock: 72
  revenue_by_category: Electronics($91,010,125.61), Home($40,877,008.66),
                        Sports($27,478,085.87), Clothing($11,731,765.10), Food($4,498,192.92)
  revenue_by_region: West($37,880,499.39), East($36,314,020.57), Central($35,679,253.01),
                     South($35,470,111.47), North($30,251,293.72)

Output: data/pdfs/08_analytics/ (5 PDFs, ~100-200 chunks each after ingestion)

Usage:
    python -m database.generate_analytics_pdfs generate
    python -m database.generate_analytics_pdfs ingest
    python -m database.generate_analytics_pdfs generate-and-ingest
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "pdfs" / "08_analytics"
CATEGORY = "08_analytics"

# ─── Ground-truth constants ────────────────────────────────────────────────────

REGIONS = ["Central", "East", "West", "South", "North"]
REGION_CUSTOMERS = {"Central": 4599, "East": 3676, "West": 2351, "South": 2330, "North": 2023}
REGION_REVENUE   = {
    "West": 37880499.39, "East": 36314020.57, "Central": 35679253.01,
    "South": 35470111.47, "North": 30251293.72,
}
PRODUCTS = [
    "Laptop", "Phone", "Tablet", "Headphones",
    "Jacket", "Jeans", "Shoes", "T-Shirt",
    "Bedding", "Decor", "Furniture", "Kitchen",
    "Accessories", "Apparel", "Equipment", "Footwear",
    "Drinks", "Frozen", "Produce", "Snacks",
]
CATEGORIES_MAP = {
    "Laptop": "Electronics", "Phone": "Electronics", "Tablet": "Electronics",
    "Headphones": "Electronics",
    "Jacket": "Clothing", "Jeans": "Clothing", "Shoes": "Clothing", "T-Shirt": "Clothing",
    "Bedding": "Home", "Decor": "Home", "Furniture": "Home", "Kitchen": "Home",
    "Accessories": "Sports", "Apparel": "Sports", "Equipment": "Sports", "Footwear": "Sports",
    "Drinks": "Food", "Frozen": "Food", "Produce": "Food", "Snacks": "Food",
}
CATEGORY_REVENUE = {
    "Electronics": 91010125.61, "Home": 40877008.66,
    "Sports": 27478085.87, "Clothing": 11731765.10, "Food": 4498192.92,
}
STORES = {r: [f"{r[0]}{str(i).zfill(3)}" for i in range(1, 21)] for r in REGIONS}
ALL_STORES = [s for r in REGIONS for s in STORES[r]]  # 100 stores

TOP_RETURN_COUNTS = {
    "Jeans": 331, "Bedding": 325, "Decor": 322, "Kitchen": 315, "Tablet": 314,
    "Phone": 309, "Laptop": 302, "Shoes": 298, "Jacket": 287, "Headphones": 281,
    "T-Shirt": 274, "Furniture": 267, "Equipment": 261, "Apparel": 258,
    "Accessories": 252, "Footwear": 244, "Frozen": 198, "Drinks": 187,
    "Produce": 175, "Snacks": 169,
}  # sums to ~5,312 of 6,000

RETURN_REASONS = ["Defective", "Size/Fit", "Not as Described", "Wrong Item",
                  "Changed Mind", "Quality Issue", "Damaged in Shipping", "Duplicate Order"]
RETURN_STATUSES = ["rejected", "refunded", "pending", "received", "approved"]
RETURN_STATUS_COUNTS = {"rejected": 1242, "refunded": 1207, "pending": 1197,
                         "received": 1181, "approved": 1173}
SUPPORT_PRIORITIES = ["low", "high", "urgent", "medium"]
SUPPORT_STATUSES   = ["closed", "in_progress", "open", "resolved"]
SUPPORT_SUBJECTS = [
    "Defective product received", "Order not delivered", "Return request",
    "Wrong item shipped", "Refund not processed", "Account access issue",
    "Billing discrepancy", "Product setup assistance", "Warranty claim",
    "Damaged packaging", "Missing accessories", "Subscription cancellation",
    "Price match request", "Delivery delay", "Exchange request",
]

_rng = random.Random(42)


def _fmt(v: float) -> str:
    return f"${v:,.2f}"


def _date_in_2024(offset_days: int) -> str:
    return (date(2024, 1, 1) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ─── ReportLab helpers ─────────────────────────────────────────────────────────

def _make_doc(path: Path, title: str):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.units import inch
    return SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title=title, author="NexusIQ Analytics",
    )


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    s = getSampleStyleSheet()
    extra = {
        "Subtitle": ParagraphStyle("Subtitle", parent=s["Normal"],
                                    fontSize=10, textColor=colors.HexColor("#555555"),
                                    spaceAfter=10),
        "SectionHead": ParagraphStyle("SectionHead", parent=s["Heading2"],
                                       fontSize=12, textColor=colors.HexColor("#1a3c6e"),
                                       spaceBefore=14, spaceAfter=5),
        "SubHead": ParagraphStyle("SubHead", parent=s["Heading3"],
                                   fontSize=10, textColor=colors.HexColor("#2c5f9e"),
                                   spaceBefore=8, spaceAfter=3),
        "Body": ParagraphStyle("Body", parent=s["Normal"],
                                fontSize=9, leading=13, spaceAfter=5),
        "Caption": ParagraphStyle("Caption", parent=s["Normal"],
                                   fontSize=7.5, textColor=colors.grey, spaceAfter=8),
        "Alert": ParagraphStyle("Alert", parent=s["Normal"],
                                 fontSize=9, textColor=colors.HexColor("#b71c1c"),
                                 leading=13, spaceAfter=5),
        "Mono": ParagraphStyle("Mono", parent=s["Normal"],
                                fontName="Courier", fontSize=8, leading=11, spaceAfter=3),
    }
    s.__dict__["byName"].update(extra)
    return s, extra


def _table(data, col_widths=None, small=False):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    fs = 7.5 if small else 8.5
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), fs),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING",    (0, 0), (-1, 0), 5),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), fs),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
    ]))
    return t


def _hr():
    from reportlab.platypus import HRFlowable
    from reportlab.lib import colors
    return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1a3c6e"),
                      spaceAfter=4, spaceBefore=4)


def _sp(h=0.08):
    from reportlab.platypus import Spacer
    from reportlab.lib.units import inch
    return Spacer(1, h * inch)


def _pgbreak():
    from reportlab.platypus import PageBreak
    return PageBreak()


# ─── PDF 1: Customer CRM Export ───────────────────────────────────────────────
# Real format: monthly acquisition tables, cohort retention, per-customer records,
# spend brackets, region×category cross-tab, churn flags.

def build_customer_crm_export(out_path: Path) -> None:
    from reportlab.platypus import Paragraph
    doc = _make_doc(out_path, "Customer CRM Export 2024")
    s, e = _styles()

    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    # Monthly acquisition per region (sums to 14,979)
    monthly_acq = {
        r: [_rng.randint(90, 150) for _ in range(12)]
        for r in REGIONS
    }
    # Scale to match exact totals
    for r in REGIONS:
        raw_total = sum(monthly_acq[r])
        scale = REGION_CUSTOMERS[r] / raw_total
        monthly_acq[r] = [int(v * scale) for v in monthly_acq[r]]
        # fix rounding diff on last month
        diff = REGION_CUSTOMERS[r] - sum(monthly_acq[r])
        monthly_acq[r][-1] += diff

    story = []
    story += [
        Paragraph("NexusIQ Corporation — Customer Relationship Management", s["Heading1"]),
        Paragraph("CRM Data Export: FY 2024 Customer Acquisition, Cohorts & Spend Analysis",
                  e["Subtitle"]),
        Paragraph("System: NexusIQ CRM v4.2 | Export date: 2025-01-03 | "
                  "Records: 14,979 customers | Classification: Internal", e["Caption"]),
        _hr(), _sp(),
    ]

    # ── Section 1: Monthly acquisition by region ──
    story += [
        Paragraph("1. Monthly Customer Acquisition by Region — FY 2024", e["SectionHead"]),
        Paragraph("New unique customers added each month, broken down by geographic region. "
                  "Cumulative total at year-end: 14,979 active customers.", e["Body"]),
    ]
    hdr = ["Month"] + REGIONS + ["Total"]
    rows = [hdr]
    running = {r: 0 for r in REGIONS}
    for mi, mn in enumerate(MONTH_NAMES):
        row_vals = [monthly_acq[r][mi] for r in REGIONS]
        running = {r: running[r] + monthly_acq[r][mi] for r in REGIONS}
        rows.append([mn] + [str(v) for v in row_vals] + [str(sum(row_vals))])
    rows.append(["YTD Total"] + [str(REGION_CUSTOMERS[r]) for r in REGIONS] + ["14,979"])
    story.append(_table(rows, col_widths=[50, 80, 60, 60, 60, 60, 55], small=True))
    story.append(e["Caption"].__class__ and
                 Paragraph("Source: customers.signup_date grouped by region and month.", e["Caption"]))
    story.append(_sp())

    # ── Section 2: Running cumulative acquisition ──
    story += [
        Paragraph("2. Cumulative Customer Base Growth — FY 2024", e["SectionHead"]),
        Paragraph("Cumulative unique customers at end of each month:", e["Body"]),
    ]
    cum_rows = [["Month"] + REGIONS + ["Total Cumulative"]]
    cum = {r: 0 for r in REGIONS}
    for mi, mn in enumerate(MONTH_NAMES):
        cum = {r: cum[r] + monthly_acq[r][mi] for r in REGIONS}
        cum_rows.append([mn] + [str(cum[r]) for r in REGIONS] + [str(sum(cum.values()))])
    story.append(_table(cum_rows, col_widths=[50, 80, 60, 60, 60, 60, 80], small=True))
    story.append(_sp())

    # ── Section 3: Customer spend brackets ──
    story += [
        Paragraph("3. Customer Spend Distribution — FY 2024", e["SectionHead"]),
        Paragraph("Distribution of 14,979 customers by total FY 2024 spend. Average: $11,722.76. "
                  "Maximum single customer: $59,521.80. Minimum: $127.40.", e["Body"]),
    ]
    brackets = [
        ("$0 - $500",          623,  "$189,280"),
        ("$500 - $1,000",      841,  "$631,012"),
        ("$1,000 - $2,500",   1847, "$3,282,450"),
        ("$2,500 - $5,000",   2932, "$10,971,840"),
        ("$5,000 - $10,000",  4112, "$30,419,840"),
        ("$10,000 - $15,000", 2318, "$28,975,000"),
        ("$15,000 - $20,000", 1022, "$17,578,200"),
        ("$20,000 - $30,000",  892, "$21,634,800"),
        ("$30,000 - $45,000",  274, "$10,378,600"),
        ("$45,000+",           118, "$7,126,758"),
    ]
    br_rows = [["Spend Range", "Customers", "Cum. %", "Segment Revenue", "% of Total Rev"]]
    cum_pct = 0
    total_rev = 175595178.16
    for bracket, cnt, rev_str in brackets:
        cum_pct += cnt
        rev_num = float(rev_str.replace("$","").replace(",",""))
        br_rows.append([
            bracket, f"{cnt:,}",
            f"{cum_pct/14979*100:.1f}%",
            rev_str,
            f"{rev_num/total_rev*100:.2f}%",
        ])
    story.append(_table(br_rows, col_widths=[110, 80, 70, 110, 90]))
    story.append(_sp())

    # ── Section 4: Region × Category spend cross-tab ──
    story += [
        Paragraph("4. Revenue by Region × Product Category — FY 2024", e["SectionHead"]),
        Paragraph("Cross-tabulation of sales_transactions revenue (100,000 rows, $175,595,178.16 total) "
                  "by customer region and product category:", e["Body"]),
    ]
    cat_region_pct = {
        "Electronics": {"Central": 0.19, "East": 0.22, "West": 0.26, "South": 0.18, "North": 0.15},
        "Home":        {"Central": 0.24, "East": 0.20, "West": 0.21, "South": 0.19, "North": 0.16},
        "Sports":      {"Central": 0.20, "East": 0.22, "West": 0.20, "South": 0.21, "North": 0.17},
        "Clothing":    {"Central": 0.22, "East": 0.21, "West": 0.19, "South": 0.21, "North": 0.17},
        "Food":        {"Central": 0.25, "East": 0.20, "West": 0.18, "South": 0.20, "North": 0.17},
    }
    cats = ["Electronics", "Home", "Sports", "Clothing", "Food"]
    cr_rows = [["Category"] + REGIONS + ["Total"]]
    for cat in cats:
        row = [cat]
        cat_total = CATEGORY_REVENUE[cat]
        for r in REGIONS:
            row.append(_fmt(cat_total * cat_region_pct[cat][r]))
        row.append(_fmt(cat_total))
        cr_rows.append(row)
    total_row = ["Total"]
    for r in REGIONS:
        total_row.append(_fmt(REGION_REVENUE[r]))
    total_row.append("$175,595,178.16")
    cr_rows.append(total_row)
    story.append(_table(cr_rows, col_widths=[90, 80, 80, 75, 75, 70, 85]))
    story.append(_sp())

    # ── Section 5: Cohort retention analysis ──
    story += [
        Paragraph("5. Customer Cohort Retention Analysis — FY 2024", e["SectionHead"]),
        Paragraph("Quarterly cohort analysis tracking customer re-purchase rates after initial acquisition. "
                  "Cohort size = customers acquired in that quarter.", e["Body"]),
    ]
    cohorts = [
        ("Q1 2024 Cohort", 3780, [100.0, 74.2, 61.8, 55.3]),
        ("Q2 2024 Cohort", 3841, [100.0, 72.9, 60.1, 53.7]),
        ("Q3 2024 Cohort", 3822, [100.0, 71.4, 59.4, None]),
        ("Q4 2024 Cohort", 3536, [100.0, 68.8, None, None]),
    ]
    coh_rows = [["Cohort", "Size", "M0 (Acq)", "M+1 (Q ret)", "M+2 (H ret)", "M+3 (Ann ret)"]]
    for cname, csize, rets in cohorts:
        row = [cname, f"{csize:,}"]
        for r in rets:
            row.append(f"{r:.1f}%" if r is not None else "—")
        coh_rows.append(row)
    story.append(_table(coh_rows, col_widths=[110, 70, 80, 85, 85, 95]))
    story.append(_sp())

    # ── Section 6: Top 200 customers by lifetime spend ──
    story += [
        Paragraph("6. Top 200 Customers by FY 2024 Lifetime Spend", e["SectionHead"]),
        Paragraph("CRM export of highest-value customers. Fields: customer_id, region, "
                  "total_purchases (FY 2024), signup_date, support_cases_opened.", e["Body"]),
    ]
    top_cust_rows = [["Customer ID", "Region", "FY 2024 Spend", "Signup Date",
                       "Transactions", "Support Cases"]]
    spend_vals = sorted(
        [_rng.uniform(25000, 59521) for _ in range(200)],
        reverse=True
    )
    spend_vals[0] = 59521.80  # max from DB
    for i, spend in enumerate(spend_vals):
        cid = f"CUST{_rng.randint(1, 14979):05d}"
        region = _rng.choice(REGIONS)
        txn_count = _rng.randint(int(spend / 2500), int(spend / 800))
        signup = _date_in_2024(_rng.randint(0, 300))
        cases = _rng.randint(0, 4)
        top_cust_rows.append([
            cid, region, _fmt(spend), signup, str(txn_count), str(cases)
        ])
    story.append(_table(top_cust_rows,
                         col_widths=[85, 65, 95, 85, 80, 80], small=True))
    story.append(_sp())

    # ── Section 7: Churn risk flags ──
    story += [
        Paragraph("7. Churn Risk Assessment — Q4 2024", e["SectionHead"]),
        Paragraph("Customers flagged as high churn risk based on: last purchase > 90 days ago, "
                  "declining spend QoQ, or 2+ unresolved support cases. "
                  "Total at-risk customers: 1,847 (12.3% of base).", e["Body"]),
    ]
    churn_rows = [["Region", "At-Risk Count", "% of Region", "Primary Signal",
                   "Est. Revenue at Risk"]]
    churn_data = [
        ("Central", 612, "13.3%", "Declining spend", "$4,218,000"),
        ("East",    482, "13.1%", "Long dormancy",   "$3,812,000"),
        ("West",    284, "12.1%", "High return rate","$5,124,000"),
        ("South",   284, "12.2%", "Unresolved cases","$2,987,000"),
        ("North",   185, "9.1%",  "Declining spend", "$2,041,000"),
    ]
    for row in churn_data:
        churn_rows.append(list(row))
    churn_rows.append(["Total", "1,847", "12.3%", "—", "~$18,182,000"])
    story.append(_table(churn_rows, col_widths=[80, 100, 90, 130, 120]))
    story.append(_sp())

    # ── Section 8: Customer × support × return summary ──
    story += [
        Paragraph("8. Customer Service Interaction Summary — FY 2024", e["SectionHead"]),
        Paragraph("Cross-reference of customers table with support_cases (2,000 rows) and "
                  "returns (6,000 rows). Interaction rate: 13.4% of customers opened "
                  "at least one support case; 23.8% initiated at least one return.", e["Body"]),
    ]
    svc_rows = [["Metric", "Count", "% of 14,979 Customers"]]
    svc_data = [
        ("Customers with 0 interactions", "9,842", "65.7%"),
        ("Customers with 1 return only",  "2,340", "15.6%"),
        ("Customers with 1 support case only", "921", "6.1%"),
        ("Customers with both return + support", "1,085", "7.2%"),
        ("Customers with 3+ returns",     "482",  "3.2%"),
        ("Customers with 2+ support cases","309",  "2.1%"),
    ]
    for row in svc_data:
        svc_rows.append(list(row))
    story.append(_table(svc_rows, col_widths=[250, 100, 150]))
    story.append(_sp())

    story += [
        _hr(),
        Paragraph("Export generated by NexusIQ CRM v4.2 | Tables: customers (14,979), "
                  "sales_transactions (100,000), support_cases (2,000), returns (6,000). "
                  "FY 2024. All monetary values USD.", e["Caption"]),
    ]

    doc.build(story)
    print(f"  ✅ {out_path.name}")


# ─── PDF 2: Returns Processing Register ───────────────────────────────────────
# Real format: individual return records with IDs, monthly cadence, per-product
# drill-down tables, reason codes, regional rates.

def build_returns_register(out_path: Path) -> None:
    from reportlab.platypus import Paragraph
    doc = _make_doc(out_path, "Returns Processing Register 2024")
    s, e = _styles()
    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

    story = []
    story += [
        Paragraph("NexusIQ Corporation — Operations", s["Heading1"]),
        Paragraph("Returns Processing Register — FY 2024 (6,000 records)",
                  e["Subtitle"]),
        Paragraph("System: NexusIQ OMS Returns Module v3.1 | Export: 2025-01-04 | "
                  "Total records: 6,000 | Avg refund: $1,618.61 | Classification: Internal",
                  e["Caption"]),
        _hr(), _sp(),
    ]

    # ── Section 1: Return volume by month × product ──
    story += [
        Paragraph("1. Monthly Return Volume by Product — FY 2024", e["SectionHead"]),
        Paragraph("Number of return cases initiated each month, by product SKU. "
                  "Total FY 2024: 6,000 returns across 20 product lines.", e["Body"]),
    ]
    monthly_returns = {}
    for p, annual in TOP_RETURN_COUNTS.items():
        base = [_rng.randint(int(annual*0.06), int(annual*0.11)) for _ in range(12)]
        total = sum(base)
        monthly_returns[p] = [int(v * annual / total) for v in base]
        diff = annual - sum(monthly_returns[p])
        monthly_returns[p][_rng.randint(0, 11)] += diff

    hdr = ["Product"] + [m[:3] for m in MONTH_NAMES] + ["Total"]
    ret_rows = [hdr]
    for p in PRODUCTS:
        m = monthly_returns[p]
        ret_rows.append([p] + [str(v) for v in m] + [str(sum(m))])
    tot_by_month = [sum(monthly_returns[p][i] for p in PRODUCTS) for i in range(12)]
    ret_rows.append(["Total"] + [str(v) for v in tot_by_month] + [str(sum(tot_by_month))])
    story.append(_table(ret_rows,
                         col_widths=[75, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 45],
                         small=True))
    story.append(_sp())

    # ── Section 2: Return rates by product vs sales volume ──
    story += [
        Paragraph("2. Return Rate Analysis by Product — FY 2024", e["SectionHead"]),
        Paragraph("Return rate calculated as: returns / estimated unit sales. "
                  "Unit sales estimated from revenue and average unit price.", e["Body"]),
    ]
    avg_prices = {
        "Laptop": 1249, "Phone": 849, "Tablet": 589, "Headphones": 178,
        "Jacket": 118, "Jeans": 89, "Shoes": 94, "T-Shirt": 32,
        "Bedding": 124, "Decor": 98, "Furniture": 389, "Kitchen": 112,
        "Accessories": 64, "Apparel": 72, "Equipment": 148, "Footwear": 94,
        "Drinks": 12, "Frozen": 18, "Produce": 9, "Snacks": 14,
    }
    rr_rows = [["Product", "Category", "Annual Returns", "Est. Units Sold",
                "Return Rate", "Avg Refund", "Total Refund"]]
    for p in PRODUCTS:
        cat = CATEGORIES_MAP[p]
        cat_rev = CATEGORY_REVENUE[cat]
        est_units = int(cat_rev / avg_prices[p] / 5)  # 5 products per cat
        ret_count = TOP_RETURN_COUNTS[p]
        rate = ret_count / max(est_units, 1) * 100
        avg_refund = avg_prices[p] * _rng.uniform(0.85, 0.98)
        total_refund = avg_refund * ret_count
        rr_rows.append([
            p, cat, str(ret_count),
            f"{est_units:,}", f"{rate:.1f}%",
            _fmt(avg_refund), _fmt(total_refund),
        ])
    story.append(_table(rr_rows,
                         col_widths=[80, 85, 80, 90, 75, 80, 90], small=True))
    story.append(_sp())

    # ── Section 3: Return status pipeline ──
    story += [
        Paragraph("3. Return Status Distribution — FY 2024", e["SectionHead"]),
        Paragraph("Pipeline status for all 6,000 returns. Liability outstanding = "
                  "approved + pending cases not yet refunded.", e["Body"]),
    ]
    status_rows = [["Status", "Count", "% of Total", "Action", "Est. Liability"]]
    liabilities = {
        "rejected": 0, "refunded": 1953661, "pending": 1936453,
        "received": 1910563, "approved": 1897429,
    }
    for status, count in RETURN_STATUS_COUNTS.items():
        liab = liabilities[status]
        status_rows.append([
            status.upper(), str(count),
            f"{count/6000*100:.1f}%",
            "Closed — no refund" if status == "rejected" else
            "Settled" if status == "refunded" else "Action required",
            _fmt(liab) if liab > 0 else "$0",
        ])
    status_rows.append(["TOTAL", "6,000", "100%", "—",
                          _fmt(sum(v for k,v in liabilities.items() if k != "refunded"))])
    story.append(_table(status_rows, col_widths=[80, 70, 80, 160, 100]))
    story.append(_sp())

    # ── Section 4: Return reasons analysis ──
    story += [
        Paragraph("4. Return Reason Code Analysis — FY 2024", e["SectionHead"]),
        Paragraph("Standardized reason codes applied at return initiation. "
                  "One reason per return record.", e["Body"]),
    ]
    reason_counts = {
        "Defective":             1248,
        "Size/Fit":              1127,
        "Not as Described":       842,
        "Quality Issue":          684,
        "Damaged in Shipping":    578,
        "Changed Mind":           541,
        "Wrong Item":             498,
        "Duplicate Order":        482,
    }
    reason_rows = [["Reason Code", "Count", "% of Returns", "Top Product",
                     "Avg Resolution Days"]]
    top_by_reason = {
        "Defective": "Tablet", "Size/Fit": "Jeans", "Not as Described": "Decor",
        "Quality Issue": "Bedding", "Damaged in Shipping": "Kitchen",
        "Changed Mind": "Jacket", "Wrong Item": "Phone", "Duplicate Order": "Laptop",
    }
    for reason, cnt in reason_counts.items():
        reason_rows.append([
            reason, str(cnt), f"{cnt/6000*100:.1f}%",
            top_by_reason.get(reason, "—"),
            str(_rng.randint(2, 8)),
        ])
    story.append(_table(reason_rows, col_widths=[140, 65, 90, 100, 120]))
    story.append(_sp())

    # ── Section 5: Regional return rates ──
    story += [
        Paragraph("5. Return Rate by Region — FY 2024", e["SectionHead"]),
        Paragraph("Regional breakdown of returns cross-referenced with regional revenue "
                  "and customer counts.", e["Body"]),
    ]
    reg_ret = [
        ("West",    1080, 37880499.39, 2351),
        ("Central", 1440, 35679253.01, 4599),
        ("East",    1380, 36314020.57, 3676),
        ("South",   1140, 35470111.47, 2330),
        ("North",    960, 30251293.72, 2023),
    ]
    reg_rows = [["Region", "Returns", "Return Rate", "Revenue", "Returns/$M Rev",
                  "Returns/Customer"]]
    for reg, ret, rev, cust in reg_ret:
        txns = int(100000 * rev / 175595178.16)
        reg_rows.append([
            reg, str(ret), f"{ret/txns*100:.1f}%",
            _fmt(rev), f"{ret/(rev/1e6):.1f}",
            f"{ret/cust:.2f}",
        ])
    story.append(_table(reg_rows, col_widths=[75, 70, 85, 120, 100, 110]))
    story.append(_sp())

    # ── Section 6: Individual return records sample (500 records) ──
    story += [
        Paragraph("6. Returns Register — Individual Records (Sample: 500 of 6,000)",
                  e["SectionHead"]),
        Paragraph("Chronological log of return cases. Full register available via "
                  "OMS API endpoint /returns?page=N. Fields: return_id, transaction_id, "
                  "customer_id, product, reason, status, return_date, refund_amount.",
                  e["Body"]),
    ]
    rec_rows = [["Return ID", "Txn ID", "Customer", "Product", "Reason",
                  "Status", "Date", "Refund"]]
    _rng2 = random.Random(77)
    products_weighted = []
    for p, cnt in TOP_RETURN_COUNTS.items():
        products_weighted.extend([p] * cnt)
    for i in range(500):
        ret_id = f"RTN-2024-{i+1:05d}"
        txn_id = f"TXN-{_rng2.randint(1, 100000):06d}"
        cust_id = f"CUST{_rng2.randint(1, 14979):05d}"
        product = _rng2.choice(products_weighted)
        reason = _rng2.choice(RETURN_REASONS)
        status = _rng2.choice(RETURN_STATUSES)
        offset = _rng2.randint(0, 365)
        ret_date = _date_in_2024(offset)
        refund = _fmt(_rng2.uniform(15, 1800)) if status in ("refunded", "approved") else "$0.00"
        rec_rows.append([ret_id, txn_id, cust_id, product, reason, status, ret_date, refund])
    story.append(_table(rec_rows,
                         col_widths=[80, 75, 70, 80, 110, 70, 75, 65], small=True))
    story.append(_sp())

    # ── Section 7: Return policy reference ──
    story += [
        Paragraph("7. Current Return Policy Reference — Policy v2.0", e["SectionHead"]),
        Paragraph("Effective: Q3 2024. Return window: <b>30 days</b> from purchase date. "
                  "Full refund to original payment method. Electronics require original packaging. "
                  "Food/perishables non-returnable. This supersedes Policy v1.0 (14-day window, "
                  "retired Q2 2024). IMPORTANT: any system or document referencing 14-day window "
                  "is outdated.", e["Body"]),
        Paragraph("The 1,242 rejected returns (20.7%) include cases outside the 30-day window "
                  "and items returned without original packaging.", e["Body"]),
    ]

    story += [
        _hr(),
        Paragraph("OMS Export | Returns module v3.1 | Tables: returns (6,000), "
                  "sales_transactions (100,000), customers (14,979). "
                  "Join: returns.transaction_id → sales_transactions.id.", e["Caption"]),
    ]

    doc.build(story)
    print(f"  ✅ {out_path.name}")


# ─── PDF 3: Inventory Full Store Register ─────────────────────────────────────
# Real format: all 2,000 inventory records (100 stores × 20 products),
# low-stock alerts with store IDs, restocking queue, turnover velocity.

def build_inventory_register(out_path: Path) -> None:
    from reportlab.platypus import Paragraph
    doc = _make_doc(out_path, "Inventory Operations Register 2024")
    s, e = _styles()

    avg_prices = {
        "Laptop": 1249, "Phone": 849, "Tablet": 589, "Headphones": 178,
        "Jacket": 118, "Jeans": 89, "Shoes": 94, "T-Shirt": 32,
        "Bedding": 124, "Decor": 98, "Furniture": 389, "Kitchen": 112,
        "Accessories": 64, "Apparel": 72, "Equipment": 148, "Footwear": 94,
        "Drinks": 12, "Frozen": 18, "Produce": 9, "Snacks": 14,
    }
    reorder_pts = {
        "Laptop": 15, "Phone": 18, "Tablet": 14, "Headphones": 30,
        "Jacket": 25, "Jeans": 35, "Shoes": 30, "T-Shirt": 50,
        "Bedding": 20, "Decor": 25, "Furniture": 8, "Kitchen": 20,
        "Accessories": 40, "Apparel": 45, "Equipment": 15, "Footwear": 30,
        "Drinks": 80, "Frozen": 60, "Produce": 70, "Snacks": 90,
    }
    _rng3 = random.Random(55)

    # Generate the full 2,000-row inventory table
    inventory = []
    low_stock = []
    for region in REGIONS:
        for store in STORES[region]:
            for product in PRODUCTS:
                rp = reorder_pts[product]
                # 3.6% chance of being below reorder — adjusted to hit exactly 72
                stock = _rng3.randint(int(rp * 0.3), int(rp * 6))
                restocked = _date_in_2024(_rng3.randint(0, 350))
                inventory.append({
                    "store_id": store, "region": region, "product": product,
                    "category": CATEGORIES_MAP[product],
                    "stock_level": stock, "reorder_point": rp,
                    "below_reorder": stock < rp,
                    "last_restocked": restocked,
                    "unit_cost": avg_prices[product],
                    "inventory_value": stock * avg_prices[product],
                })
                if stock < rp:
                    low_stock.append((store, region, product, stock, rp))

    # Adjust to exactly 72 low-stock records
    current_low = sum(1 for rec in inventory if rec["below_reorder"])
    if current_low < 72:
        above = [i for i, rec in enumerate(inventory) if not rec["below_reorder"]]
        _rng3.shuffle(above)
        for idx in above[:72 - current_low]:
            rp = inventory[idx]["reorder_point"]
            inventory[idx]["stock_level"] = _rng3.randint(int(rp * 0.3), rp - 1)
            inventory[idx]["below_reorder"] = True
            inventory[idx]["inventory_value"] = (
                inventory[idx]["stock_level"] * inventory[idx]["unit_cost"]
            )
    elif current_low > 72:
        below = [i for i, rec in enumerate(inventory) if rec["below_reorder"]]
        _rng3.shuffle(below)
        for idx in below[:current_low - 72]:
            rp = inventory[idx]["reorder_point"]
            inventory[idx]["stock_level"] = _rng3.randint(rp, rp * 4)
            inventory[idx]["below_reorder"] = False
            inventory[idx]["inventory_value"] = (
                inventory[idx]["stock_level"] * inventory[idx]["unit_cost"]
            )

    low_stock = [(r["store_id"], r["region"], r["product"],
                  r["stock_level"], r["reorder_point"])
                 for r in inventory if r["below_reorder"]]

    story = []
    story += [
        Paragraph("NexusIQ Corporation — Supply Chain & Operations", s["Heading1"]),
        Paragraph("Inventory Operations Register — Year-End Snapshot FY 2024 (2,000 records)",
                  e["Subtitle"]),
        Paragraph("System: NexusIQ WMS v2.8 | Snapshot: 2024-12-31 23:59 UTC | "
                  "Records: 2,000 (100 stores × 20 SKUs) | Low-stock alerts: 72 | "
                  "Classification: Internal — Operations", e["Caption"]),
        _hr(), _sp(),
    ]

    # ── Section 1: Summary by region ──
    story += [
        Paragraph("1. Inventory Summary by Region — FY 2024 Year-End", e["SectionHead"]),
        Paragraph("Aggregated inventory position across 20 stores per region, 20 SKUs each.", e["Body"]),
    ]
    reg_sum_rows = [["Region", "Stores", "SKUs", "Total Records",
                      "Below Reorder", "Alert Rate", "Total Inv. Value"]]
    for region in REGIONS:
        region_inv = [r for r in inventory if r["region"] == region]
        below = sum(1 for r in region_inv if r["below_reorder"])
        total_val = sum(r["inventory_value"] for r in region_inv)
        reg_sum_rows.append([
            region, "20", "20", "400",
            str(below), f"{below/400*100:.1f}%",
            _fmt(total_val),
        ])
    story.append(_table(reg_sum_rows, col_widths=[75, 55, 50, 90, 90, 80, 110]))
    story.append(_sp())

    # ── Section 2: Summary by product category ──
    story += [
        Paragraph("2. Inventory Summary by Product Category", e["SectionHead"]),
        Paragraph("Category-level view: 4 SKUs × 100 stores = 400 records per category.", e["Body"]),
    ]
    cat_sum_rows = [["Category", "SKUs", "Records", "Below Reorder",
                      "Alert Rate", "Avg Stock Level", "Total Value"]]
    for cat in ["Electronics", "Home", "Clothing", "Sports", "Food"]:
        cat_inv = [r for r in inventory if r["category"] == cat]
        below = sum(1 for r in cat_inv if r["below_reorder"])
        avg_stock = sum(r["stock_level"] for r in cat_inv) / len(cat_inv)
        total_val = sum(r["inventory_value"] for r in cat_inv)
        cat_sum_rows.append([
            cat, "4", str(len(cat_inv)), str(below),
            f"{below/len(cat_inv)*100:.1f}%",
            f"{avg_stock:.0f}", _fmt(total_val),
        ])
    story.append(_table(cat_sum_rows, col_widths=[85, 45, 70, 90, 80, 100, 90]))
    story.append(_sp())

    # ── Section 3: All 72 low-stock alerts ──
    story += [
        Paragraph("3. Full Low-Stock Alert Register — 72 Records", e["SectionHead"]),
        Paragraph("All store-product combinations below reorder point as of 2024-12-31. "
                  "Emergency restock required for records marked CRITICAL (stock < 25% of reorder point).",
                  e["Body"]),
    ]
    alert_rows = [["Store ID", "Region", "Product", "Category",
                    "Current Stock", "Reorder Pt", "Gap", "Urgency"]]
    for store_id, region, product, stock, rp in sorted(low_stock,
                                                         key=lambda x: x[3] / x[4]):
        gap = rp - stock
        urgency = "CRITICAL" if stock < rp * 0.25 else "HIGH" if stock < rp * 0.5 else "MEDIUM"
        alert_rows.append([
            store_id, region, product, CATEGORIES_MAP[product],
            str(stock), str(rp), str(gap), urgency,
        ])
    story.append(_table(alert_rows,
                         col_widths=[65, 65, 80, 85, 80, 75, 50, 70], small=True))
    story.append(_sp())

    # ── Section 4: Full inventory register (2,000 rows — split across pages) ──
    story += [
        Paragraph("4. Complete Inventory Register — All 2,000 Records", e["SectionHead"]),
        Paragraph("Full store × SKU inventory snapshot at FY 2024 year-end. Sorted by region, "
                  "store, then product. Records with stock_level < reorder_point are flagged.",
                  e["Body"]),
    ]
    inv_rows = [["Store", "Region", "Product", "Cat", "Stock", "Reorder", "Value", "Status"]]
    for rec in inventory:
        status = "LOW" if rec["below_reorder"] else "OK"
        inv_rows.append([
            rec["store_id"], rec["region"], rec["product"],
            rec["category"][:4],
            str(rec["stock_level"]),
            str(rec["reorder_point"]),
            _fmt(rec["inventory_value"]),
            status,
        ])
    story.append(_table(inv_rows,
                         col_widths=[48, 58, 75, 42, 45, 55, 80, 45], small=True))
    story.append(_sp())

    # ── Section 5: Inventory vs revenue velocity ──
    story += [
        Paragraph("5. Inventory Turnover Velocity by SKU", e["SectionHead"]),
        Paragraph("Estimated turnover days based on FY 2024 sales velocity and "
                  "average inventory levels. Cross-references sales_transactions revenue "
                  "($175,595,178.16 total, 100,000 transactions).", e["Body"]),
    ]
    vel_rows = [["Product", "Category", "FY Returns", "Avg Stock",
                  "Est. Turnover", "Revenue Rank", "Restock Priority"]]
    rev_rank = {
        "Laptop": 1, "Phone": 2, "Tablet": 3, "Headphones": 4,
        "Bedding": 5, "Furniture": 6, "Decor": 7, "Kitchen": 8,
        "Equipment": 9, "Jeans": 10, "Shoes": 11, "Jacket": 12,
        "Accessories": 13, "Footwear": 14, "Apparel": 15, "T-Shirt": 16,
        "Frozen": 17, "Drinks": 18, "Produce": 19, "Snacks": 20,
    }
    turnover_days = {
        "Laptop": 20, "Phone": 18, "Tablet": 22, "Headphones": 28,
        "Jacket": 32, "Jeans": 29, "Shoes": 30, "T-Shirt": 15,
        "Bedding": 28, "Decor": 35, "Furniture": 48, "Kitchen": 31,
        "Accessories": 33, "Apparel": 27, "Equipment": 40, "Footwear": 38,
        "Drinks": 4, "Frozen": 3, "Produce": 3, "Snacks": 5,
    }
    for p in PRODUCTS:
        avg_stock = sum(r["stock_level"] for r in inventory if r["product"] == p) / 100
        vel_rows.append([
            p, CATEGORIES_MAP[p], str(TOP_RETURN_COUNTS[p]),
            f"{avg_stock:.0f}",
            f"{turnover_days[p]} days",
            f"#{rev_rank[p]}",
            "URGENT" if rev_rank[p] <= 4 else "HIGH" if rev_rank[p] <= 8 else "NORMAL",
        ])
    story.append(_table(vel_rows,
                         col_widths=[80, 85, 75, 75, 85, 80, 90], small=True))

    story += [
        _sp(), _hr(),
        Paragraph("WMS Export | Tables: inventory (2,000 rows), products (20 rows), "
                  "sales_transactions (100,000 rows). Snapshot: 2024-12-31.", e["Caption"]),
    ]

    doc.build(story)
    print(f"  ✅ {out_path.name}")


# ─── PDF 4: Support Case Log ───────────────────────────────────────────────────
# Real format: individual case records with ticket IDs, weekly volume tables,
# agent metrics, SLA compliance logs.

def build_support_case_log(out_path: Path) -> None:
    from reportlab.platypus import Paragraph
    doc = _make_doc(out_path, "Support Case Log 2024")
    s, e = _styles()
    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]

    _rng4 = random.Random(33)

    story = []
    story += [
        Paragraph("NexusIQ Corporation — Customer Experience", s["Heading1"]),
        Paragraph("Support Case Log — FY 2024 (2,000 cases)", e["Subtitle"]),
        Paragraph("System: NexusIQ CX Platform v5.0 | Export: 2025-01-05 | "
                  "Total cases: 2,000 | Resolved+Closed: 1,005 (50.3%) | "
                  "Classification: Internal", e["Caption"]),
        _hr(), _sp(),
    ]

    # ── Section 1: Monthly case volume ──
    story += [
        Paragraph("1. Monthly Case Volume by Priority — FY 2024", e["SectionHead"]),
        Paragraph("New cases opened each month. Total FY 2024: 2,000 cases.", e["Body"]),
    ]
    monthly_cases = {p: [_rng4.randint(30, 55) for _ in range(12)]
                     for p in SUPPORT_PRIORITIES}
    targets = {"low": 520, "high": 502, "urgent": 497, "medium": 481}
    for p in SUPPORT_PRIORITIES:
        raw = sum(monthly_cases[p])
        monthly_cases[p] = [int(v * targets[p] / raw) for v in monthly_cases[p]]
        diff = targets[p] - sum(monthly_cases[p])
        monthly_cases[p][_rng4.randint(0, 11)] += diff

    mc_hdr = ["Month"] + [p.title() for p in SUPPORT_PRIORITIES] + ["Monthly Total"]
    mc_rows = [mc_hdr]
    for mi, mn in enumerate(MONTH_NAMES):
        vals = [monthly_cases[p][mi] for p in SUPPORT_PRIORITIES]
        mc_rows.append([mn] + [str(v) for v in vals] + [str(sum(vals))])
    mc_rows.append(["YTD"] + [str(targets[p]) for p in SUPPORT_PRIORITIES] + ["2,000"])
    story.append(_table(mc_rows, col_widths=[55, 80, 75, 80, 85, 100]))
    story.append(_sp())

    # ── Section 2: Case status × priority matrix ──
    story += [
        Paragraph("2. Case Status × Priority Matrix — FY 2024", e["SectionHead"]),
        Paragraph("Distribution of case statuses broken down by priority level.", e["Body"]),
    ]
    status_prio_data = {
        "closed":      {"low": 138, "high": 131, "urgent": 130, "medium": 131},
        "in_progress": {"low": 132, "high": 128, "urgent": 124, "medium": 122},
        "open":        {"low": 126, "high": 122, "urgent": 120, "medium": 121},
        "resolved":    {"low": 124, "high": 121, "urgent": 123, "medium": 107},
    }
    sp_rows = [["Status"] + [p.title() for p in SUPPORT_PRIORITIES] + ["Row Total"]]
    for st, pdata in status_prio_data.items():
        row = [st.upper()] + [str(pdata[p]) for p in SUPPORT_PRIORITIES]
        row.append(str(sum(pdata.values())))
        sp_rows.append(row)
    sp_rows.append(["Col Total"] + [str(targets[p]) for p in SUPPORT_PRIORITIES] + ["2,000"])
    story.append(_table(sp_rows, col_widths=[90, 85, 75, 85, 90, 90]))
    story.append(_sp())

    # ── Section 3: Case volume by product category ──
    story += [
        Paragraph("3. Support Cases by Product Category — FY 2024", e["SectionHead"]),
        Paragraph("Cases categorized by the product involved in the inquiry. "
                  "Electronics dominates consistent with $91,010,125.61 revenue base.", e["Body"]),
    ]
    cat_case_rows = [["Category", "Cases", "% of Total", "Top Subject",
                       "Avg Priority Score", "Avg Resolution (days)"]]
    cat_cases = [
        ("Electronics", 840, "42.0%", "Defective device",    3.1, 2.1),
        ("Home",        560, "28.0%", "Return/refund",        2.4, 4.8),
        ("Clothing",    280, "14.0%", "Size exchange",        2.1, 3.2),
        ("Sports",      200, "10.0%", "Product inquiry",      1.9, 5.6),
        ("Food",        120, "6.0%",  "Delivery issue",       2.7, 1.8),
    ]
    for row in cat_cases:
        cat_case_rows.append([row[0], str(row[1]), row[2], row[3],
                               f"{row[4]:.1f}", f"{row[5]:.1f}"])
    story.append(_table(cat_case_rows, col_widths=[85, 60, 80, 150, 110, 115]))
    story.append(_sp())

    # ── Section 4: SLA compliance weekly log ──
    story += [
        Paragraph("4. SLA Compliance Weekly Log — FY 2024 (52 weeks)", e["SectionHead"]),
        Paragraph("Weekly SLA compliance rate per priority. Urgent SLA = 1 day; "
                  "High = 3 days; Medium = 5 days; Low = 7 days.", e["Body"]),
    ]
    sla_rows = [["Week", "Urgent %", "High %", "Medium %", "Low %", "Overall %"]]
    for wk in range(1, 53):
        u = _rng4.uniform(81, 96)
        h = _rng4.uniform(83, 97)
        m = _rng4.uniform(86, 98)
        lo = _rng4.uniform(89, 99)
        overall = (u + h + m + lo) / 4
        sla_rows.append([f"W{wk:02d}", f"{u:.1f}%", f"{h:.1f}%",
                          f"{m:.1f}%", f"{lo:.1f}%", f"{overall:.1f}%"])
    story.append(_table(sla_rows, col_widths=[50, 75, 65, 75, 65, 80], small=True))
    story.append(_sp())

    # ── Section 5: All 2,000 case records ──
    story += [
        Paragraph("5. Complete Case Register — All 2,000 Records", e["SectionHead"]),
        Paragraph("Full case log for FY 2024. Fields: case_id, customer_id, subject, "
                  "priority, status, created_at, resolved_at, product_category.", e["Body"]),
    ]
    case_rows = [["Case ID", "Customer", "Subject", "Priority", "Status",
                   "Created", "Resolved", "Category"]]
    subjects_pool = SUPPORT_SUBJECTS
    for i in range(2000):
        case_id = f"CASE-2024-{i+1:05d}"
        cust_id = f"CUST{_rng4.randint(1, 14979):05d}"
        subject = _rng4.choice(subjects_pool)
        priority = _rng4.choice(SUPPORT_PRIORITIES)
        status = _rng4.choice(SUPPORT_STATUSES)
        created = _date_in_2024(_rng4.randint(0, 360))
        resolved = _date_in_2024(_rng4.randint(0, 365)) if status in ("closed", "resolved") else "—"
        cat = _rng4.choice(list(CATEGORY_REVENUE.keys()))
        case_rows.append([case_id, cust_id, subject, priority, status,
                           created, resolved, cat])
    story.append(_table(case_rows,
                         col_widths=[80, 68, 110, 55, 72, 70, 70, 75], small=True))

    story += [
        _sp(), _hr(),
        Paragraph("CX Platform Export | Tables: support_cases (2,000 rows), customers (14,979 rows). "
                  "Join: support_cases.customer_id → customers.customer_id.", e["Caption"]),
    ]

    doc.build(story)
    print(f"  ✅ {out_path.name}")


# ─── PDF 5: Cross-Business Intelligence Register ───────────────────────────────
# Real format: joined views across all tables, product scorecards (all 20),
# store performance (all 100), quarterly P&L with all dimensions.

def build_cross_bi_register(out_path: Path) -> None:
    from reportlab.platypus import Paragraph
    doc = _make_doc(out_path, "Cross-Business Intelligence Register 2024")
    s, e = _styles()
    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    _rng5 = random.Random(88)

    avg_prices = {
        "Laptop": 1249, "Phone": 849, "Tablet": 589, "Headphones": 178,
        "Jacket": 118, "Jeans": 89, "Shoes": 94, "T-Shirt": 32,
        "Bedding": 124, "Decor": 98, "Furniture": 389, "Kitchen": 112,
        "Accessories": 64, "Apparel": 72, "Equipment": 148, "Footwear": 94,
        "Drinks": 12, "Frozen": 18, "Produce": 9, "Snacks": 14,
    }

    story = []
    story += [
        Paragraph("NexusIQ Corporation — Chief Analytics Office", s["Heading1"]),
        Paragraph("Cross-Business Intelligence Register — FY 2024 Full Data Extract",
                  e["Subtitle"]),
        Paragraph("Generated: 2025-01-06 | Source tables: sales_transactions (100,000), "
                  "customers (14,979), returns (6,000), inventory (2,000), "
                  "support_cases (2,000), products (20) | Classification: Executive",
                  e["Caption"]),
        _hr(), _sp(),
    ]

    # ── Section 1: Monthly revenue across all dimensions ──
    story += [
        Paragraph("1. Monthly Revenue & Operational KPIs — FY 2024", e["SectionHead"]),
        Paragraph("All KPIs tracked monthly. Revenue from sales_transactions; "
                  "returns/support from operations tables.", e["Body"]),
    ]
    monthly_rev = [
        ("Jan", 12.8, 421, 148, 182),
        ("Feb", 13.1, 438, 152, 168),
        ("Mar", 14.2, 492, 167, 173),
        ("Apr", 13.9, 467, 158, 165),
        ("May", 14.6, 501, 163, 171),
        ("Jun", 14.3, 489, 159, 168),
        ("Jul", 14.8, 511, 165, 174),
        ("Aug", 15.2, 524, 171, 180),
        ("Sep", 14.9, 509, 164, 172),
        ("Oct", 15.8, 537, 178, 188),
        ("Nov", 17.6, 612, 206, 219),
        ("Dec", 14.4, 499, 169, 180),
    ]
    rev_rows = [["Month", "Revenue", "Transactions", "Returns", "Support Cases",
                  "Return Rate", "Support Rate"]]
    for mn, rev, txns, rets, sups in monthly_rev:
        rev_rows.append([
            mn, f"${rev:.1f}M", f"{txns*200:,}", str(rets*12), str(sups*11),
            f"{rets*12/(txns*200)*100:.2f}%",
            f"{sups*11/(txns*200)*100:.2f}%",
        ])
    rev_rows.append([
        "FY 2024", "$175.6M", "100,000", "6,000", "2,000",
        "6.00%", "2.00%",
    ])
    story.append(_table(rev_rows, col_widths=[50, 75, 90, 70, 100, 80, 85]))
    story.append(_sp())

    # ── Section 2: Full product scorecard (all 20 SKUs) ──
    story += [
        Paragraph("2. Product Scorecard — All 20 SKUs, FY 2024", e["SectionHead"]),
        Paragraph("Multi-dimensional product view: revenue, returns, inventory health, "
                  "support cases. Cross-joins: sales_transactions + returns + inventory + "
                  "support_cases on product_name.", e["Body"]),
    ]
    ps_rows = [["Product", "Category", "Est. Revenue", "Units Sold",
                 "Returns", "Ret Rate", "Inv Alerts", "Support Cases"]]
    for p in PRODUCTS:
        cat = CATEGORIES_MAP[p]
        cat_rev = CATEGORY_REVENUE[cat]
        est_rev = cat_rev / 4 + _rng5.uniform(-cat_rev*0.1, cat_rev*0.1)
        est_units = int(est_rev / avg_prices[p])
        ret_cnt = TOP_RETURN_COUNTS[p]
        ret_rate = ret_cnt / max(est_units, 1) * 100
        inv_alerts = sum(1 for store in ALL_STORES
                         if _rng5.random() < 0.036)  # 3.6% rate
        sup_cnt = int(2000 * (ret_cnt / sum(TOP_RETURN_COUNTS.values())))
        ps_rows.append([
            p, cat, _fmt(est_rev), f"{est_units:,}",
            str(ret_cnt), f"{min(ret_rate, 25):.1f}%",
            str(min(inv_alerts, 8)), str(sup_cnt),
        ])
    story.append(_table(ps_rows,
                         col_widths=[80, 85, 95, 75, 60, 65, 70, 80], small=True))
    story.append(_sp())

    # ── Section 3: All 100 store performance ──
    story += [
        Paragraph("3. Store Performance Register — All 100 Stores, FY 2024",
                  e["SectionHead"]),
        Paragraph("Per-store sales performance cross-referenced with inventory health "
                  "and regional benchmarks. Revenue estimated from regional totals / 20 stores.",
                  e["Body"]),
    ]
    store_rows = [["Store ID", "Region", "Est. Revenue", "Transactions",
                    "Customers", "Returns", "Low-Stock SKUs", "Support Cases"]]
    for region in REGIONS:
        region_rev = REGION_REVENUE[region]
        region_cust = REGION_CUSTOMERS[region]
        for store in STORES[region]:
            store_rev = region_rev / 20 + _rng5.uniform(-region_rev*0.03, region_rev*0.03)
            store_txns = int(100000 * store_rev / 175595178.16)
            store_cust = int(region_cust / 20 + _rng5.randint(-30, 30))
            store_rets = int(6000 * store_rev / 175595178.16)
            low_skus = _rng5.randint(0, 4)
            sup_cases = int(2000 * store_rev / 175595178.16)
            store_rows.append([
                store, region, _fmt(store_rev), f"{store_txns:,}",
                str(store_cust), str(store_rets), str(low_skus), str(sup_cases),
            ])
    story.append(_table(store_rows,
                         col_widths=[60, 65, 90, 80, 70, 65, 90, 90], small=True))
    story.append(_sp())

    # ── Section 4: Quarterly P&L breakdown ──
    story += [
        Paragraph("4. Quarterly Business Performance — FY 2024", e["SectionHead"]),
        Paragraph("Full-year revenue broken into quarters with returns exposure, "
                  "support costs, and inventory adjustments.", e["Body"]),
    ]
    qtr_rows = [["Quarter", "Revenue", "Transactions", "Customers (New)",
                  "Returns", "Avg Refund", "Support Cases", "Net Revenue Est."]]
    qtrs = [
        ("Q1 2024", 40100000, 22900, 3780, 1260, 1618.61, 468, 38100000),
        ("Q2 2024", 42600000, 24300, 3841, 1440, 1618.61, 502, 40200000),
        ("Q3 2024", 44900000, 25600, 3822, 1560, 1618.61, 521, 42400000),
        ("Q4 2024", 47995178, 27200, 3536, 1740, 1618.61, 509, 45100000),
    ]
    for qname, rev, txns, new_cust, rets, avg_ref, sups, net in qtrs:
        qtr_rows.append([
            qname, _fmt(rev), f"{txns:,}", f"{new_cust:,}",
            str(rets), _fmt(avg_ref), str(sups), _fmt(net),
        ])
    qtr_rows.append([
        "FY 2024", "$175,595,178.16", "100,000", "14,979",
        "6,000", "$1,618.61", "2,000", "~$165,800,000",
    ])
    story.append(_table(qtr_rows,
                         col_widths=[65, 95, 80, 90, 65, 80, 80, 95]))
    story.append(_sp())

    # ── Section 5: Customer × returns × support joined view (200 records) ──
    story += [
        Paragraph("5. Customer 360 View — Joined Records (Sample: 200 Customers)",
                  e["SectionHead"]),
        Paragraph("Three-way join: customers LEFT JOIN returns USING (customer_id) "
                  "LEFT JOIN support_cases USING (customer_id). Shows combined customer "
                  "interaction profile.", e["Body"]),
    ]
    c360_rows = [["Customer ID", "Region", "FY Spend", "Transactions",
                   "Returns", "Open Cases", "Status"]]
    _rng5b = random.Random(21)
    for _ in range(200):
        cid = f"CUST{_rng5b.randint(1, 14979):05d}"
        region = _rng5b.choice(REGIONS)
        spend = _rng5b.uniform(500, 45000)
        txns = int(spend / _rng5b.uniform(800, 2500))
        rets = _rng5b.randint(0, 5)
        open_cases = _rng5b.randint(0, 3)
        if open_cases >= 2 or rets >= 4:
            status = "AT-RISK"
        elif spend > 15000:
            status = "LOYAL"
        else:
            status = "ACTIVE"
        c360_rows.append([cid, region, _fmt(spend), str(txns),
                           str(rets), str(open_cases), status])
    story.append(_table(c360_rows,
                         col_widths=[80, 65, 85, 80, 65, 80, 80], small=True))
    story.append(_sp())

    # ── Section 6: Policy and data integrity notes ──
    story += [
        Paragraph("6. Data Integrity & Policy Reference Notes", e["SectionHead"]),
        Paragraph("Return policy: 30-day window (v2.0, effective Q3 2024). "
                  "Previous 14-day policy (v1.0) retired Q2 2024 and must not be used "
                  "in operational calculations.", e["Alert"]),
        Paragraph("Revenue figures: $175,595,178.16 FY 2024 from sales_transactions (100,000 rows). "
                  "Quarterly split: Q1 $40.1M / Q2 $42.6M / Q3 $44.9M / Q4 $48.0M.", e["Body"]),
        Paragraph("Customer count: 14,979 unique customer_ids in sales_transactions, "
                  "avg spend $11,722.76, max $59,521.80. Regional: Central 4,599 / East 3,676 / "
                  "West 2,351 / South 2,330 / North 2,023.", e["Body"]),
        Paragraph("Returns: 6,000 records at $1,618.61 avg refund. Status: rejected 1,242 / "
                  "refunded 1,207 / pending 1,197 / received 1,181 / approved 1,173.", e["Body"]),
        Paragraph("Support: 2,000 cases. Priority: low 520 / high 502 / urgent 497 / medium 481. "
                  "Status: closed 530 / in_progress 506 / open 489 / resolved 475.", e["Body"]),
        Paragraph("Inventory: 2,000 records (100 stores × 20 SKUs). 72 below reorder point (3.6%).",
                  e["Body"]),
    ]

    story += [
        _sp(), _hr(),
        Paragraph("Executive Analytics Export | All source tables joined via customer_id, "
                  "transaction_id, product_name. FY 2024 data. USD.", e["Caption"]),
    ]

    doc.build(story)
    print(f"  ✅ {out_path.name}")


# ─── Generation + ingestion orchestration ─────────────────────────────────────

PDFS = [
    ("01_Customer_CRM_Export_2024.pdf",               build_customer_crm_export),
    ("02_Returns_Processing_Register_2024.pdf",        build_returns_register),
    ("03_Inventory_Operations_Register_2024.pdf",      build_inventory_register),
    ("04_Support_Case_Log_2024.pdf",                   build_support_case_log),
    ("05_Cross_Business_Intelligence_Register_2024.pdf", build_cross_bi_register),
]


def generate_all() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📊 Generating {len(PDFS)} data-dense analytics PDFs → {OUTPUT_DIR}\n")
    for filename, builder in PDFS:
        out = OUTPUT_DIR / filename
        print(f"  Building {filename}...")
        builder(out)
    print(f"\n✅ All {len(PDFS)} PDFs written.\n")


def ingest_all() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from database.setup_rag_pipeline import RAGPipelineSetup, bump_ingestion_version

    print(f"\n📥 Ingesting {CATEGORY} PDFs into ChromaDB...\n")
    pipeline = RAGPipelineSetup(reset_collection=False)

    for filename, _ in PDFS:
        pdf_path = OUTPUT_DIR / filename
        if not pdf_path.exists():
            print(f"  ⚠️  Missing: {filename} — run 'generate' first")
            continue

        print(f"\n  📄 {filename}")
        pages_data, metadata = pipeline.extract_text_from_pdf(pdf_path)
        if not pages_data:
            print(f"    ❌ No text extracted")
            continue

        # Delete stale chunks before re-ingesting
        try:
            existing = pipeline.collection.get(
                where={"filename": {"$eq": filename}}
            )
            if existing["ids"]:
                pipeline.collection.delete(ids=existing["ids"])
                print(f"    🗑️  Deleted {len(existing['ids'])} stale chunks")
        except Exception:
            pass

        chunks = pipeline.chunk_text(pages_data, metadata)
        print(f"    Created {len(chunks)} chunks")
        pipeline.embed_and_store(chunks)

    new_ver = bump_ingestion_version()
    total = pipeline.collection.count()
    print(f"\n✅ Ingestion complete. Collection size: {total} | Version: {new_ver}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate/ingest NexusIQ data-dense analytics PDFs")
    parser.add_argument("action",
                        choices=["generate", "ingest", "generate-and-ingest"])
    args = parser.parse_args()
    if args.action in ("generate", "generate-and-ingest"):
        generate_all()
    if args.action in ("ingest", "generate-and-ingest"):
        ingest_all()


if __name__ == "__main__":
    main()
