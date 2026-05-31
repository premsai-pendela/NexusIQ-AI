"""
Generate 15 enterprise operational documents for NexusIQ RAG corpus.

Prose-first business documents: SOPs, memos, analyses, reviews.
60-70% narrative paragraphs, 30-40% supporting tables.
Each document reads like a real company analyst wrote it.

Document list:
  01_Returns_Refunds_Policy.pdf
  02_Inventory_Reorder_SOP.pdf
  03_Customer_Escalation_Policy.pdf
  04_Q4_2024_Revenue_Performance_Memo.pdf
  05_Q3_2024_Revenue_Performance_Memo.pdf
  06_Electronics_Category_Deep_Dive.pdf
  07_Regional_Performance_Analysis.pdf
  08_Payment_Method_Adoption_Report.pdf
  09_Weekly_Operations_Digest_Week48.pdf
  10_Weekly_Operations_Digest_Week12.pdf
  11_Seasonal_Demand_Incident_Report.pdf
  12_Inventory_Shortage_Root_Cause_Analysis.pdf
  13_2024_Annual_Business_Review.pdf
  14_Customer_Lifetime_Value_Study.pdf
  15_Supply_Chain_Risk_Assessment.pdf

Ground-truth DB values (live Supabase, 2026-05-27):
  transactions: 100,000 | total_revenue: $175,595,178.16
  customers: 14,979 | avg_spend: $11,722.76 | max: $59,521.80
  regions: Central(4,599), East(3,676), West(2,351), South(2,330), North(2,023)
  region_revenue: West($37,880,499.39), East($36,314,020.57), Central($35,679,253.01),
                  South($35,470,111.47), North($30,251,293.72)
  category_revenue: Electronics($90,958,302.29), Home($40,877,008.66),
                    Sports($27,478,085.87), Clothing($11,731,765.10), Food($4,498,192.92)
  returns: 5,685 | avg_refund: $1,618.61
  return_statuses: rejected(1,242), refunded(1,207), pending(1,197), received(1,181), approved(1,173)
  support_priorities: low(520), high(502), urgent(497), medium(481)
  support_statuses: closed(530), in_progress(506), open(489), resolved(475)
  inventory_low_stock: 72 SKUs

Quarterly revenue:
  Q1 2024: $38,241,892.14  Q2 2024: $42,184,731.08
  Q3 2024: $48.9M  Q4 2024: $58.9M

Usage:
    python -m database.generate_analytics_pdfs generate
    python -m database.generate_analytics_pdfs ingest
    python -m database.generate_analytics_pdfs generate-and-ingest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "pdfs" / "08_analytics"
CATEGORY = "08_analytics"

# ─── Ground-truth constants ────────────────────────────────────────────────────

REGIONS = ["Central", "East", "West", "South", "North"]
REGION_CUSTOMERS = {"Central": 4599, "East": 3676, "West": 2351, "South": 2330, "North": 2023}
REGION_REVENUE = {
    "West": 37_880_499.39, "East": 36_314_020.57, "Central": 35_679_253.01,
    "South": 35_470_111.47, "North": 30_251_293.72,
}
TOTAL_REVENUE = 175_595_178.16
TOTAL_TRANSACTIONS = 100_000
TOTAL_CUSTOMERS = 14_979
AVG_SPEND = 11_722.76
MAX_CUSTOMER_SPEND = 59_521.80
TOTAL_RETURNS = 5_685
AVG_REFUND = 1_618.61

CATEGORY_REVENUE = {
    "Electronics": 90_958_302.29, "Home": 40_877_008.66,
    "Sports": 27_478_085.87, "Clothing": 11_731_765.10, "Food": 4_498_192.92,
}

Q1_REV = 38_241_892.14
Q2_REV = 42_184_731.08
Q3_REV = 43_322_149.57
Q4_REV = 58_900_000.00
Q4_ELECTRONICS_REV = 31_270_715.79
Q3_ELECTRONICS_REV = 25_779_650.28

TOP_RETURN_COUNTS = {
    "Jeans": 331, "Bedding": 325, "Decor": 322, "Kitchen": 315, "Tablet": 314,
    "Phone": 309, "Laptop": 302, "Shoes": 298, "Jacket": 287, "Headphones": 281,
    "T-Shirt": 274, "Furniture": 267, "Equipment": 261, "Apparel": 258,
    "Accessories": 252,
}

RETURN_STATUSES = {"rejected": 1242, "refunded": 1207, "pending": 1197,
                   "received": 1181, "approved": 1173}
SUPPORT_PRIORITIES = {"low": 520, "high": 502, "urgent": 497, "medium": 481}
SUPPORT_STATUSES = {"closed": 530, "in_progress": 506, "open": 489, "resolved": 475}


def _fmt(v: float) -> str:
    return f"${v:,.2f}"


def _fmtm(v: float) -> str:
    return f"${v / 1_000_000:.1f}M"


# ─── ReportLab helpers ─────────────────────────────────────────────────────────

def _make_doc(path: Path, title: str):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.units import inch
    return SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title=title, author="NexusIQ Business Operations",
    )


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    s = getSampleStyleSheet()
    extra = {
        "DocTitle": ParagraphStyle("DocTitle", parent=s["Heading1"],
                                   fontSize=15, textColor=colors.HexColor("#1a3c6e"),
                                   spaceBefore=0, spaceAfter=4),
        "Subtitle": ParagraphStyle("Subtitle", parent=s["Normal"],
                                   fontSize=10, textColor=colors.HexColor("#444444"),
                                   spaceAfter=4),
        "Meta": ParagraphStyle("Meta", parent=s["Normal"],
                               fontSize=8, textColor=colors.HexColor("#888888"),
                               spaceAfter=8),
        "SectionHead": ParagraphStyle("SectionHead", parent=s["Heading2"],
                                      fontSize=11, textColor=colors.HexColor("#1a3c6e"),
                                      spaceBefore=12, spaceAfter=4),
        "SubHead": ParagraphStyle("SubHead", parent=s["Heading3"],
                                  fontSize=10, textColor=colors.HexColor("#2c5f9e"),
                                  spaceBefore=8, spaceAfter=3),
        "Body": ParagraphStyle("Body", parent=s["Normal"],
                               fontSize=9.5, leading=14, spaceAfter=7),
        "Caption": ParagraphStyle("Caption", parent=s["Normal"],
                                  fontSize=8, textColor=colors.grey,
                                  spaceAfter=8, fontName="Helvetica-Oblique"),
        "Alert": ParagraphStyle("Alert", parent=s["Normal"],
                                fontSize=9.5, textColor=colors.HexColor("#b71c1c"),
                                leading=14, spaceAfter=7),
        "Note": ParagraphStyle("Note", parent=s["Normal"],
                               fontSize=9, textColor=colors.HexColor("#444400"),
                               leading=13, spaceAfter=5),
    }
    s.__dict__["byName"].update(extra)
    return s, extra


def _table(data, col_widths=None, small=False):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    fs = 8 if small else 9
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
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _hr():
    from reportlab.platypus import HRFlowable
    from reportlab.lib import colors
    return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1a3c6e"),
                      spaceAfter=4, spaceBefore=4)


def _sp(h=0.1):
    from reportlab.platypus import Spacer
    from reportlab.lib.units import inch
    return Spacer(1, h * inch)


def _pgbreak():
    from reportlab.platypus import PageBreak
    return PageBreak()


def P(text, style):
    from reportlab.platypus import Paragraph
    return Paragraph(text, style)


# ─── Document 1: Returns & Refunds Policy ─────────────────────────────────────

def build_returns_policy(out_path: Path) -> None:
    doc = _make_doc(out_path, "Returns and Refunds Policy — NexusIQ Corporation")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Returns & Refunds Policy", e["DocTitle"]),
        P("Standard Operating Procedure | Version 3.2 | Effective: January 1, 2024", e["Subtitle"]),
        P("Owner: Customer Operations | Review cycle: Bi-annual | Last revised: December 15, 2023 | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Purpose and Scope", e["SectionHead"]),
        P("This policy governs merchandise returns and refund issuance across all NexusIQ sales "
          "channels: direct e-commerce, regional distribution partners, and the NexusIQ mobile "
          "application. It applies to all 14,979 active customer accounts and all five product "
          "categories sold under the NexusIQ brand: Electronics, Home Goods, Sports and Fitness, "
          "Clothing and Apparel, and Food and Consumables.", e["Body"]),
        P("NexusIQ processed 5,685 returns in FY 2024, a 5.7% return rate against 100,000 "
          "transactions. Gross refund value totaled approximately $9,201,779 at the average refund "
          "of $1,618.61 per return. Managing return friction is a strategic priority: each "
          "unresolved return costs an estimated $47.20 in repeat-contact labor and creates "
          "measurable churn risk. The Electronics category warrants particular attention given "
          "average transaction values above $1,800.", e["Body"]),
        P("This document should be read alongside the Customer Escalation Policy (Section 4.3 "
          "covers return-driven escalation triggers) and the Inventory Reorder SOP (Section 7 "
          "addresses restocking returned goods).", e["Body"]),
    ]

    story += [
        P("2. Return Eligibility Criteria", e["SectionHead"]),
        P("A return is eligible for processing when all four conditions are satisfied. First, the "
          "item must be within the applicable return window defined in Section 3. Windows begin at "
          "confirmed delivery, not purchase date. Second, the customer must present a valid order "
          "reference number or receipt; loyalty members at Gold tier and above may use account "
          "lookup in lieu of a physical receipt. Third, the item must be in original or near-"
          "original condition. For Electronics, original packaging must be intact unless a "
          "manufacturing defect is documented. Fourth, the return reason must fall within accepted "
          "categories: Defective, Not As Described, Wrong Item Shipped, Size/Fit Issue "
          "(Clothing only), or Preference Change subject to a shorter window.", e["Body"]),
        P("Items ineligible for return include opened food products, software licenses and digital "
          "downloads, custom or personalized merchandise, and items marked Final Sale at purchase. "
          "Suspected fraudulent returns — flagged when an account shows more than three returns in "
          "90 days or return value exceeds 60% of annual purchase spend — route automatically "
          "to Risk Operations for manual review. In FY 2024, 147 accounts were flagged and 89 "
          "resulted in temporary account holds.", e["Body"]),
    ]

    story += [
        P("3. Return Windows and Refund Methods by Category", e["SectionHead"]),
        P("Return windows reflect the nature of each product type and observed customer behavior. "
          "Electronics carries the shortest standard window due to activation and licensing "
          "considerations. Clothing offers the longest window to accommodate fit-related returns, "
          "which represent 44% of all Clothing returns by reason code. The following table "
          "defines current return policy parameters effective January 1, 2024.", e["Body"]),
    ]
    rw_rows = [
        ["Category", "Standard Window", "Defective/DOA Window", "Refund Method", "Restocking Fee"],
        ["Electronics", "30 days", "90 days (mfr warranty)", "Original payment; store credit option", "None (defective); 15% (preference)"],
        ["Home Goods", "45 days", "60 days", "Original payment method", "None"],
        ["Sports & Fitness", "45 days", "60 days", "Original payment method", "None"],
        ["Clothing & Apparel", "60 days", "60 days", "Original payment or exchange", "None"],
        ["Food & Consumables", "14 days (unopened)", "30 days (sealed defect)", "Original payment method", "None"],
    ]
    story += [
        _table(rw_rows, col_widths=[90, 80, 110, 140, 125]),
        P("Window begins at delivery confirmation per carrier tracking. Effective January 1, 2024.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("4. Refund Processing Timeline and Status Tracking", e["SectionHead"]),
        P("Once a return is approved, refunds process through the original payment gateway. "
          "NexusIQ's internal processing target is 48 hours from return receipt to refund "
          "initiation. FY 2024 actual average was 51.3 hours, slightly above target due to "
          "elevated Q4 holiday volume. The returns table in the NexusIQ operations database "
          "tracks each return through five statuses. As of year-end 2024, status distribution "
          "was as follows:", e["Body"]),
    ]
    status_rows = [
        ["Status", "FY 2024 Count", "% of Total", "Avg Days to Resolution", "Description"],
        ["Refunded", "1,144", "20.1%", "3.2 days", "Refund issued to original payment method"],
        ["Approved", "1,112", "19.6%", "1.8 days", "Approved; refund queued for processing"],
        ["Pending", "1,134", "19.9%", "6.1 days", "In transit or awaiting quality inspection"],
        ["Received", "1,120", "19.7%", "2.4 days", "Item received; inspection in progress"],
        ["Rejected", "1,175", "20.7%", "4.7 days", "Return denied; customer notified per policy"],
        ["Total", "5,685", "100%", "3.6 days avg", "All FY 2024 return records"],
    ]
    story += [
        _table(status_rows, col_widths=[80, 90, 70, 105, 200]),
        P("Source: returns table. FY 2024. Resolution days measured from return_date to status_updated.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("5. High-Return-Rate Products — FY 2024", e["SectionHead"]),
        P("Product-level return rate analysis is conducted quarterly to identify quality issues, "
          "listing inaccuracies, or sizing inconsistencies. Jeans led all products with 331 returns "
          "in FY 2024, consistent with the category pattern where fit dissatisfaction drives 44% "
          "of Clothing returns. Among Electronics, Tablet (314 returns) and Phone (309) combined "
          "for 623 returns; quality team investigation in Q3 2024 identified a specific Tablet "
          "model with an accelerometer calibration defect accounting for 87 of those returns. "
          "That defect was addressed in a supplier corrective action filed in September 2024.", e["Body"]),
    ]
    pr_rows = [
        ["Product", "Category", "Return Count", "Primary Return Reason", "Action Status"],
        ["Jeans", "Clothing", "331", "Size/Fit Issue", "Sizing guide updated Oct 2024"],
        ["Bedding", "Home", "325", "Not As Described", "Listing photos updated Q3 2024"],
        ["Decor", "Home", "322", "Not As Described", "Description review in progress"],
        ["Kitchen", "Home", "315", "Defective/Damaged", "Packaging upgrade Q2 2024"],
        ["Tablet", "Electronics", "314", "Defective — Calibration", "Supplier corrective action filed Sep 2024"],
        ["Phone", "Electronics", "309", "Defective/Malfunctioning", "Firmware update issued Aug 2024"],
        ["Laptop", "Electronics", "302", "Performance Issue", "QC checklist updated"],
        ["Shoes", "Clothing", "298", "Size/Fit Issue", "Size chart revision in progress"],
        ["Jacket", "Clothing", "287", "Size/Fit Issue", "Sizing guide updated Oct 2024"],
        ["Headphones", "Electronics", "281", "Defective/Malfunctioning", "Supplier audit scheduled Q1 2025"],
    ]
    story += [
        _table(pr_rows, col_widths=[80, 80, 80, 140, 165]),
        _sp(),
    ]

    story += [
        P("6. Exception Handling and Appeals", e["SectionHead"]),
        P("When a return is rejected under standard criteria, customers may request supervisory "
          "review within 14 days of the rejection notice. In FY 2024 approximately 18% of "
          "rejections were appealed; 31% of appeals were overturned. Most overturned cases "
          "involved defect evidence submitted after initial rejection, or carrier delays that "
          "pushed a return past the window through no fault of the customer.", e["Body"]),
        P("Customers at Platinum and Diamond loyalty tiers — those with cumulative spend "
          "exceeding $15,000 — receive one courtesy return exception per 12-month period. "
          "This policy was introduced in Q2 2024 following churn analysis showing loyalty-tier "
          "customers who experienced a rejected return had a 34% higher 90-day churn rate than "
          "those whose returns were accepted. Exception authority rests with Customer Operations "
          "supervisors and is not available to front-line agents.", e["Body"]),
        P("For escalation paths beyond supervisor level, refer to the Customer Escalation Policy, "
          "specifically Section 4: Cross-Functional Escalation Procedures. Policy questions "
          "should be directed to the Operations Policy inbox.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 2: Inventory Reorder SOP ────────────────────────────────────────

def build_inventory_reorder_sop(out_path: Path) -> None:
    doc = _make_doc(out_path, "Inventory Reorder SOP — NexusIQ Corporation")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Inventory Reorder Standard Operating Procedure", e["DocTitle"]),
        P("Operations SOP | Version 2.1 | Effective: March 1, 2024", e["Subtitle"]),
        P("Owner: Supply Chain Operations | Review cycle: Quarterly | Last revised: February 20, 2024 | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Purpose and Scope", e["SectionHead"]),
        P("This SOP defines procedures for inventory monitoring, reorder threshold triggers, "
          "purchase order initiation, and emergency procurement across all NexusIQ distribution "
          "facilities. The inventory table covers 2,000 records representing 100 stores across "
          "five regions — Central, East, West, South, and North — each stocking 20 product SKUs "
          "across the Electronics, Home, Sports, Clothing, and Food categories.", e["Body"]),
        P("As of the latest inventory snapshot, 72 SKUs across the network are below their "
          "defined reorder point, representing 3.6% of total inventory positions. This figure "
          "is above the target threshold of 2.5% and has triggered a Category 2 supply chain "
          "alert per Section 5 of this document. Electronics and Home categories account for "
          "the majority of below-reorder positions, driven by Q4 holiday demand exceeding "
          "forecast by 14% in Electronics and 9% in Home.", e["Body"]),
        P("This document should be read alongside the Seasonal Demand Incident Report (November "
          "2024) and the Inventory Shortage Root Cause Analysis, which provide background on "
          "the Q4 demand surge that produced current low-stock conditions.", e["Body"]),
    ]

    story += [
        P("2. Reorder Threshold Definitions", e["SectionHead"]),
        P("Reorder points are calculated using a standard formula: Reorder Point = (Average Daily "
          "Sales x Lead Time Days) + Safety Stock. Safety stock is set at 1.5 standard deviations "
          "of daily demand variability to provide approximately 93% service level protection. "
          "Lead time assumptions are reviewed quarterly with each vendor and updated in the "
          "procurement system. Electronics carries the longest lead time due to international "
          "component sourcing; Food carries the shortest due to regional supplier networks.", e["Body"]),
    ]
    threshold_rows = [
        ["Category", "Avg Daily Units Sold", "Lead Time (days)", "Safety Stock (units)", "Reorder Point", "Current Low-Stock SKUs"],
        ["Electronics", "42 units", "21 days", "88 units", "970 units", "28 SKUs"],
        ["Home", "38 units", "18 days", "72 units", "756 units", "19 SKUs"],
        ["Sports", "31 units", "14 days", "58 units", "492 units", "12 SKUs"],
        ["Clothing", "29 units", "16 days", "55 units", "519 units", "8 SKUs"],
        ["Food", "24 units", "7 days", "45 units", "213 units", "5 SKUs"],
        ["All Categories", "164 units avg", "15 days avg", "64 units avg", "590 units avg", "72 SKUs total"],
    ]
    story += [
        _table(threshold_rows, col_widths=[90, 100, 90, 100, 90, 105]),
        P("Source: inventory table, procurement system. As of latest snapshot. Lead times per vendor agreements.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("3. Reorder Initiation Procedures", e["SectionHead"]),
        P("When a SKU falls below its reorder point, the inventory management system generates "
          "an automated purchase order draft within four hours. The draft is reviewed by the "
          "category buyer before submission to avoid duplicate orders or orders that conflict "
          "with pending inbound shipments. For standard reorders the buyer review window is "
          "24 hours; for high-velocity SKUs — defined as those with daily sales exceeding "
          "twice the category average — the window is reduced to four hours.", e["Body"]),
        P("Purchase orders are submitted electronically to primary vendors via the supplier "
          "portal. Vendors are required to acknowledge receipt within 8 business hours and "
          "provide a confirmed ship date within 24 hours. Orders not acknowledged within the "
          "window are escalated to the supply chain manager and the backup vendor is contacted "
          "simultaneously.", e["Body"]),
        P("Quantities ordered follow an Economic Order Quantity calculation to balance ordering "
          "costs against carrying costs. In practice, EOQ quantities are rounded up to the "
          "nearest pallet quantity to optimize freight costs. During Q4 seasonal periods "
          "(October through December), order quantities are multiplied by a 1.3 seasonal "
          "factor for Electronics and Home categories based on historical demand patterns.", e["Body"]),
    ]

    story += [
        P("4. Current Low-Stock Alert Summary", e["SectionHead"]),
        P("The following stores have the highest concentration of below-reorder-point SKUs "
          "as of the latest inventory snapshot. Store identifiers follow the format "
          "[Region Initial][Store Number]. Stores with five or more low-stock positions "
          "are classified as high-priority and receive daily replenishment review until "
          "stock levels are restored. The current situation is concentrated in West and "
          "Central region stores, consistent with their higher Electronics transaction mix "
          "as documented in the Regional Performance Analysis.", e["Body"]),
    ]
    alert_rows = [
        ["Store ID", "Region", "Low-Stock SKUs", "Most Affected Category", "Expected Restock Date", "Priority"],
        ["W014", "West", "8 SKUs", "Electronics", "Dec 18, 2024", "HIGH"],
        ["W007", "West", "7 SKUs", "Electronics, Home", "Dec 19, 2024", "HIGH"],
        ["C003", "Central", "6 SKUs", "Electronics", "Dec 20, 2024", "HIGH"],
        ["W019", "West", "5 SKUs", "Home", "Dec 21, 2024", "HIGH"],
        ["C011", "Central", "5 SKUs", "Electronics", "Dec 21, 2024", "HIGH"],
        ["E008", "East", "4 SKUs", "Home, Sports", "Dec 22, 2024", "MEDIUM"],
        ["S002", "South", "4 SKUs", "Clothing", "Dec 22, 2024", "MEDIUM"],
        ["N005", "North", "3 SKUs", "Sports", "Dec 24, 2024", "NORMAL"],
        ["E015", "East", "3 SKUs", "Electronics", "Dec 24, 2024", "NORMAL"],
        ["All others", "Various", "27 SKUs (2 each)", "Mixed", "Dec 22–28, 2024", "NORMAL"],
    ]
    story += [
        _table(alert_rows, col_widths=[60, 60, 80, 130, 120, 70]),
        P("72 total SKUs below reorder point as of snapshot. 26 HIGH priority stores require daily review.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("5. Emergency Reorder Procedures", e["SectionHead"]),
        P("When a store reaches zero inventory on a high-velocity SKU before a scheduled "
          "reorder arrives — a stockout event — the supply chain team initiates an emergency "
          "transfer from the nearest regional distribution center with available stock. "
          "Emergency transfers carry a 40% premium over standard replenishment costs due to "
          "expedited freight. In FY 2024, 23 emergency transfers were executed, predominantly "
          "in Q4; total emergency freight premium cost was approximately $87,400.", e["Body"]),
        P("If regional distribution center stock is also depleted, the category buyer contacts "
          "the top three vendors for emergency spot orders. Spot order pricing is typically "
          "8-15% above contracted pricing. Any spot order exceeding $25,000 requires Supply "
          "Chain Manager approval. The decision to accept spot order pricing versus accepting "
          "a stockout period is made on a SKU-by-SKU basis considering the product margin, "
          "expected stockout duration, and availability of substitutes.", e["Body"]),
        P("Following any emergency reorder event, a root cause analysis is completed within "
          "five business days. The analysis examines whether the event resulted from forecast "
          "error, vendor delivery failure, or demand anomaly. Results feed into the quarterly "
          "reorder parameter review. For the most recent emergency reorder analysis, see the "
          "Inventory Shortage Root Cause Analysis document.", e["Body"]),
    ]

    story += [
        P("6. Vendor Performance Monitoring", e["SectionHead"]),
        P("Vendors are scored quarterly on three dimensions: on-time delivery rate (target "
          ">95%), fill rate on ordered quantities (target >98%), and product quality acceptance "
          "rate (target >99.5%). Vendors falling below target on any dimension receive a "
          "formal performance notice and must submit a corrective action plan within 14 days. "
          "Vendors with two consecutive quarters below target on delivery or fill rate are "
          "placed on probation and the backup vendor share is increased from 15% to 40% of "
          "category orders.", e["Body"]),
    ]
    vendor_rows = [
        ["Category", "Primary Vendor", "On-Time Delivery", "Fill Rate", "Quality Rate", "Status"],
        ["Electronics", "TechSource Global", "94.2%", "97.8%", "99.6%", "Performance Notice — Delivery"],
        ["Home", "HomeSupply Co", "96.1%", "98.4%", "99.7%", "Good Standing"],
        ["Sports", "SportPro Dist.", "95.8%", "98.1%", "99.8%", "Good Standing"],
        ["Clothing", "FashionLink", "93.7%", "97.2%", "99.4%", "Performance Notice — Fill Rate"],
        ["Food", "FreshChain Ltd", "97.3%", "99.1%", "99.9%", "Good Standing"],
    ]
    story += [
        _table(vendor_rows, col_widths=[80, 110, 90, 70, 80, 115]),
        P("Q4 2024 vendor scorecard. TechSource and FashionLink on performance notice.", e["Caption"]),
        _sp(),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 3: Customer Escalation Policy ───────────────────────────────────

def build_escalation_policy(out_path: Path) -> None:
    doc = _make_doc(out_path, "Customer Escalation Policy — NexusIQ Corporation")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Customer Escalation Policy", e["DocTitle"]),
        P("Standard Operating Procedure | Version 4.0 | Effective: January 1, 2024", e["Subtitle"]),
        P("Owner: Customer Success | Review cycle: Quarterly | Last revised: December 10, 2023 | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Purpose and Escalation Philosophy", e["SectionHead"]),
        P("NexusIQ operates a tiered customer support structure across 2,000 active support "
          "cases in FY 2024. The escalation framework exists to ensure that customer issues "
          "exceeding the resolution authority of front-line agents are transferred quickly "
          "and with full context to personnel with the authority and expertise to resolve them. "
          "Escalation is not a failure indicator; it is a designed pathway for complex cases.", e["Body"]),
        P("FY 2024 support case distribution by priority: low 520 cases (26.0%), high 502 "
          "cases (25.1%), urgent 497 cases (24.9%), medium 481 cases (24.1%). Resolution "
          "status at year-end: closed 530 (26.5%), in-progress 506 (25.3%), open 489 (24.5%), "
          "resolved 475 (23.8%). Cases classified as urgent that remain open beyond 24 hours "
          "trigger automatic supervisor notification.", e["Body"]),
    ]

    story += [
        P("2. Escalation Tier Definitions", e["SectionHead"]),
        P("The escalation structure has four tiers. Tier 1 is front-line customer service, "
          "handling routine inquiries, order status checks, standard returns, and policy "
          "clarifications. Tier 1 agents have authority to issue refunds up to $200 and "
          "apply standard return windows without supervisor approval. Tier 2 is the senior "
          "specialist team, handling complex returns, billing disputes, multi-transaction "
          "issues, and cases requiring cross-department coordination. Tier 3 is the Customer "
          "Success Manager tier, handling high-value customer retention cases, cases involving "
          "potential legal exposure, and customers whose lifetime value exceeds $10,000. "
          "Tier 4 is the Executive Escalation path for media-facing complaints, regulatory "
          "inquiries, and cases flagged by the legal team.", e["Body"]),
    ]
    tier_rows = [
        ["Tier", "Role", "Authority Limit", "Avg Case Volume/Day", "Resolution Target"],
        ["Tier 1", "Front-Line Agent", "Refunds to $200; standard policy", "18 cases/agent", "Same day"],
        ["Tier 2", "Senior Specialist", "Refunds to $1,500; policy exceptions", "9 cases/agent", "48 hours"],
        ["Tier 3", "Success Manager", "Refunds unlimited; retention offers", "4 cases/manager", "72 hours"],
        ["Tier 4", "Executive / Legal", "Full authority", "As needed", "Case by case"],
    ]
    story += [
        _table(tier_rows, col_widths=[50, 120, 170, 110, 95]),
        _sp(),
    ]

    story += [
        P("3. Escalation Triggers and Response Time SLAs", e["SectionHead"]),
        P("Cases are escalated when any of the following triggers fire: refund amount exceeds "
          "the agent's authority limit, the customer makes a repeat contact on the same issue "
          "for the third time within 30 days, the customer explicitly requests supervisor "
          "review, the case involves a product safety concern, or the case has remained open "
          "beyond the tier SLA. Urgent priority cases have compressed SLAs across all tiers "
          "to ensure rapid resolution of time-sensitive issues.", e["Body"]),
    ]
    sla_rows = [
        ["Priority", "Tier 1 Initial Response", "Tier 1 Resolution Target", "Tier 2 Response", "Tier 3 Response"],
        ["Urgent", "30 minutes", "4 hours", "1 hour", "2 hours"],
        ["High", "2 hours", "Same business day", "4 hours", "Same day"],
        ["Medium", "4 hours", "48 hours", "8 hours", "24 hours"],
        ["Low", "8 hours", "5 business days", "24 hours", "48 hours"],
    ]
    story += [
        _table(sla_rows, col_widths=[70, 120, 130, 110, 115]),
        P("SLAs measured from case creation timestamp. Breach notifications fire automatically at 80% of SLA window.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("4. Return-Driven Escalation Procedures", e["SectionHead"]),
        P("Return cases frequently escalate when the customer disputes a rejection decision "
          "or when the return involves a high-value Electronics item. Per the Returns and "
          "Refunds Policy (Section 6), rejected returns may be appealed within 14 days. "
          "Those appeals enter the support queue at Tier 2 automatically, bypassing Tier 1 "
          "review to reduce repeat customer effort.", e["Body"]),
        P("In FY 2024, return-driven escalations accounted for 31% of all Tier 2 cases. "
          "The most common reasons were: rejected return appeal (42% of return escalations), "
          "refund not received within expected timeline (28%), and product defect dispute "
          "requiring quality team input (18%). The remaining 12% involved cases where the "
          "customer's return tracking showed delivery but no NexusIQ receipt acknowledgment, "
          "typically caused by processing delays at regional return centers.", e["Body"]),
    ]

    story += [
        P("5. High-Value Customer Handling", e["SectionHead"]),
        P("Customers with lifetime spend above $15,000 — approximately 1,390 accounts "
          "based on FY 2024 customer spend analysis — are flagged in the CRM as Platinum "
          "or Diamond tier. When a flagged customer contacts support, the case is routed "
          "directly to a dedicated senior specialist pool rather than general Tier 1 queue. "
          "This routing reduced average resolution time for high-value customers from "
          "3.8 days to 1.4 days following its introduction in Q1 2024.", e["Body"]),
        P("High-value customers are also eligible for proactive outreach when the system "
          "detects a negative signal: a return submitted, a support case open beyond 48 hours, "
          "or a purchase not completed after cart abandonment. Proactive outreach increased "
          "high-value customer satisfaction scores from 78% to 86% over FY 2024.", e["Body"]),
    ]

    story += [
        P("6. FY 2024 Escalation Performance Summary", e["SectionHead"]),
    ]
    perf_rows = [
        ["Metric", "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "FY 2024"],
        ["Total support cases", "481", "492", "503", "524", "2,000"],
        ["Tier 2 escalations", "112", "118", "124", "141", "495 (24.8%)"],
        ["Tier 3 escalations", "28", "31", "33", "41", "133 (6.7%)"],
        ["Avg resolution time (all)", "2.9 days", "2.7 days", "2.6 days", "3.1 days", "2.8 days avg"],
        ["SLA breach rate", "8.2%", "7.1%", "6.8%", "9.4%", "7.9% avg"],
        ["Customer satisfaction (CSAT)", "79%", "81%", "82%", "80%", "80.5% avg"],
    ]
    story += [
        _table(perf_rows, col_widths=[160, 60, 60, 60, 60, 95]),
        P("Q4 2024 escalation volume and resolution time reflect holiday season demand surge. "
          "See Seasonal Demand Incident Report for root cause analysis.", e["Caption"]),
        _sp(),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 4: Q4 2024 Revenue Performance Memo ─────────────────────────────

def build_q4_revenue_memo(out_path: Path) -> None:
    doc = _make_doc(out_path, "Q4 2024 Revenue Performance Memo — NexusIQ")
    s, e = _styles()
    story = []

    # Q4 category split (Electronics heavy in holiday)
    q4_cat = {
        "Electronics": Q4_ELECTRONICS_REV,  # 53.1% of Q4
        "Home": 13_134_700.00,              # 22.3%
        "Sports":  9_188_400.00,            # 15.6%
        "Clothing": 3_946_300.00,           # 6.7%
        "Food":  1_413_600.00,              # 2.4%
    }  # aligned with the SQL-backed Q4 financial report

    story += [
        P("NexusIQ Corporation — Q4 2024 Revenue Performance Memo", e["DocTitle"]),
        P("Internal Analysis | Prepared by: Finance & Analytics Team | Date: January 8, 2025", e["Subtitle"]),
        P("Period: October 1 – December 31, 2024 | Distribution: Leadership Team, Category Managers | "
          "Classification: Confidential", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("Executive Summary", e["SectionHead"]),
        P("Q4 2024 revenue reached $58.9M, representing 33.5% of the full-year total of "
          "$175,595,178.16. This is a 20.6% increase over Q3 2024 and marks "
          "the highest quarterly revenue in NexusIQ's operating history. The result exceeded the "
          "Q4 internal forecast of $55.0M by $3.9M, or 7.1%. The outperformance was driven "
          "primarily by Electronics, which contributed $31,270,715.79 in Q4 — representing "
          "53.1% of quarterly revenue versus its 51.8% annual average, and a 21.3% increase "
          "over Q3 Electronics revenue of approximately $25.8M.", e["Body"]),
        P("The quarterly strength validates the demand thesis behind Q3 inventory investments "
          "in Laptop, Phone, and Tablet SKUs. However, the demand surge also exposed supply "
          "chain constraints detailed in the Inventory Shortage Root Cause Analysis and the "
          "Seasonal Demand Incident Report. As of December 31, 72 SKUs remain below reorder "
          "point across the network — a supply condition the operations team is actively "
          "addressing per the Inventory Reorder SOP.", e["Body"]),
    ]

    story += [
        P("Q4 Monthly Revenue Progression", e["SectionHead"]),
        P("Revenue ramped steadily through Q4, with the largest single-week revenue in company "
          "history occurring during Week 48 (November 25–December 1, 2024) — the Black Friday "
          "and Cyber Monday period. December 2024 was the highest-revenue month on record at "
          "$19.0M, driven by Electronics gift purchases and Home category seasonal promotions.", e["Body"]),
    ]
    monthly_rows = [
        ["Month", "Revenue", "Transactions", "Avg Transaction Value", "vs Prior Month", "vs Q4 Target"],
        ["October 2024", "$15,823,416.22", "30,284", "$522.44", "— (Q4 start)", "+1.2%"],
        ["November 2024", "$17,161,849.28", "32,817", "$523.06", "+8.5%", "+6.8%"],
        ["December 2024", "$18,861,139.87", "36,899", "$511.17", "+9.9%", "+12.4%"],
        ["Q4 2024 Total", "$58.9M", "29,500", "$1,998 avg", "+20.6% vs Q3", "+7.1% vs forecast"],
    ]
    story += [
        _table(monthly_rows, col_widths=[100, 110, 80, 110, 90, 95]),
        P("Note: 100,000 transactions is the full-year figure. Monthly transaction counts are proportional estimates. "
          "Avg transaction value reflects all categories.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("Category Performance Analysis", e["SectionHead"]),
        P("Electronics delivered $31,270,715.79 in Q4 — a record quarterly high for the "
          "category and a 53.1% share of Q4 revenue. Laptop, Phone, and Tablet collectively "
          "drove 78% of Electronics Q4 revenue, consistent with their holiday gift demand "
          "profile. The Electronics category benefited from a targeted promotional campaign "
          "in November that offered bundle pricing on Laptop plus Headphones, which increased "
          "average Electronics transaction value by 12% in November versus October.", e["Body"]),
        P("Home Goods performed strongly at $11,406,208.78 (22% of Q4), driven by seasonal "
          "demand for Bedding and Kitchen products in November and December. Sports and Fitness "
          "was in line with expectations at $5,184,640.54; the category typically softens in "
          "Q4 as outdoor sports equipment demand decreases in colder months. Clothing came in "
          "at $4,665,376.48, supported by winter apparel but somewhat dampened by ongoing "
          "high return rates in the Jeans and Jacket subcategories. Food remained the smallest "
          "category at $3,607,849.77, consistent with its position as a complementary "
          "offering rather than a primary demand driver.", e["Body"]),
    ]
    cat_rows = [
        ["Category", "Q4 2024 Revenue", "% of Q4", "Q3 2024 Revenue", "QoQ Growth", "Full-Year Revenue"],
        ["Electronics", "$31,270,715.79", "53.1%", "$25,779,650", "+21.3%", "$90,958,302.29"],
        ["Home", "$13,134,700", "22.3%", "$10,855,124", "+21.0%", "$40,877,008.66"],
        ["Sports", "$9,188,400", "15.6%", "$7,747,386", "+18.6%", "$27,478,085.87"],
        ["Clothing", "$3,946,300", "6.7%", "$3,307,880", "+19.3%", "$11,731,765.10"],
        ["Food", "$1,413,600", "2.4%", "$1,186,902", "+19.1%", "$4,498,192.92"],
        ["Total", "$58.9M", "100%", "$48.9M", "+20.6%", "$175,595,178.16"],
    ]
    story += [
        _table(cat_rows, col_widths=[90, 110, 65, 100, 80, 110]),
        P("Q3 category revenues are estimates based on Q3 total and category share assumptions. "
          "Full-year figures are confirmed from sales_transactions table.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("Regional Performance", e["SectionHead"]),
        P("The West region led Q4 absolute revenue contribution, consistent with its full-year "
          "position as the top-revenue region at $37,880,499.39 for FY 2024. West's outperformance "
          "in Q4 was driven by a higher Electronics mix than other regions: West customers show "
          "a preference for premium Laptop and Phone SKUs that command above-average transaction "
          "values. The East region was a close second, benefiting from strong Home category "
          "performance driven by holiday home furnishing purchases.", e["Body"]),
        P("The South region showed the most significant Q4 acceleration of any region, growing "
          "faster than forecast in November and December on the strength of Clothing and Sports "
          "promotions targeted at warmer-weather markets. Despite this Q4 momentum, the South "
          "region's full-year revenue of $35,470,111.47 remained $410,388 below that of the "
          "Central region ($35,679,253.01). The reasons for West outperforming South on a "
          "full-year basis are explored in depth in the Regional Performance Analysis document, "
          "which attributes the gap primarily to customer base composition and Electronics "
          "category affinity differences.", e["Body"]),
    ]
    reg_q4_rows = [
        ["Region", "Est. Q4 Revenue", "% of Q4 Total", "FY 2024 Total", "Key Q4 Driver"],
        ["West", "$15,329,038", "29.6%", "$37,880,499.39", "Electronics (Laptop, Phone)"],
        ["East", "$14,217,246", "27.4%", "$36,314,020.57", "Home (Bedding, Kitchen)"],
        ["Central", "$11,011,921", "21.2%", "$35,679,253.01", "Electronics, Home mixed"],
        ["South", "$7,523,419", "14.5%", "$35,470,111.47", "Clothing, Sports"],
        ["North", "$3,764,781", "7.3%", "$30,251,293.72", "Sports, Home"],
        ["Total", "$58.9M", "100%", "$175,595,178.16", "—"],
    ]
    story += [
        _table(reg_q4_rows, col_widths=[70, 100, 80, 110, 190]),
        P("Q4 regional figures are estimates. FY 2024 totals from sales_transactions.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("Key Observations and Recommendations", e["SectionHead"]),
        P("Three observations stand out from Q4 2024 performance. First, the Electronics "
          "category continues to expand its revenue share during peak periods, reaching 52% "
          "of Q4 revenue against a full-year average of 51.8%. This reinforces Electronics "
          "as the primary demand lever for NexusIQ and warrants proportionally larger "
          "inventory investments going into Q4 2025.", e["Body"]),
        P("Second, the supply chain was not positioned to fully capitalize on demand strength. "
          "The 72 below-reorder SKUs identified at year-end represent lost sales opportunity; "
          "initial estimates by the operations team suggest approximately $2.1M in demand "
          "went unfulfilled in December due to stockout conditions, primarily in Tablet "
          "and Laptop SKUs. The Inventory Reorder SOP has been updated with a 1.3x seasonal "
          "multiplier to mitigate this in future Q4 cycles.", e["Body"]),
        P("Third, the South region's Q4 acceleration suggests there is untapped demand in "
          "that market. A targeted Q1 2025 campaign focused on Electronics cross-sell to "
          "the South region's Clothing and Sports customer base is being evaluated by the "
          "category management team.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 5: Q3 2024 Revenue Performance Memo ─────────────────────────────

def build_q3_revenue_memo(out_path: Path) -> None:
    doc = _make_doc(out_path, "Q3 2024 Revenue Performance Memo — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Q3 2024 Revenue Performance Memo", e["DocTitle"]),
        P("Internal Analysis | Prepared by: Finance & Analytics Team | Date: October 7, 2024", e["Subtitle"]),
        P("Period: July 1 – September 30, 2024 | Distribution: Leadership Team, Category Managers | "
          "Classification: Confidential", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("Executive Summary", e["SectionHead"]),
        P("Q3 2024 revenue reached $43,322,149.57, a 2.7% increase over Q2 2024 "
          "($42,184,731.08) and a 13.3% increase over Q1 2024 ($38,241,892.14). "
          "NexusIQ is on track to achieve the full-year $175M revenue target: cumulative "
          "nine-month revenue through September 30 stands at $123,748,772.79, or 70.5% of "
          "full-year target, consistent with the expected back-weighted revenue profile given "
          "Q4 seasonal dynamics.", e["Body"]),
        P("Q3 was characterized by back-to-school demand in Electronics and a solid Sports "
          "and Fitness performance through summer. The August-September back-to-school period "
          "drove a notable 18% spike in Laptop sales and a 14% spike in Tablet sales versus "
          "Q2 levels. Home category remained steady, benefiting from continued strength in "
          "Bedding and Kitchen subcategories driven by new household formation purchases.", e["Body"]),
    ]

    story += [
        P("Q3 Monthly Revenue Detail", e["SectionHead"]),
    ]
    monthly_rows = [
        ["Month", "Revenue", "vs Prior Month", "Category Highlight", "Notable Event"],
        ["July 2024", "$13,821,486.22", "+1.4% vs Jun", "Sports peak (summer)", "Summer sale promotion week 2"],
        ["August 2024", "$14,472,319.48", "+4.7% vs Jul", "Electronics (back-to-school)", "Back-to-school campaign launched Aug 1"],
        ["September 2024", "$15,028,343.87", "+3.8% vs Aug", "Electronics, Home", "Labor Day weekend sale event"],
        ["Q3 Total", "$43,322,149.57", "+2.7% vs Q2", "Electronics led", "Cumulative YTD: $123,748,772.79"],
    ]
    story += [
        _table(monthly_rows, col_widths=[90, 100, 100, 145, 110]),
        _sp(),
    ]

    story += [
        P("Category Performance", e["SectionHead"]),
        P("Electronics contributed an estimated $19,482,967 in Q3, representing 45.0% of "
          "quarterly revenue. While Electronics' quarterly share was lower than the full-year "
          "average of 51.8%, this reflects Q3's more balanced category mix driven by summer "
          "Sports demand. The back-to-school acceleration in August and September positions "
          "Electronics well for continued growth into Q4.", e["Body"]),
        P("Sports and Fitness performed above Q4 2025 planning assumptions in Q3, with "
          "outdoor equipment and athletic apparel driving strong performance through July "
          "and August. The Sports category typically peaks in Q2 and Q3; Q4 seasonality "
          "is expected to moderate Sports contribution as documented in the 2024 Annual "
          "Business Review's seasonal demand analysis.", e["Body"]),
        P("Home category held steady through Q3 at approximately $8,664,430. No major "
          "Home promotions ran in Q3; the category benefits from consistent demand for "
          "everyday home goods without the pronounced seasonality seen in Electronics and "
          "Sports. Clothing ran at reduced levels in Q3 summer months; the category typically "
          "accelerates in October through December as winter apparel demand grows.", e["Body"]),
    ]
    cat_rows = [
        ["Category", "Est. Q3 Revenue", "% of Q3", "Est. Q2 Revenue", "QoQ Growth", "YTD through Q3"],
        ["Electronics", "$19,482,967", "45.0%", "$18,332,558", "+6.3%", "$64,027,795"],
        ["Home", "$8,664,430", "20.0%", "$8,436,946", "+2.7%", "$29,470,799"],
        ["Sports", "$7,597,376", "17.5%", "$7,805,575", "-2.7%", "$20,293,445"],
        ["Clothing", "$5,198,658", "12.0%", "$4,640,320", "+12.0%", "$7,066,388"],
        ["Food", "$2,378,719", "5.5%", "$2,969,332", "-19.9%", "$2,890,343"],
        ["Total", "$43,322,150", "100%", "$42,184,731", "+2.7%", "$123,748,770"],
    ]
    story += [
        _table(cat_rows, col_widths=[90, 100, 65, 100, 85, 105]),
        P("Q3 and Q2 category figures are estimates. YTD calculated from Q1+Q2+Q3 totals.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("Q4 Outlook and Preparation", e["SectionHead"]),
        P("Q4 2024 forecast stands at $48.2M based on historical seasonality and current "
          "demand signals. Electronics is expected to lead Q4 as holiday gift demand drives "
          "Laptop, Phone, and Tablet purchases. The supply chain team has been briefed on "
          "the need to pre-position Electronics inventory above standard reorder thresholds "
          "ahead of the November demand peak.", e["Body"]),
        P("Three risks are identified for Q4. First, Tablet supply — the TechSource Global "
          "vendor is on performance notice for delivery rates below 95% per the Inventory "
          "Reorder SOP vendor scorecard, and delivery reliability must improve before the "
          "November peak. Second, return volume is expected to be elevated in Q4 as gift "
          "recipients return items; the customer operations team should pre-staff the returns "
          "function per the Returns and Refunds Policy Section 4 guidance on Q4 processing "
          "timelines. Third, the West region faces the most concentrated inventory risk given "
          "its above-average Electronics mix.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 6: Electronics Category Deep-Dive ───────────────────────────────

def build_electronics_deep_dive(out_path: Path) -> None:
    doc = _make_doc(out_path, "Electronics Category Deep-Dive — NexusIQ FY 2024")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Electronics Category Deep-Dive Analysis", e["DocTitle"]),
        P("FY 2024 | Prepared by: Category Analytics Team | Date: January 15, 2025", e["Subtitle"]),
        P("Category: Electronics | Total Revenue: $90,958,302.29 | Share of Total: 51.8% | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Category Overview", e["SectionHead"]),
        P("Electronics is NexusIQ's largest revenue category by a significant margin. FY 2024 "
          "Electronics revenue of $90,958,302.29 represents 51.8% of total company revenue "
          "of $175,595,178.16 — a category concentration that has grown from 48.3% in FY 2022 "
          "and 50.1% in FY 2023. This growth trajectory reflects both strong underlying demand "
          "for consumer electronics and NexusIQ's deliberate expansion of its Electronics SKU "
          "catalog from 4 to 8 active product lines over the past 24 months.", e["Body"]),
        P("The Electronics product lineup consists of four core SKUs: Laptop, Phone, Tablet, "
          "and Headphones. Laptop is the highest-revenue individual product in the NexusIQ "
          "catalog. Phone ranks second. Together, Laptop and Phone account for approximately "
          "68% of Electronics category revenue and 35% of total company revenue — a "
          "concentration that creates both opportunity (scale-based supplier leverage) and "
          "risk (single-vendor dependency for key components).", e["Body"]),
    ]

    story += [
        P("2. Product Revenue Breakdown — FY 2024", e["SectionHead"]),
        P("Revenue within the Electronics category is distributed unevenly across the four "
          "product lines. Laptop and Phone together dominate, while Tablet has shown the "
          "fastest growth rate in the category. Headphones, though the lowest-revenue "
          "Electronics product, carries strong attachment rates as a bundle accessory with "
          "Laptop and Phone purchases — the Q4 2024 Laptop+Headphones bundle contributed "
          "meaningfully to Q4 category outperformance as noted in the Q4 Revenue Memo.", e["Body"]),
    ]
    prod_rows = [
        ["Product", "Est. FY Revenue", "% of Electronics", "Est. Units Sold", "Avg Transaction Value", "Return Count"],
        ["Laptop", "$33,273,695.91", "36.6%", "12,400 units", "$2,683.36", "302"],
        ["Phone", "$28,923,339.94", "31.8%", "19,200 units", "$1,506.42", "309"],
        ["Tablet", "$20,932,328.89", "23.0%", "14,800 units", "$1,414.35", "314"],
        ["Headphones", "$7,881,860.87", "8.7%", "21,600 units", "$364.90", "281"],
        ["Electronics Total", "$90,958,302.29", "100%", "68,000 units est.", "$1,337.62 avg", "1,206 total"],
    ]
    story += [
        _table(prod_rows, col_widths=[90, 110, 90, 90, 110, 80]),
        P("Product revenue estimates based on category total and historical revenue share percentages. "
          "Return counts from returns table.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("3. Quarterly Revenue Progression", e["SectionHead"]),
        P("Electronics revenue shows pronounced Q4 seasonality driven by holiday gift purchasing. "
          "Q4 2024 contributed $31,270,715.79 — 34.4% of the category's full-year revenue — "
          "making it the single highest-revenue quarter in Electronics history. The Q4/Q1 ratio "
          "of 1.74x reflects significantly stronger holiday demand relative to the post-holiday "
          "trough in Q1. This seasonality pattern directly informs the Inventory Reorder SOP's "
          "1.3x Q4 seasonal multiplier applied to Electronics reorder quantities.", e["Body"]),
    ]
    qtr_rows = [
        ["Quarter", "Electronics Revenue", "% of Full Year", "QoQ Growth", "Inventory Pressure", "Supply Status"],
        ["Q1 2024 (Jan-Mar)", "$15,471,721.35", "17.0%", "— (base)", "Low", "Normal"],
        ["Q2 2024 (Apr-Jun)", "$18,332,558.23", "20.1%", "+18.5%", "Moderate", "Normal"],
        ["Q3 2024 (Jul-Sep)", "$25,779,650.28", "28.3%", "+6.3%", "Moderate-High", "Watch"],
        ["Q4 2024 (Oct-Dec)", "$31,270,715.79", "34.4%", "+21.3%", "High", "Constrained"],
        ["FY 2024 Total", "$90,958,302.29", "100%", "+7.5% vs FY 2023", "—", "72 SKUs below reorder"],
    ]
    story += [
        _table(qtr_rows, col_widths=[100, 110, 80, 80, 90, 95]),
        _sp(),
    ]

    story += [
        P("4. Regional Electronics Performance", e["SectionHead"]),
        P("Electronics revenue distribution across regions is not proportional to customer "
          "count. The West region, despite having only 2,351 customers — the second-smallest "
          "regional customer base — generates the highest per-customer Electronics spend. "
          "West's customers average $6,487 in Electronics purchases versus a network average "
          "of $6,075. This premium affinity for Electronics is a key driver of the West "
          "region's overall revenue leadership as detailed in the Regional Performance "
          "Analysis document.", e["Body"]),
    ]
    reg_elec_rows = [
        ["Region", "Customers", "Est. Electronics Revenue", "% of Cat Revenue", "Electronics per Customer", "vs Network Avg"],
        ["West", "2,351", "$19,610,180.21", "21.5%", "$6,341.29 × 1.07x", "+4.4%"],
        ["East", "3,676", "$20,022,227.63", "22.0%", "$5,447.56 × 0.90x", "-10.4%"],
        ["Central", "4,599", "$18,657,375.75", "20.5%", "$4,057.92 × 0.67x", "-33.2%"],
        ["South", "2,330", "$18,383,055.43", "20.2%", "$7,889.30 × 1.30x", "+29.9%"],
        ["North", "2,023", "$14,337,286.59", "15.8%", "$7,088.40 × 1.17x", "+16.7%"],
        ["Total", "14,979", "$90,958,302.29", "100%", "$6,071.95", "—"],
    ]
    story += [
        _table(reg_elec_rows, col_widths=[65, 70, 120, 80, 120, 90]),
        P("Electronics revenue by region estimated using category proportions. Per-customer calculation uses total customer count per region.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("5. Returns and Quality Analysis", e["SectionHead"]),
        P("Electronics generated 1,206 returns in FY 2024, representing a 1.8% return rate "
          "on an estimated 68,000 units sold — below the NexusIQ network average return rate "
          "of 6.0% on a per-transaction basis. However, the absolute refund value impact is "
          "disproportionately large given Electronics' high average selling price. An estimated "
          "$1,613,458 in Electronics refunds were processed in FY 2024 based on the average "
          "Electronics return value.", e["Body"]),
        P("The Tablet quality issue identified in Q3 2024 — an accelerometer calibration defect "
          "in one specific model — accounted for 87 of the 314 Tablet returns. The defect was "
          "addressed through a supplier corrective action in September 2024, and Tablet return "
          "rates in Q4 were lower than Q3 despite higher overall sales volume, indicating the "
          "corrective action was effective. The quality team continues to monitor Headphones "
          "return rates, which at 281 for the year are tracking toward the upper bound of "
          "acceptable range given unit volume.", e["Body"]),
    ]

    story += [
        P("6. FY 2025 Category Outlook", e["SectionHead"]),
        P("Electronics is projected to grow 8-12% in FY 2025 based on new SKU introductions "
          "and continued market penetration in the South and East regions where Electronics "
          "per-customer spend is below the network average. Two initiatives are under evaluation: "
          "a trade-in program for Laptops and Phones that would increase upgrade cycle velocity, "
          "and an expanded Headphones lineup targeting the premium audio segment where current "
          "coverage is limited.", e["Body"]),
        P("The primary supply chain risk for FY 2025 is the TechSource Global vendor situation. "
          "TechSource supplies the majority of NexusIQ's Laptop and Tablet inventory, and its "
          "FY 2024 on-time delivery rate of 94.2% — below the 95% target — contributed to "
          "the Q4 2024 inventory constraints. A secondary vendor qualification process is "
          "underway; results are expected by March 2025 and will be reflected in the Supply "
          "Chain Risk Assessment annual update.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 7: Regional Performance Analysis ────────────────────────────────

def build_regional_analysis(out_path: Path) -> None:
    doc = _make_doc(out_path, "Regional Performance Analysis — NexusIQ FY 2024")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Regional Performance Analysis", e["DocTitle"]),
        P("FY 2024 Full-Year Review | Prepared by: Strategy & Analytics | Date: January 20, 2025", e["Subtitle"]),
        P("Scope: All five regions | Total Revenue: $175,595,178.16 | Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Full-Year Regional Revenue Summary", e["SectionHead"]),
        P("NexusIQ operates across five geographic regions, each served by 20 retail and "
          "distribution stores. The West region led FY 2024 revenue at $37,880,499.39 despite "
          "having the second-smallest customer count of 2,351. East followed at $36,314,020.57 "
          "with 3,676 customers. Central placed third at $35,679,253.01 with 4,599 customers — "
          "the largest customer base of any region. South came fourth at $35,470,111.47 with "
          "2,330 customers, and North trailed at $30,251,293.72 with 2,023 customers.", e["Body"]),
        P("The counter-intuitive relationship between customer count and revenue — where West "
          "generates more revenue than Central despite having 49% fewer customers — is the "
          "central theme of this analysis. The explanation lies in customer composition, "
          "category affinity, and average transaction value differences across regions.", e["Body"]),
    ]
    regional_summary_rows = [
        ["Region", "FY 2024 Revenue", "% of Total", "Customers", "Revenue per Customer", "Rank by Revenue"],
        ["West", "$37,880,499.39", "21.6%", "2,351", "$16,113.78", "1st"],
        ["East", "$36,314,020.57", "20.7%", "3,676", "$9,880.37", "2nd"],
        ["Central", "$35,679,253.01", "20.3%", "4,599", "$7,757.83", "3rd"],
        ["South", "$35,470,111.47", "20.2%", "2,330", "$15,224.51", "4th"],
        ["North", "$30,251,293.72", "17.2%", "2,023", "$14,955.51", "5th"],
        ["Total", "$175,595,178.16", "100%", "14,979", "$11,722.76 avg", "—"],
    ]
    story += [
        _table(regional_summary_rows, col_widths=[70, 110, 70, 80, 110, 105]),
        _sp(),
    ]

    story += [
        P("2. Why West Outperformed South in FY 2024", e["SectionHead"]),
        P("West and South have similar customer counts — 2,351 and 2,330 respectively — "
          "making them directly comparable for revenue-per-customer analysis. West generated "
          "$37,880,499.39 versus South's $35,470,111.47, a difference of $2,410,387.92 "
          "or 6.8%. This gap persisted across all four quarters and is structural rather "
          "than driven by any single promotion or event.", e["Body"]),
        P("The primary driver is category composition. West's customer base has significantly "
          "higher Electronics affinity: Electronics represents an estimated 51.7% of West "
          "revenue versus 51.8% at the network level, but West customers purchase higher-value "
          "Electronics SKUs. The average Electronics transaction value in West is $1,487 "
          "versus $1,263 in South. West customers index heavily toward Laptop purchases — "
          "the highest-ASP Electronics product — while South customers show a stronger "
          "relative mix of Phone and Tablet purchases at lower price points.", e["Body"]),
        P("A secondary driver is customer tenure. West customers have, on average, longer "
          "account history with NexusIQ, which correlates with higher lifetime spend and a "
          "demonstrated pattern of upgrade purchasing. West's cohort retention rate through "
          "FY 2024 was 74.2% at the 12-month mark versus South's 68.8%, a meaningful "
          "difference that compounds over multi-year customer relationships. The Customer "
          "Lifetime Value Study contains a detailed cohort analysis supporting this finding.", e["Body"]),
        P("South's lower per-customer revenue is partially offset by its Q4 2024 "
          "acceleration: the region showed faster-than-network-average growth in November "
          "and December, closing some of the per-customer gap with West. If South's Q4 "
          "momentum reflects a genuine shift in category mix toward higher-ASP Electronics, "
          "the gap between the two regions could narrow meaningfully over FY 2025.", e["Body"]),
    ]

    story += [
        P("3. West vs. South Comparative Analysis", e["SectionHead"]),
    ]
    comparison_rows = [
        ["Metric", "West Region", "South Region", "West Advantage", "Implication"],
        ["FY 2024 Revenue", "$37,880,499.39", "$35,470,111.47", "+$2,410,388", "West leads by 6.8%"],
        ["Customer Count", "2,351", "2,330", "+21 customers", "Negligible difference"],
        ["Revenue per Customer", "$16,113.78", "$15,224.51", "+$889.27 (+5.8%)", "West customers spend more per head"],
        ["Electronics Revenue Mix", "~52.0%", "~51.8%", "~Equal share", "ASP difference drives gap, not share"],
        ["Avg Electronics ASP", "$1,487", "$1,263", "+$224 (+17.7%)", "West buys higher-value SKUs"],
        ["12-Month Retention Rate", "74.2%", "68.8%", "+5.4 pts", "West retains customers better"],
        ["Laptop as % of Electronics", "~41%", "~34%", "+7 pts", "Laptop is highest-ASP SKU"],
        ["Q4 2024 Growth vs Q3", "+21.3%", "+24.1%", "South faster", "South closing gap — watch in FY25"],
    ]
    story += [
        _table(comparison_rows, col_widths=[140, 100, 100, 100, 105]),
        P("Revenue mix estimates based on regional customer profiles and transaction analysis. "
          "Retention rates from cohort analysis in Customer Lifetime Value Study.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("4. Central Region Analysis", e["SectionHead"]),
        P("Central is NexusIQ's largest customer region at 4,599 accounts but ranks third "
          "in revenue at $35,679,253.01. The revenue-per-customer figure of $7,757.83 is "
          "the lowest of any region — 33.8% below the network average of $11,722.76. This "
          "gap is attributable to Central's customer demographic profile: a higher proportion "
          "of lower-frequency buyers with strong Food and Clothing category affinity relative "
          "to high-ASP Electronics. Central customers made an average of 6.7 purchases in "
          "FY 2024 versus 8.2 for West customers, and average transaction value of $1,158 "
          "versus $1,964 in West.", e["Body"]),
        P("Central represents the most significant untapped revenue opportunity in the "
          "network. A strategy of migrating Central customers from their current category "
          "profile toward higher-ASP Electronics through targeted recommendations could "
          "meaningfully increase per-customer revenue. The Electronics Deep-Dive analysis "
          "shows that Central's Electronics revenue per customer ($4,058) is the lowest "
          "of all five regions, suggesting substantial room for category penetration growth.", e["Body"]),
    ]

    story += [
        P("5. North Region Considerations", e["SectionHead"]),
        P("North trails all other regions at $30,251,293.72 with 2,023 customers. The "
          "revenue gap versus West ($7,629,205.67) is driven by both customer count "
          "and per-customer spend differences. North customers have the second-highest "
          "revenue per customer at $14,955.51 — indicating engaged, high-value customers "
          "— but the region lacks the customer volume to close the absolute revenue gap. "
          "Customer acquisition in the North region is identified as a growth priority "
          "in the Supply Chain Risk Assessment and the FY 2025 planning documents.", e["Body"]),
    ]

    story += [
        P("6. Category Revenue by Region", e["SectionHead"]),
    ]
    cat_region_rows = [
        ["Category", "West", "East", "Central", "South", "North", "Total"],
        ["Electronics", "$19,599,009", "$20,010,826", "$18,646,750", "$18,372,588", "$14,329,129", "$90,958,302"],
        ["Home", "$8,573,713", "$7,701,125", "$7,949,803", "$8,240,436", "$8,411,930", "$40,877,007"],
        ["Sports", "$5,952,498", "$5,988,062", "$5,905,980", "$5,669,841", "$3,961,705", "$27,478,086"],
        ["Clothing", "$2,366,427", "$2,405,282", "$2,614,454", "$2,407,252", "$1,938,350", "$11,731,765"],
        ["Food", "$1,377,681", "$1,197,324", "$552,640", "$769,528", "$601,020", "$4,498,193"],
        ["Total", "$37,880,499", "$36,314,021", "$35,679,253", "$35,470,112", "$30,251,292", "$175,595,177"],
    ]
    story += [
        _table(cat_region_rows, col_widths=[85, 80, 80, 80, 80, 80, 80], small=True),
        P("Revenue by region estimated using category total and proportional allocation. "
          "Figures rounded. Total from sales_transactions: $175,595,178.16.", e["Caption"]),
        _sp(),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 8: Payment Method Adoption Report ───────────────────────────────

def build_payment_method_report(out_path: Path) -> None:
    doc = _make_doc(out_path, "Payment Method Adoption Report — NexusIQ FY 2024")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Payment Method Adoption Report", e["DocTitle"]),
        P("FY 2024 Annual Review | Prepared by: Finance Operations | Date: January 22, 2025", e["Subtitle"]),
        P("Scope: All 100,000 transactions | Total Revenue: $175,595,178.16 | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Executive Summary", e["SectionHead"]),
        P("FY 2024 marked a significant shift in NexusIQ's payment method distribution. "
          "Digital wallet adoption — primarily Apple Pay and Google Pay — grew from 11.2% "
          "of transactions in Q1 2024 to 22.4% in Q4 2024, a near-doubling over the course "
          "of the year. This growth came at the expense of traditional credit card share, "
          "which declined from 49.1% in Q1 to 43.2% in Q4. Debit card share was relatively "
          "stable. Buy Now Pay Later (BNPL) held steady at 6-7% throughout the year.", e["Body"]),
        P("The digital wallet trend carries several strategic implications. Fraud and "
          "chargeback rates for digital wallet transactions are significantly lower than "
          "for card transactions — digital wallet fraud rate was 0.12% in FY 2024 versus "
          "0.81% for credit cards — generating approximately $218,000 in avoided fraud "
          "losses. Additionally, digital wallet checkout completion rates are 8.3 percentage "
          "points higher than credit card checkout, contributing to revenue capture "
          "that would otherwise be lost to cart abandonment.", e["Body"]),
    ]

    story += [
        P("2. Payment Method Distribution by Quarter", e["SectionHead"]),
        P("The table below shows payment method share by transaction count and the "
          "corresponding revenue share for each payment type. Digital wallet transactions "
          "skew slightly toward higher-value purchases, particularly in the Electronics "
          "category where Apple Pay usage is concentrated among Laptop and Phone buyers. "
          "BNPL shows the inverse pattern — higher adoption in lower-ASP categories "
          "like Food and Clothing where customers split purchases into installments.", e["Body"]),
    ]
    pm_rows = [
        ["Payment Method", "Q1 2024 Share", "Q2 2024 Share", "Q3 2024 Share", "Q4 2024 Share", "FY 2024 Avg"],
        ["Credit Card", "49.1%", "47.2%", "45.8%", "43.2%", "46.3%"],
        ["Debit Card", "29.8%", "28.9%", "27.6%", "27.1%", "28.4%"],
        ["Digital Wallet (Apple/Google Pay)", "11.2%", "14.1%", "17.3%", "22.4%", "16.3%"],
        ["Buy Now Pay Later (BNPL)", "6.9%", "6.8%", "6.7%", "5.9%", "6.6%"],
        ["Bank Transfer / ACH", "3.0%", "3.0%", "2.6%", "1.4%", "2.5%"],
        ["Total", "100%", "100%", "100%", "100%", "100%"],
    ]
    story += [
        _table(pm_rows, col_widths=[160, 70, 70, 70, 70, 75]),
        P("Share measured by transaction count across 100,000 FY 2024 transactions.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("3. Digital Wallet Adoption Deep-Dive", e["SectionHead"]),
        P("The 22.4% digital wallet share in Q4 2024 is the highest recorded for any quarter "
          "in NexusIQ's history. Three factors drove the acceleration. First, the NexusIQ "
          "mobile app introduced Apple Pay and Google Pay as one-tap checkout options in "
          "March 2024, reducing friction in the mobile purchase flow. By Q4, mobile-app "
          "purchases accounted for 38% of all transactions, and among mobile transactions, "
          "digital wallet was the dominant payment method at 47%.", e["Body"]),
        P("Second, NexusIQ ran a 2% rebate promotion for digital wallet payments during "
          "October and November 2024, which drove adoption among first-time digital wallet "
          "users. Post-promotion analysis shows that 71% of customers who first used "
          "a digital wallet during the promotion continued using it for subsequent "
          "purchases in December, indicating strong habit formation.", e["Body"]),
        P("Third, generational shift plays a role. The 18-34 age cohort — which represents "
          "an estimated 34% of NexusIQ's customer base by transaction count — uses digital "
          "wallets at a 41% rate versus 8% for customers over 55. As the customer base "
          "continues to skew younger in new customer acquisition, digital wallet adoption "
          "is expected to continue growing organically.", e["Body"]),
    ]

    story += [
        P("4. Fraud and Chargeback Analysis by Payment Method", e["SectionHead"]),
        P("Payment method selection has a measurable impact on fraud rates and chargeback "
          "incidence. Digital wallets use tokenized payment credentials and biometric "
          "authentication, making them substantially harder to compromise than traditional "
          "card numbers. The data below reflects FY 2024 fraud and chargeback experience "
          "across NexusIQ's payment processing.", e["Body"]),
    ]
    fraud_rows = [
        ["Payment Method", "Transaction Volume", "Fraud Rate", "Chargeback Rate", "Est. Annual Loss", "Trend"],
        ["Credit Card", "46,300 txns", "0.81%", "0.43%", "$174,240", "Stable"],
        ["Debit Card", "28,400 txns", "0.34%", "0.18%", "$28,480", "Declining"],
        ["Digital Wallet", "16,300 txns", "0.12%", "0.06%", "$3,920", "Declining"],
        ["BNPL", "6,600 txns", "0.22%", "0.51% (disputes)", "$9,140", "Stable"],
        ["Bank Transfer", "2,500 txns", "0.08%", "0.04%", "$1,280", "Declining"],
        ["Total / Weighted Avg", "100,000 txns", "0.51% avg", "0.31% avg", "$217,060", "Improving"],
    ]
    story += [
        _table(fraud_rows, col_widths=[115, 90, 75, 85, 90, 70]),
        P("Fraud rates and losses estimated from payment processor reports. Digital wallet fraud avoidance "
          "versus credit card: ~$218K in FY 2024.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("5. Category Affinity by Payment Method", e["SectionHead"]),
        P("Payment method preference varies meaningfully by product category. Electronics "
          "buyers show the highest digital wallet adoption, driven by mobile-first purchasing "
          "behavior among the category's younger demographic. BNPL is most prevalent in "
          "Clothing and Home categories, where customers use installment financing to "
          "manage larger discretionary purchases. Food category transactions are overwhelmingly "
          "debit-card based, consistent with everyday grocery purchasing patterns.", e["Body"]),
    ]
    cat_pm_rows = [
        ["Category", "Top Payment Method", "Digital Wallet Share", "BNPL Share", "Credit Card Share"],
        ["Electronics", "Credit Card (40%)", "26.2%", "5.8%", "40.0%"],
        ["Home", "Credit Card (44%)", "14.1%", "9.2%", "44.1%"],
        ["Sports", "Credit Card (47%)", "12.8%", "7.4%", "47.0%"],
        ["Clothing", "Credit Card (46%)", "11.2%", "10.8%", "46.2%"],
        ["Food", "Debit Card (51%)", "5.4%", "2.1%", "31.4%"],
    ]
    story += [
        _table(cat_pm_rows, col_widths=[90, 130, 100, 80, 110]),
        _sp(),
    ]

    story += [
        P("6. FY 2025 Outlook", e["SectionHead"]),
        P("Digital wallet adoption is forecast to reach 28-32% of transactions in FY 2025 "
          "based on current trajectory. Finance Operations recommends maintaining the "
          "digital wallet checkout incentive program through at least Q2 2025, given the "
          "strong habit formation demonstrated in Q4 2024. The continued shift toward "
          "digital wallets is projected to reduce annual fraud losses by an additional "
          "$35,000-$55,000 per year as the payment mix tilts away from higher-fraud "
          "credit card transactions.", e["Body"]),
        P("BNPL risk monitoring will continue in FY 2025. While BNPL chargeback rates "
          "are within acceptable bounds, the BNPL provider has indicated potential pricing "
          "changes for merchants above certain volume thresholds. The Finance team is "
          "evaluating a secondary BNPL provider relationship as a negotiating leverage "
          "tool ahead of contract renewal discussions in Q2 2025.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 9: Weekly Operations Digest — Week 48 ───────────────────────────

def build_weekly_digest_week48(out_path: Path) -> None:
    doc = _make_doc(out_path, "Weekly Operations Digest — Week 48 — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Weekly Operations Digest", e["DocTitle"]),
        P("Week 48: November 25 – December 1, 2024 (Black Friday / Cyber Monday Week)", e["Subtitle"]),
        P("Prepared by: Operations Analytics | Distributed: Monday Dec 2, 2024 | "
          "Classification: Internal — Operations", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("Week Overview", e["SectionHead"]),
        P("Week 48 was the highest-revenue week in NexusIQ's operating history. Gross revenue "
          "of $7,218,440 represents a 151% increase over the prior week (Week 47: $2,874,320) "
          "and a 213% increase over the same week in 2023. The Black Friday promotional event "
          "on November 29 and Cyber Monday on December 2 (captured in the final hours of this "
          "reporting period) together drove approximately 62% of week revenue. The operations "
          "team executed the surge without a system outage, though two fulfillment centers "
          "experienced temporary processing delays on November 29 that were resolved within "
          "four hours.", e["Body"]),
        P("Electronics was the dominant category, accounting for 71% of week revenue versus "
          "its standard 51.8% annual average. Laptop and Phone promotions drove the "
          "majority of Electronics demand. Headphone bundle attach rate reached 34% of "
          "Laptop transactions — well above the 18% annual average — driven by the "
          "$349 Laptop+Headphones bundle promotion advertised in the Black Friday catalog.", e["Body"]),
    ]

    story += [
        P("Daily Revenue Summary — Week 48", e["SectionHead"]),
    ]
    daily_rows = [
        ["Date", "Day", "Gross Revenue", "Transaction Count", "Avg Transaction Value", "Highlight"],
        ["Nov 25, 2024", "Monday", "$748,210", "1,421", "$526.53", "Week-opening promotions live"],
        ["Nov 26, 2024", "Tuesday", "$612,340", "1,182", "$518.05", "Normal Tuesday volume"],
        ["Nov 27, 2024", "Wednesday", "$891,480", "1,688", "$528.13", "Pre-Thanksgiving electronics purchases"],
        ["Nov 28, 2024", "Thursday (Thanksgiving)", "$1,124,670", "2,109", "$533.27", "Thanksgiving deals — online only"],
        ["Nov 29, 2024", "Friday (Black Friday)", "$2,418,920", "4,632", "$522.25", "Black Friday — highest single-day ever"],
        ["Nov 30, 2024", "Saturday", "$884,320", "1,692", "$522.65", "Post-BF continued deals"],
        ["Dec 1, 2024", "Sunday", "$538,500", "1,041", "$517.29", "Cyber Monday preview — partial day"],
        ["Week 48 Total", "", "$7,218,440", "13,765", "$524.40 avg", "151% above prior week"],
    ]
    story += [
        _table(daily_rows, col_widths=[90, 90, 85, 100, 110, 170]),
        _sp(),
    ]

    story += [
        P("Category Performance", e["SectionHead"]),
    ]
    cat_rows = [
        ["Category", "Week 48 Revenue", "% of Week", "Vs Prior Week", "Vs Annual Avg Share", "Key SKU"],
        ["Electronics", "$5,125,092", "71.0%", "+218%", "+19.2 pts vs 51.8%", "Laptop (bundles)"],
        ["Home", "$793,028", "11.0%", "+87%", "-9.0 pts vs 20.0%", "Bedding, Kitchen"],
        ["Sports", "$433,106", "6.0%", "+41%", "-7.5 pts vs 13.5%", "Equipment"],
        ["Clothing", "$578,747", "8.0%", "+121%", "+1.3 pts vs 6.7%", "Jackets, Jeans"],
        ["Food", "$288,467", "4.0%", "+18%", "-1.5 pts vs 5.5%", "Packaged goods"],
        ["Total", "$7,218,440", "100%", "+151%", "—", "—"],
    ]
    story += [
        _table(cat_rows, col_widths=[90, 95, 65, 80, 115, 100]),
        _sp(),
    ]

    story += [
        P("Operations Issues and Inventory Alerts", e["SectionHead"]),
        P("Two fulfillment issues occurred during the week. The West region fulfillment "
          "center (W-FC) experienced a pick-and-pack queue backup on Black Friday morning, "
          "resulting in an estimated 847 orders delayed beyond the promised 2-hour processing "
          "window. The delay was resolved by 2:00 PM PT through temporary staff reallocation "
          "from the returns processing team. Customer communications were sent proactively "
          "to affected orders. The Central fulfillment center (C-FC) experienced a barcode "
          "scanner outage for approximately 90 minutes on November 27; no orders were lost "
          "but approximately 340 orders required manual entry during the outage.", e["Body"]),
        P("Inventory alerts as of end of Week 48: 31 Electronics SKUs are now at or below "
          "reorder point, up from 24 at the start of the week. Laptop inventory at stores "
          "W014, W007, C003, and C011 fell below safety stock thresholds during the week. "
          "Emergency replenishment orders were placed for those four stores. Per the "
          "Inventory Reorder SOP, high-priority stores receive daily replenishment review "
          "until stock is restored. Restock is expected December 18-21 for the most "
          "affected stores.", e["Body"]),
    ]
    alert_rows = [
        ["Alert Type", "Count", "Primary Category", "Action Taken", "Expected Resolution"],
        ["SKUs below reorder point", "31", "Electronics (22), Home (6), Other (3)", "Emergency POs placed", "Dec 18-21"],
        ["Stores at critical stock", "4 stores", "Electronics — Laptop, Tablet", "Emergency transfers", "Dec 18-19"],
        ["Pending return processing backlog", "412 items", "Electronics (248), Clothing (164)", "Extra staff scheduled", "Dec 5"],
        ["Fulfillment delay complaints", "184 tickets", "All categories", "Proactive comms sent", "Closed"],
    ]
    story += [
        _table(alert_rows, col_widths=[140, 60, 165, 130, 100]),
        P("As of December 1, 2024 end of day. Inventory data from inventory table snapshot.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("Customer Service Impact", e["SectionHead"]),
        P("Support case volume reached 94 new cases in Week 48 — the highest weekly count "
          "of FY 2024. The majority were related to order status inquiries during the Black "
          "Friday processing delay (41 cases) and delivery timeline questions (28 cases). "
          "Return initiation cases numbered 18, consistent with post-promotion return "
          "patterns. Support operated above staffed capacity on November 29; three Tier 2 "
          "escalations were required for cases involving customers who received incorrect "
          "items due to the fulfillment queue backup.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 10: Weekly Operations Digest — Week 12 ──────────────────────────

def build_weekly_digest_week12(out_path: Path) -> None:
    doc = _make_doc(out_path, "Weekly Operations Digest — Week 12 — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Weekly Operations Digest", e["DocTitle"]),
        P("Week 12: March 18 – March 24, 2024", e["Subtitle"]),
        P("Prepared by: Operations Analytics | Distributed: Monday Mar 25, 2024 | "
          "Classification: Internal — Operations", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("Week Overview", e["SectionHead"]),
        P("Week 12 was a representative operating week with no major promotional events or "
          "demand anomalies. Gross revenue of $3,142,840 is in line with the Q1 weekly "
          "average of approximately $2,942,453 ($38,241,892 / 13 weeks). The 6.8% premium "
          "over the Q1 average reflects a modest uptick in Home and Sports demand consistent "
          "with the early spring buying pattern typically observed in mid-March as customers "
          "begin home improvement and outdoor fitness purchasing.", e["Body"]),
        P("Operations ran smoothly across all five regions. No fulfillment issues were "
          "reported. Return volume was within normal range at 112 returns for the week, "
          "representing a 5.8% return rate on 1,926 transactions — slightly above the "
          "FY 2024 average of 6.0% but within the normal operational range. Customer "
          "support case volume was 38 new cases — a standard weekly load for the Tier 1 "
          "team.", e["Body"]),
    ]

    story += [
        P("Daily Revenue Summary — Week 12", e["SectionHead"]),
    ]
    daily_rows = [
        ["Date", "Day", "Gross Revenue", "Transactions", "Avg Value", "Notable Activity"],
        ["Mar 18, 2024", "Monday", "$371,284", "714", "$519.87", "Standard Monday — Home category leads"],
        ["Mar 19, 2024", "Tuesday", "$354,118", "683", "$518.48", "Normal volume"],
        ["Mar 20, 2024", "Wednesday", "$482,844", "928", "$520.31", "Mid-week Sports promotion — email send"],
        ["Mar 21, 2024", "Thursday", "$558,280", "1,074", "$519.79", "Spring Sports campaign Day 2"],
        ["Mar 22, 2024", "Friday", "$693,416", "1,330", "$521.37", "Friday lift — Electronics"],
        ["Mar 23, 2024", "Saturday", "$512,018", "983", "$520.87", "Weekend home shopping"],
        ["Mar 24, 2024", "Sunday", "$170,880", "328", "$521.00", "Normal Sunday trough"],
        ["Week 12 Total", "", "$3,142,840", "6,040", "$520.34 avg", "+6.8% vs Q1 weekly avg"],
    ]
    story += [
        _table(daily_rows, col_widths=[90, 85, 85, 85, 80, 175]),
        _sp(),
    ]

    story += [
        P("Category Performance", e["SectionHead"]),
        P("Electronics maintained its leading position at 51.2% of week revenue, in line "
          "with the full-year average. The Home category showed early spring seasonal strength "
          "at 22.4%, slightly above its annual 20.2% share, driven by Bedding and Decor "
          "purchases. The Sports and Fitness category benefited from a targeted email "
          "campaign sent Wednesday March 20 promoting spring Equipment and Footwear lines. "
          "Clothing and Food performed at seasonal norms.", e["Body"]),
    ]
    cat_rows = [
        ["Category", "Week 12 Revenue", "% of Week", "Vs FY Avg Share", "Week's Best SKU"],
        ["Electronics", "$1,609,134", "51.2%", "Approx FY average", "Phone"],
        ["Home", "$703,997", "22.4%", "+2.2 pts — spring lift", "Bedding"],
        ["Sports", "$408,569", "13.0%", "Approx FY average", "Equipment"],
        ["Clothing", "$282,856", "9.0%", "+2.3 pts — spring apparel", "Jackets"],
        ["Food", "$138,284", "4.4%", "Approx FY average", "Snacks"],
        ["Total", "$3,142,840", "100%", "—", "—"],
    ]
    story += [
        _table(cat_rows, col_widths=[90, 100, 80, 160, 115]),
        _sp(),
    ]

    story += [
        P("Inventory and Supply Chain Status", e["SectionHead"]),
        P("Inventory positions were healthy across the network in Week 12. No SKUs reached "
          "reorder alert status during the week. The Q1 inventory review conducted in "
          "February 2024 resulted in reorder quantities being recalibrated after the "
          "post-holiday Q1 demand trough. All five regions were operating within 20% "
          "above their reorder thresholds — a comfortable buffer heading into the "
          "spring Sports and Home demand season.", e["Body"]),
        P("The TechSource Global Electronics supply agreement was renegotiated in Week 11 "
          "(March 11-17), resulting in a 4.2% reduction in Laptop unit cost and an extended "
          "payment terms arrangement (net-45 versus the prior net-30). This negotiation "
          "was facilitated by the category team's analysis of TechSource's on-time delivery "
          "performance in Q4 2023 and Q1 2024. The cost reduction is expected to contribute "
          "approximately $1.1M in improved gross margin on an annualized basis.", e["Body"]),
    ]

    story += [
        P("Return Processing Summary", e["SectionHead"]),
        P("The 112 returns processed in Week 12 were handled within normal SLA windows. "
          "Status breakdown: 24 refunded (21.4%), 22 approved pending refund (19.6%), "
          "23 pending inspection (20.5%), 21 received (18.8%), and 22 rejected (19.6%). "
          "The rejection rate of 19.6% is below the FY 2024 average rejection rate of "
          "20.7%, consistent with mid-year return quality improving as customers become "
          "more familiar with return eligibility criteria from the updated Returns and "
          "Refunds Policy introduced in January 2024.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 11: Seasonal Demand Incident Report ────────────────────────────

def build_seasonal_demand_incident(out_path: Path) -> None:
    doc = _make_doc(out_path, "Seasonal Demand Incident Report Q4 2024 — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Seasonal Demand Incident Report", e["DocTitle"]),
        P("Q4 2024 Electronics Demand Surge | Incident Reference: OPS-2024-Q4-001 | "
          "Date: December 15, 2024", e["Subtitle"]),
        P("Prepared by: Supply Chain Operations | Reviewed by: VP Operations | "
          "Classification: Internal — Operations", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Incident Summary", e["SectionHead"]),
        P("Beginning in the week of November 18, 2024, Electronics demand at NexusIQ stores "
          "across all five regions exceeded the Q4 demand forecast by a widening margin. By "
          "Week 48 (Black Friday week), Electronics daily transaction rates were 14% above "
          "the Q4 plan prepared in September 2024. The excess demand exhausted available "
          "safety stock in Electronics across 26 high-priority stores and triggered 23 "
          "emergency replenishment orders between November 22 and December 5, 2024.", e["Body"]),
        P("This incident is classified as an Unforecasted Demand Surge — Category 2 (Supply "
          "Constrained). Category 2 means demand exceeded supply for a meaningful duration "
          "but did not result in a total stockout across the network. Estimated lost sales "
          "due to stockout conditions in Laptop and Tablet SKUs are approximately $2.1M, "
          "based on the demand signal observed at stores that did maintain sufficient stock. "
          "No customer data breaches, safety issues, or regulatory matters were involved.", e["Body"]),
    ]

    story += [
        P("2. Timeline of Events", e["SectionHead"]),
    ]
    timeline_rows = [
        ["Date", "Event", "Scope", "Action Taken"],
        ["Sep 20, 2024", "Q4 demand forecast finalized at $48.2M", "Planning", "Inventory positions set per forecast"],
        ["Nov 1, 2024", "October actuals: $15.82M — 1.2% above Q4 monthly target", "Monitoring", "No action — within normal variance"],
        ["Nov 15, 2024", "Week 46 Electronics sales 8% above weekly plan", "Early signal", "Watch status set; no order change"],
        ["Nov 18, 2024", "Electronics velocity now 11% above plan — trending to exceed forecast", "Alert Level 1", "Category buyer alerted; backup vendor contacted"],
        ["Nov 22, 2024", "First 4 emergency replenishment orders placed", "Alert Level 2", "Emergency orders: W014, W007, C003, C011"],
        ["Nov 25–29, 2024", "Black Friday week: Electronics revenue 38% above sub-plan for the week", "Incident Active", "19 additional emergency orders placed"],
        ["Dec 1, 2024", "31 SKUs below reorder point; 4 stores at critical stock", "Incident Active", "Daily ops review initiated per Inventory Reorder SOP Section 5"],
        ["Dec 5, 2024", "Emergency replenishments begin arriving at high-priority stores", "Recovering", "Stock positions improving at W014, W007"],
        ["Dec 15, 2024", "Incident report filed; 72 SKUs remain below reorder point network-wide", "Monitoring", "Restock expected Dec 18-28 for all affected stores"],
    ]
    story += [
        _table(timeline_rows, col_widths=[90, 185, 90, 170], small=True),
        _sp(),
    ]

    story += [
        P("3. Root Cause Analysis", e["SectionHead"]),
        P("Three contributing causes were identified through this investigation. The primary "
          "cause was forecast methodology: the Q4 demand forecast used a two-year historical "
          "average that did not fully weight the accelerating growth trajectory NexusIQ "
          "experienced in H2 2024. A forecast based purely on linear extrapolation of the "
          "Q1-Q3 2024 trend would have produced a Q4 forecast of $52.8M — $4.6M higher "
          "than the actual $48.2M plan — and would have prompted larger inventory positions. "
          "The forecasting model is being revised for FY 2025 planning.", e["Body"]),
        P("The secondary cause was the Black Friday promotional design. The Laptop+Headphones "
          "bundle offered at $349 in the Black Friday catalog generated substantially higher "
          "attach rates than modeled. The bundle was designed by the category team without "
          "a formal demand elasticity analysis; the 34% Headphones attach rate observed "
          "during the week was approximately twice the planning assumption of 17%. This "
          "incremental bundle demand consumed Laptop and Headphones inventory faster than "
          "the base replenishment cycle supported.", e["Body"]),
        P("The tertiary cause was vendor lead time. The primary Electronics vendor, "
          "TechSource Global, had an on-time delivery rate of 94.2% in FY 2024 per the "
          "Inventory Reorder SOP vendor scorecard — below the 95% target. When emergency "
          "orders were placed in late November, TechSource's production queue was already "
          "at capacity servicing other retail customers' holiday orders, resulting in "
          "longer-than-standard lead times for the emergency replenishments.", e["Body"]),
    ]

    story += [
        P("4. Impact Assessment", e["SectionHead"]),
    ]
    impact_rows = [
        ["Impact Category", "Magnitude", "Affected Scope", "Financial Estimate"],
        ["Lost Laptop sales (stockout)", "~1,400 units unavailable", "W014, W007, C003, C011 + 4 others", "~$1,480,000"],
        ["Lost Tablet sales (stockout)", "~840 units unavailable", "8 stores across West and Central", "~$620,000"],
        ["Emergency freight premium", "23 emergency orders", "Network-wide", "~$87,400"],
        ["Customer satisfaction impact", "184 complaint tickets filed", "Primarily West and Central", "Qualitative — churn risk"],
        ["Support cost (extra staffing)", "Est. 420 additional labor-hours", "Customer Operations", "~$14,700"],
        ["Total estimated incident cost", "", "", "~$2,202,100"],
    ]
    story += [
        _table(impact_rows, col_widths=[145, 130, 145, 115]),
        P("Financial estimates based on average transaction values and standard labor rates.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("5. Corrective Actions", e["SectionHead"]),
        P("Four corrective actions are in progress following this incident. First, the "
          "FY 2025 Q4 demand forecast will use a weighted model that gives 60% weight to "
          "the most recent four quarters and 40% to the two-year average, rather than an "
          "equal weighting. This change is expected to produce forecasts that better track "
          "current demand trajectory. Second, all major promotional bundles must pass a "
          "demand elasticity review before catalog publication; the category team will "
          "maintain a promotional demand model updated with post-event actuals.", e["Body"]),
        P("Third, the Inventory Reorder SOP has been updated (Version 2.1, effective "
          "March 1, 2024) to apply a 1.3x seasonal multiplier to Electronics and Home "
          "category reorder quantities for the October-December period. This creates a "
          "larger pre-season safety buffer. Fourth, a secondary Electronics vendor "
          "qualification process is underway to reduce dependency on TechSource Global "
          "for emergency replenishment capacity. Vendor qualification is expected to "
          "complete by March 2025 per the Supply Chain Risk Assessment timeline.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 12: Inventory Shortage Root Cause Analysis ──────────────────────

def build_inventory_shortage_rca(out_path: Path) -> None:
    doc = _make_doc(out_path, "Inventory Shortage Root Cause Analysis — NexusIQ Nov 2024")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Inventory Shortage Root Cause Analysis", e["DocTitle"]),
        P("November 2024 Electronics Stockout Post-Mortem | Reference: OPS-RCA-2024-011", e["Subtitle"]),
        P("Prepared by: Supply Chain Analytics | Date: December 10, 2024 | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Background", e["SectionHead"]),
        P("This root cause analysis examines the inventory shortage that developed across "
          "NexusIQ's Electronics category during November 2024. The shortage was first "
          "identified when routine inventory monitoring flagged 31 Electronics SKUs below "
          "reorder point on December 1, 2024 — up from 12 on November 1. By December 15, "
          "the network-wide below-reorder count had grown to 72 SKUs across all categories, "
          "with Electronics accounting for 39 of those positions.", e["Body"]),
        P("This analysis should be read in conjunction with the Seasonal Demand Incident "
          "Report (OPS-2024-Q4-001), which covers the demand-side events. This document "
          "focuses specifically on the supply chain process failures and the inventory "
          "management decisions that allowed shortage conditions to develop.", e["Body"]),
    ]

    story += [
        P("2. Shortage Scope by Product", e["SectionHead"]),
        P("The shortage was concentrated in Laptop and Tablet SKUs, consistent with those "
          "products' higher velocity and longer vendor lead times. Phone shortages developed "
          "later in November as the initial Laptop demand drew customers toward Phone as "
          "an alternative gift purchase, accelerating Phone depletion unexpectedly.", e["Body"]),
    ]
    shortage_rows = [
        ["Product", "SKUs Affected", "Stores Below Safety Stock", "Stockout Days (est.)", "Units Short (est.)", "Revenue Impact (est.)"],
        ["Laptop", "8 SKU variants", "16 stores", "4.2 days avg", "1,420 units", "~$1,480,000"],
        ["Tablet", "6 SKU variants", "11 stores", "3.1 days avg", "840 units", "~$620,000"],
        ["Phone", "5 SKU variants", "8 stores", "1.8 days avg", "380 units", "~$340,000"],
        ["Headphones", "3 SKU variants", "6 stores", "1.2 days avg", "290 units", "~$87,000"],
        ["Total Electronics", "22 SKU variants", "26+ unique stores", "2.6 days avg", "2,930 units", "~$2,527,000"],
    ]
    story += [
        _table(shortage_rows, col_widths=[80, 80, 100, 100, 90, 105]),
        P("Estimates based on demand signal analysis at comparable stores that maintained stock. "
          "Stockout days measured from first reported zero-inventory date to emergency restock arrival.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("3. Root Cause: Systematic Reorder Point Underestimation", e["SectionHead"]),
        P("The primary root cause was that Electronics reorder points were calibrated on "
          "FY 2023 demand data without adjustment for FY 2024 demand growth. Electronics "
          "unit velocity grew 18.3% year-over-year from FY 2023 to FY 2024, driven by "
          "expanded customer base and improved Electronics category conversion rates. "
          "However, the reorder point formula in the inventory management system used "
          "a rolling 12-month average that at the time of Q4 2024 planning (September 2024) "
          "still included the lower-demand months of Q4 2023 and Q1 2024.", e["Body"]),
        P("A reorder point calculation using only the most recent 6 months (April-September "
          "2024) would have set the Laptop reorder point at 1,180 units versus the actual "
          "970 units — a 21.6% increase. At the actual Q4 Laptop velocity, the higher "
          "reorder point would have triggered purchase orders 8.4 days earlier in the cycle, "
          "providing adequate buffer for the Black Friday demand spike.", e["Body"]),
    ]

    story += [
        P("4. Contributing Factor: Vendor Delivery Variance", e["SectionHead"]),
        P("TechSource Global's 94.2% on-time delivery rate in FY 2024 means that "
          "approximately 5.8% of Electronics orders arrived later than the contracted "
          "lead time. During a normal operating period, this variance is absorbed by "
          "safety stock without customer impact. During Q4's high-demand window, the same "
          "absolute delivery variance had significantly larger consequences because there "
          "was no safety stock buffer remaining to absorb delays.", e["Body"]),
        P("Specifically, two TechSource shipments scheduled to arrive November 20-22 "
          "(before Black Friday) arrived November 27-28 (during Black Friday). The "
          "combined late inventory of 847 Laptop and Tablet units arrived after the demand "
          "peak had already drawn down store stock to critical levels. Had those shipments "
          "arrived on schedule, the shortage at the four highest-impact stores would likely "
          "have been prevented.", e["Body"]),
    ]

    story += [
        P("5. Corrective Actions and Implementation Status", e["SectionHead"]),
    ]
    action_rows = [
        ["Corrective Action", "Owner", "Target Date", "Status", "Expected Impact"],
        ["Update reorder formula to 6-month rolling avg for high-velocity SKUs", "Supply Chain Analytics", "Jan 15, 2025", "In Progress", "Earlier reorder triggers; reduces stockout risk by est. 60%"],
        ["Add 1.3x seasonal multiplier to Electronics Q4 reorder quantities (in SOP v2.1)", "Category Ops", "Completed Mar 2024", "Complete", "Larger Q4 safety buffer"],
        ["Qualify secondary Electronics vendor; target 15% share", "Procurement", "Mar 31, 2025", "In Progress", "Reduces single-vendor dependency"],
        ["Set TechSource on 90-day performance watch; escalate if below 95% on-time", "Procurement", "Jan 1, 2025", "Active", "Pressure vendor to improve delivery reliability"],
        ["Implement promotional demand review for bundles", "Category Management", "Feb 1, 2025", "Planned", "Prevents bundle-driven demand surprise"],
        ["Add automated 30-day Q4 advance order trigger for top 20 Electronics SKUs", "Systems", "Q2 2025", "Planned", "Pre-positions stock before demand materializes"],
    ]
    story += [
        _table(action_rows, col_widths=[145, 95, 75, 70, 150], small=True),
        _sp(),
    ]

    story += [
        P("6. Lessons Learned", e["SectionHead"]),
        P("This shortage demonstrated that static reorder parameters calibrated annually "
          "cannot keep pace with a rapidly growing business. NexusIQ's Electronics category "
          "grew faster than any prior planning cycle anticipated, and the inventory system's "
          "backward-looking calibration created a structural lag. The corrective actions "
          "above address the immediate process gaps, but the deeper lesson is that inventory "
          "parameters must be reviewed on a rolling quarterly basis — not just at annual "
          "planning — for high-velocity, high-ASP categories like Electronics.", e["Body"]),
        P("A secondary lesson is that promotional planning and supply chain planning must "
          "be connected earlier in the promotional calendar. The Black Friday Laptop bundle "
          "was finalized in marketing in late October without a supply chain impact assessment; "
          "future promotions of this scale will require supply chain sign-off no later than "
          "six weeks before the promotional start date.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 13: 2024 Annual Business Review ─────────────────────────────────

def build_annual_business_review(out_path: Path) -> None:
    doc = _make_doc(out_path, "2024 Annual Business Review — NexusIQ Corporation")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — 2024 Annual Business Review", e["DocTitle"]),
        P("Executive Summary | FY 2024 Full-Year Performance | Date: January 28, 2025", e["Subtitle"]),
        P("Distribution: Board of Directors, Executive Team | Classification: Highly Confidential", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. FY 2024 at a Glance", e["SectionHead"]),
        P("NexusIQ achieved $175,595,178.16 in total revenue for FY 2024, its highest annual "
          "revenue on record. The result was driven by strong Electronics performance, "
          "disciplined customer acquisition across all five geographic regions, and the "
          "continued maturation of the NexusIQ digital platform including the mobile app "
          "launch in Q1 2024. Total transactions for the year numbered 100,000, with 14,979 "
          "unique customers making purchases at an average spend per customer of $11,722.76.", e["Body"]),
        P("The year's performance was back-weighted as expected: Q4 2024 alone contributed "
          "$58.9M (33.5% of full-year revenue) versus Q1's $38,241,892.14. This "
          "seasonality is inherent to the Electronics-heavy category mix and is expected to "
          "persist in FY 2025. The challenge going into FY 2025 is translating the Q4 2024 "
          "demand strength into sustained customer engagement throughout the year.", e["Body"]),
    ]
    kpi_rows = [
        ["Key Performance Indicator", "FY 2024 Actual", "FY 2023 Comparable", "YoY Change"],
        ["Total Revenue", "$175,595,178.16", "~$162,400,000", "+8.1%"],
        ["Total Transactions", "100,000", "~91,200", "+9.6%"],
        ["Active Customers", "14,979", "~13,400", "+11.8%"],
        ["Revenue per Customer", "$11,722.76", "~$12,119", "-3.3%"],
        ["Electronics Revenue Share", "51.8%", "50.1%", "+1.7 pts"],
        ["Return Rate (% of transactions)", "6.0%", "5.8%", "+0.2 pts"],
        ["Support Cases Filed", "2,000", "~1,820", "+9.9%"],
        ["Inventory Low-Stock SKUs (year-end)", "72 (3.6%)", "~31 (1.6%)", "+41 SKUs"],
        ["Digital Wallet Payment Share (Q4)", "22.4%", "~9.1%", "+13.3 pts"],
    ]
    story += [
        _table(kpi_rows, col_widths=[200, 130, 120, 95]),
        P("FY 2023 comparables are management estimates; formal audited comparatives available separately.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("2. Revenue Analysis by Quarter", e["SectionHead"]),
        P("Revenue growth accelerated through the year, with each successive quarter "
          "exceeding the prior quarter. Q1 2024 started the year at $38,241,892 — 13.2% "
          "above Q4 2023 run rate — driven by new customer acquisition campaigns and "
          "expanded mobile app distribution. Q2 grew 10.3% to $42,184,731 as spring "
          "category promotions drove Home and Sports demand. Q3 added 2.7% to $43,322,150 "
          "with back-to-school Electronics serving as the primary growth driver. Q4 surged "
          "20.6% to $58.9M — the largest single-quarter revenue figure in company "
          "history — on the back of holiday Electronics demand that exceeded forecast by "
          "$3.9M.", e["Body"]),
    ]
    qtr_rows = [
        ["Quarter", "Revenue", "% of FY", "Transactions (est.)", "Key Category", "vs Prior Quarter"],
        ["Q1 2024 (Jan-Mar)", "$38,241,892.14", "21.8%", "~23,800", "Electronics", "— (year start)"],
        ["Q2 2024 (Apr-Jun)", "$42,184,731.08", "24.0%", "~25,300", "Sports, Home", "+10.3%"],
        ["Q3 2024 (Jul-Sep)", "$43,322,149.57", "24.7%", "~25,900", "Electronics (back-to-school)", "+2.7%"],
        ["Q4 2024 (Oct-Dec)", "$58.9M", "33.5%", "29,500", "Electronics (holiday)", "+20.6%"],
        ["FY 2024 Total", "$175,595,178.16", "100%", "100,000", "Electronics (51.8% of total)", "—"],
    ]
    story += [
        _table(qtr_rows, col_widths=[115, 110, 60, 95, 130, 90]),
        _sp(),
    ]

    story += [
        P("3. Category Performance Review", e["SectionHead"]),
        P("Electronics extended its dominance in FY 2024, growing to $90,958,302.29 and "
          "51.8% of total revenue. The category's growth was powered by all four product "
          "lines: Laptop, Phone, Tablet, and Headphones. The Tablet quality issue addressed "
          "in Q3 2024 (accelerometer calibration defect affecting one model) was contained "
          "and resolved without material impact on the full-year Tablet revenue figure. "
          "For a complete Electronics analysis, see the Electronics Category Deep-Dive.", e["Body"]),
        P("Home Goods at $40,877,008.66 and Sports at $27,478,085.87 both delivered "
          "consistent performances throughout the year without significant anomalies. "
          "Clothing at $11,731,765.10 was the most volatile category, with Q4 return "
          "rates for Jeans and Jacket requiring active management per the Returns and "
          "Refunds Policy. Food at $4,498,192.92 remained the smallest category and "
          "primarily serves as a complementary product offering.", e["Body"]),
    ]
    cat_annual_rows = [
        ["Category", "FY 2024 Revenue", "% of Total", "YoY Growth (est.)", "Return Count", "FY 2025 Outlook"],
        ["Electronics", "$90,958,302.29", "51.8%", "+10.2%", "1,206", "Strong — 8-12% growth projected"],
        ["Home", "$40,877,008.66", "23.3%", "+6.8%", "911", "Stable — 5-7% growth projected"],
        ["Sports", "$27,478,085.87", "15.6%", "+4.1%", "771", "Moderate — 4-6% growth projected"],
        ["Clothing", "$11,731,765.10", "6.7%", "+3.2%", "859", "Cautious — return rate management priority"],
        ["Food", "$4,498,192.92", "2.6%", "+1.8%", "253", "Stable — no major changes planned"],
        ["Total", "$175,595,178.16", "100%", "+8.1%", "5,685 (5.7% rate)", "8-10% growth target"],
    ]
    story += [
        _table(cat_annual_rows, col_widths=[90, 110, 65, 90, 80, 150]),
        _sp(),
    ]

    story += [
        P("4. Customer Analysis", e["SectionHead"]),
        P("The 14,979-customer base grew 11.8% year-over-year. Customer quality — measured "
          "by average spend — declined slightly from $12,119 in FY 2023 to $11,722.76 in "
          "FY 2024, reflecting an influx of newer, lower-frequency customers in the customer "
          "mix. This pattern is typical during high-growth acquisition periods and is "
          "expected to normalize as new cohorts mature.", e["Body"]),
        P("The top-spending customers represent a disproportionate share of revenue. The "
          "top 10% of customers (approximately 1,498 accounts) generated an estimated 34% "
          "of total revenue. The West region has the highest revenue-per-customer at "
          "$16,113.78 versus the network average of $11,722.76; the Central region has "
          "the lowest at $7,757.83, representing the largest opportunity for per-customer "
          "revenue improvement. The Customer Lifetime Value Study provides a complete "
          "segmentation and cohort analysis.", e["Body"]),
    ]

    story += [
        P("5. Strategic Priorities for FY 2025", e["SectionHead"]),
        P("Three strategic priorities emerge from the FY 2024 performance review. First, "
          "supply chain resilience must be strengthened. The Q4 2024 inventory shortage "
          "cost an estimated $2.1M in lost Electronics revenue and exposed over-dependence "
          "on a single Electronics vendor. Vendor diversification and improved forecasting "
          "are underway per the Inventory Shortage Root Cause Analysis corrective actions.", e["Body"]),
        P("Second, Central and South region Electronics penetration represents the largest "
          "revenue opportunity within the existing customer base. Central customers spend "
          "only $4,058 in Electronics per year versus $7,888 for South and $6,341 for West. "
          "Targeted Electronics cross-sell campaigns in Central could yield incremental "
          "revenue of $8-12M annually if per-customer Electronics spend can be raised to "
          "even the South region's level.", e["Body"]),
        P("Third, digital wallet adoption momentum should be sustained. The shift from "
          "credit cards to digital wallets reduces fraud costs and improves checkout "
          "completion rates. The FY 2025 payment strategy will prioritize further digital "
          "wallet incentives, with an FY 2025 target of 30% digital wallet share across "
          "all transactions.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 14: Customer Lifetime Value Study ───────────────────────────────

def build_clv_study(out_path: Path) -> None:
    doc = _make_doc(out_path, "Customer Lifetime Value Study FY 2024 — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Customer Lifetime Value Study", e["DocTitle"]),
        P("FY 2024 Customer Segmentation and CLV Analysis | Prepared by: Customer Analytics", e["Subtitle"]),
        P("Date: February 3, 2025 | Distribution: Marketing, Customer Success, Finance | "
          "Classification: Internal", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Study Overview and Methodology", e["SectionHead"]),
        P("This study analyzes the lifetime value of NexusIQ's 14,979 active customers "
          "using FY 2024 purchase data from the sales_transactions table (100,000 "
          "transactions, $175,595,178.16 total revenue). Customer lifetime value (CLV) is "
          "calculated as total revenue attributable to a customer account since first "
          "purchase. Average CLV across all active customers is $11,722.76, equal to the "
          "average annual spend figure, as FY 2024 is the primary measurement period.", e["Body"]),
        P("Customers are segmented into five tiers based on CLV and purchase behavior: "
          "Diamond (top 2% by spend, CLV >$35,000), Platinum (next 8%, CLV $15,000-$35,000), "
          "Gold (next 15%, CLV $7,500-$15,000), Silver (next 25%, CLV $3,000-$7,500), and "
          "Bronze (remaining 50%, CLV <$3,000). The relationship between tier and category "
          "affinity, regional distribution, and return behavior is analyzed in subsequent "
          "sections.", e["Body"]),
    ]

    story += [
        P("2. Customer Tier Summary", e["SectionHead"]),
    ]
    tier_rows = [
        ["Tier", "CLV Range", "Customer Count", "% of Base", "Revenue Contribution", "% of Total Revenue"],
        ["Diamond", ">$35,000", "300 customers", "2.0%", "~$14,231,580", "8.1%"],
        ["Platinum", "$15,000-$35,000", "1,198 customers", "8.0%", "~$28,463,160", "16.2%"],
        ["Gold", "$7,500-$15,000", "2,247 customers", "15.0%", "~$38,836,310", "22.1%"],
        ["Silver", "$3,000-$7,500", "3,745 customers", "25.0%", "~$35,760,500", "20.4%"],
        ["Bronze", "<$3,000", "7,489 customers", "50.0%", "~$58,303,630", "33.2%"],
        ["Total", "—", "14,979 customers", "100%", "$175,595,178", "100%"],
    ]
    story += [
        _table(tier_rows, col_widths=[70, 110, 95, 70, 120, 110]),
        P("Revenue contributions estimated using tier CLV midpoints. Diamond/Platinum combined revenue: 24.3% from top 10%.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("3. Regional CLV Distribution", e["SectionHead"]),
        P("Customer lifetime value is not distributed uniformly across regions. West region "
          "customers have the highest average CLV at $16,113.78 — 37.5% above the network "
          "average of $11,722.76. The West concentration of Diamond and Platinum tier "
          "customers reflects both the region's historical tenure as an early NexusIQ "
          "market and the region's strong Electronics category affinity, where high-ASP "
          "Laptop and Phone purchases compound rapidly over multiple upgrade cycles.", e["Body"]),
        P("South region's average CLV of $15,224.51 is the second-highest — somewhat "
          "surprising given the region's fourth-place finish in absolute revenue. South "
          "benefits from having a small but highly engaged customer base with "
          "above-average purchase frequency. The South CLV profile suggests the region's "
          "growth opportunity lies in customer acquisition rather than per-customer "
          "value improvement, the inverse of the Central region's situation.", e["Body"]),
    ]
    clv_reg_rows = [
        ["Region", "Customers", "Avg CLV", "vs Network Avg", "Diamond+Platinum %", "Retention Rate (12-mo)"],
        ["West", "2,351", "$16,113.78", "+37.5%", "14.2%", "74.2%"],
        ["South", "2,330", "$15,224.51", "+29.9%", "13.8%", "68.8%"],
        ["North", "2,023", "$14,955.51", "+27.6%", "13.1%", "71.3%"],
        ["East", "3,676", "$9,880.37", "-15.7%", "8.9%", "72.9%"],
        ["Central", "4,599", "$7,757.83", "-33.8%", "6.1%", "61.4%"],
        ["Network", "14,979", "$11,722.76", "—", "10.0%", "70.2%"],
    ]
    story += [
        _table(clv_reg_rows, col_widths=[70, 75, 90, 90, 105, 120]),
        P("Retention rate = % of customers who made at least one purchase in the 12 months following first purchase.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("4. CLV and Category Affinity", e["SectionHead"]),
        P("A strong correlation exists between Electronics category adoption and customer "
          "tier. Diamond and Platinum customers have an Electronics spend share of 64.3% "
          "versus 51.8% network average, and their average Electronics transaction value "
          "of $2,248 exceeds the network Electronics average of $1,338 by 68%. These "
          "high-tier customers consistently purchase Laptop and Phone — the two "
          "highest-ASP Electronics products — and exhibit strong renewal and upgrade "
          "purchase patterns.", e["Body"]),
        P("Bronze tier customers, by contrast, have Electronics spend share of only 38.7% "
          "and are more concentrated in Food, Clothing, and lower-ASP Electronics products "
          "like Headphones. The Bronze-to-Silver tier upgrade pathway — where a customer "
          "first engages through a low-ASP Food or Clothing purchase and then cross-sells "
          "into Electronics — is one of the highest-value conversion opportunities in "
          "NexusIQ's customer base.", e["Body"]),
    ]

    story += [
        P("5. Customer Retention and Churn Analysis", e["SectionHead"]),
        P("Network-wide 12-month retention rate of 70.2% means that approximately 29.8% "
          "of customers who made a purchase in FY 2024 had not made a prior-year purchase. "
          "This reflects both genuine new customer acquisition and re-activation of "
          "dormant accounts. The churn risk analysis identified 1,847 customers (12.3% "
          "of base) as high churn risk based on declining spend, long dormancy (last "
          "purchase >90 days), or multiple unresolved support cases.", e["Body"]),
        P("High churn risk is concentrated in the Central region (612 at-risk customers, "
          "13.3% of Central base) and East region (482 at-risk, 13.1% of East base). The "
          "Central concentration is consistent with that region's lower retention rate of "
          "61.4% — the lowest in the network. The Returns and Refunds Policy Section 6 "
          "exception program for Platinum/Diamond customers is specifically designed to "
          "address a key churn trigger for high-value accounts.", e["Body"]),
    ]
    churn_rows = [
        ["Region", "At-Risk Customers", "% of Region Base", "Est. Revenue at Risk", "Primary Churn Signal"],
        ["Central", "612", "13.3%", "$4,218,000", "Declining spend QoQ"],
        ["East", "482", "13.1%", "$3,812,000", "Long dormancy (>90 days)"],
        ["West", "284", "12.1%", "$5,124,000", "High return rate"],
        ["South", "284", "12.2%", "$2,987,000", "Unresolved support cases"],
        ["North", "185", "9.1%", "$2,041,000", "Declining spend QoQ"],
        ["Total", "1,847", "12.3%", "~$18,182,000", "—"],
    ]
    story += [
        _table(churn_rows, col_widths=[70, 95, 100, 110, 170]),
        _sp(),
    ]

    story += [
        P("6. Recommendations", e["SectionHead"]),
        P("Three recommendations follow from this CLV analysis. First, invest in Central "
          "region Electronics cross-sell: Central's low per-customer CLV ($7,757.83) "
          "combined with the region's large customer base (4,599 customers) creates the "
          "largest absolute revenue opportunity in the network. A targeted Electronics "
          "introduction campaign for Central Silver-tier customers could yield $6-10M "
          "in incremental annual revenue.", e["Body"]),
        P("Second, prioritize retention intervention for the 1,847 at-risk customers. "
          "The estimated $18.2M revenue at risk represents 10.4% of total FY 2024 revenue. "
          "Even a 25% reduction in churn among at-risk customers would protect "
          "approximately $4.5M in annual revenue at relatively low intervention cost. "
          "The Customer Escalation Policy's Tier 3 success manager team is best positioned "
          "to run proactive retention outreach for high-value at-risk accounts.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Document 15: Supply Chain Risk Assessment ────────────────────────────────

def build_supply_chain_risk(out_path: Path) -> None:
    doc = _make_doc(out_path, "Supply Chain Risk Assessment FY 2025 — NexusIQ")
    s, e = _styles()
    story = []

    story += [
        P("NexusIQ Corporation — Supply Chain Risk Assessment", e["DocTitle"]),
        P("FY 2025 Planning Cycle | Prepared by: Supply Chain Strategy | Date: February 10, 2025", e["Subtitle"]),
        P("Distribution: Executive Team, Supply Chain, Category Management | "
          "Classification: Confidential", e["Meta"]),
        _hr(), _sp(),
    ]

    story += [
        P("1. Purpose and Scope", e["SectionHead"]),
        P("This risk assessment evaluates supply chain vulnerabilities across NexusIQ's "
          "five product categories entering FY 2025. It incorporates lessons from the Q4 "
          "2024 Electronics inventory shortage documented in the Seasonal Demand Incident "
          "Report and the Inventory Shortage Root Cause Analysis, and provides a "
          "forward-looking view of supply risks that could impair NexusIQ's ability to "
          "fulfill demand across its 100-store network.", e["Body"]),
        P("NexusIQ's supply chain serves $175,595,178.16 in annual revenue across 100,000 "
          "transactions. Electronics — the highest-revenue category at $90,958,302.29 — "
          "carries the highest supply chain concentration risk. The network's 72 below-"
          "reorder SKUs at year-end 2024 represent the most visible symptom of supply "
          "chain stress entering FY 2025.", e["Body"]),
    ]

    story += [
        P("2. Risk Inventory by Category", e["SectionHead"]),
    ]
    risk_rows = [
        ["Category", "Primary Risk", "Severity", "Likelihood", "Risk Score", "Key Vendor"],
        ["Electronics", "Single-vendor dependency (TechSource Global); Q4 demand volatility", "HIGH", "HIGH", "9/10", "TechSource Global"],
        ["Home", "Seasonal demand spikes; packaging quality issues", "MEDIUM", "MEDIUM", "5/10", "HomeSupply Co"],
        ["Sports", "Weather-dependent demand volatility", "MEDIUM", "LOW", "3/10", "SportPro Dist."],
        ["Clothing", "Fashion cycle risk; high return rates driving reverse logistics cost", "MEDIUM", "MEDIUM", "5/10", "FashionLink"],
        ["Food", "Shelf life and cold chain compliance", "LOW", "LOW", "2/10", "FreshChain Ltd"],
    ]
    story += [
        _table(risk_rows, col_widths=[80, 175, 60, 65, 70, 95]),
        _sp(),
    ]

    story += [
        P("3. Electronics Vendor Concentration Risk — Critical", e["SectionHead"]),
        P("The most significant supply chain risk facing NexusIQ in FY 2025 is the "
          "concentration of Electronics sourcing in TechSource Global. TechSource "
          "currently supplies approximately 85% of NexusIQ's Laptop, Tablet, and "
          "accessory inventory. The remaining 15% comes from spot purchases across "
          "three secondary vendors, none of which has the capacity to scale to meaningful "
          "NexusIQ volumes on short notice.", e["Body"]),
        P("TechSource's FY 2024 on-time delivery rate of 94.2% — below the 95% contract "
          "minimum — combined with the Q4 2024 emergency order failure (two shipments "
          "arriving 7-8 days late during the critical Black Friday window) demonstrates "
          "that single-vendor dependency creates material business risk. If TechSource "
          "experiences a production disruption, NexusIQ has no qualified backup capable "
          "of filling the gap within a holiday-season lead time.", e["Body"]),
        P("The corrective action — qualifying a secondary vendor at 15% contracted share "
          "— is on track for March 2025 completion. The target secondary vendor is Pacific "
          "Components Ltd, which completed initial quality assessment in January 2025 with "
          "acceptable results. A trial order of 500 Laptop units is scheduled for "
          "February 2025. If the trial is successful, the formal contract will target "
          "15% Electronics share by Q2 2025, rising to 25% by Q4 2025 in advance of the "
          "next holiday season.", e["Body"]),
    ]

    story += [
        P("4. Clothing Category Reverse Logistics Risk", e["SectionHead"]),
        P("Clothing's 5,685-return contribution (assuming proportional share of the "
          "network total) and elevated return rates in Jeans (331 returns) and Jacket "
          "(287 returns) create a structural reverse logistics cost that erodes category "
          "margins. The FashionLink vendor is on performance notice for fill rate below "
          "target, adding forward logistics risk to an already stressed category.", e["Body"]),
        P("Two risk mitigation options are under evaluation for Clothing in FY 2025. "
          "Option A is a return reduction program: investing in improved size guides, "
          "augmented reality try-on tools for the mobile app, and more accurate product "
          "photography to reduce returns driven by size and appearance mismatches. "
          "Estimated return rate reduction: 1.5-2.0 percentage points. Option B is a "
          "vendor change: replacing FashionLink with a vendor capable of higher fill "
          "rates and better product quality consistency. The decision will be made "
          "by the Q1 2025 business review.", e["Body"]),
    ]

    story += [
        P("5. Demand Forecast Risk for FY 2025", e["SectionHead"]),
        P("The revised forecasting methodology — using a 6-month rolling average weighted "
          "60/40 toward recent periods — will reduce forecast error for high-growth "
          "categories. However, FY 2025 introduces a new forecasting challenge: "
          "NexusIQ's customer base has grown 11.8% in FY 2024 and the geographic "
          "expansion of the customer base into underserved North region markets is "
          "planned for H1 2025. New market demand is inherently harder to forecast "
          "than demand from established customer cohorts.", e["Body"]),
        P("Supply chain planners should build 15% demand uplift buffers into North region "
          "inventory positions for the first two quarters of FY 2025 until demand patterns "
          "stabilize. This is consistent with the Inventory Reorder SOP's framework for "
          "new market inventory positioning. Total incremental inventory investment for "
          "North region expansion is estimated at approximately $840,000 in working capital "
          "above standard network norms.", e["Body"]),
    ]

    story += [
        P("6. Mitigation Roadmap — FY 2025", e["SectionHead"]),
    ]
    roadmap_rows = [
        ["Initiative", "Category", "Target Completion", "Expected Benefit", "Investment"],
        ["Secondary vendor qualification (Pacific Components)", "Electronics", "Q1 2025", "Reduces single-vendor risk; adds surge capacity", "$80K qualification cost"],
        ["Forecast model update (6-month rolling, 60/40 weight)", "All", "Jan 2025 (complete)", "Reduces Q4 demand surprise; earlier reorder triggers", "Internal — no cost"],
        ["Q4 seasonal multiplier in reorder SOP (1.3x)", "Electronics, Home", "Completed Mar 2024", "Larger Q4 safety buffer", "Carrying cost: ~$120K/year"],
        ["Promotional demand elasticity review process", "All", "Feb 2025", "Prevents bundle-driven stockouts like Q4 2024", "Internal — 2 FTEs"],
        ["FashionLink performance review / vendor change decision", "Clothing", "Q1 2025", "Improved fill rate; reduced return-driven costs", "TBD pending decision"],
        ["North region expansion inventory buffer", "All", "Q1-Q2 2025", "Supports new market launch without stockout risk", "~$840K working capital"],
    ]
    story += [
        _table(roadmap_rows, col_widths=[145, 70, 85, 165, 80], small=True),
        P("Progress updates to be presented at monthly Supply Chain Operations review. "
          "Major milestones reviewed at Q1 2025 business review.", e["Caption"]),
        _sp(),
    ]

    story += [
        P("7. Summary Risk Rating", e["SectionHead"]),
        P("Entering FY 2025, NexusIQ's supply chain is in a managed-risk state. The Q4 "
          "2024 shortage was a significant operational event but has produced a clear set "
          "of corrective actions with defined owners and timelines. The Electronics "
          "vendor concentration risk remains the highest-priority open item; until the "
          "secondary vendor relationship is established and proven, NexusIQ retains "
          "meaningful exposure to a repeat of Q4 2024 conditions in the next holiday "
          "season. The supply chain team considers the current risk trajectory as "
          "'improving' provided the Q1 2025 vendor qualification milestones are met "
          "on schedule.", e["Body"]),
    ]

    doc.build(story)
    print(f"  OK {out_path.name}")


# ─── Generation + ingestion orchestration ─────────────────────────────────────

PDFS = [
    ("01_Returns_Refunds_Policy.pdf",               build_returns_policy),
    ("02_Inventory_Reorder_SOP.pdf",                build_inventory_reorder_sop),
    ("03_Customer_Escalation_Policy.pdf",           build_escalation_policy),
    ("04_Q4_2024_Revenue_Performance_Memo.pdf",     build_q4_revenue_memo),
    ("05_Q3_2024_Revenue_Performance_Memo.pdf",     build_q3_revenue_memo),
    ("06_Electronics_Category_Deep_Dive.pdf",       build_electronics_deep_dive),
    ("07_Regional_Performance_Analysis.pdf",        build_regional_analysis),
    ("08_Payment_Method_Adoption_Report.pdf",       build_payment_method_report),
    ("09_Weekly_Operations_Digest_Week48.pdf",      build_weekly_digest_week48),
    ("10_Weekly_Operations_Digest_Week12.pdf",      build_weekly_digest_week12),
    ("11_Seasonal_Demand_Incident_Report.pdf",      build_seasonal_demand_incident),
    ("12_Inventory_Shortage_Root_Cause_Analysis.pdf", build_inventory_shortage_rca),
    ("13_2024_Annual_Business_Review.pdf",          build_annual_business_review),
    ("14_Customer_Lifetime_Value_Study.pdf",        build_clv_study),
    ("15_Supply_Chain_Risk_Assessment.pdf",         build_supply_chain_risk),
]


def generate_all() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerating {len(PDFS)} enterprise prose PDFs -> {OUTPUT_DIR}\n")
    for filename, builder in PDFS:
        out = OUTPUT_DIR / filename
        print(f"  Building {filename}...")
        builder(out)
    print(f"\nAll {len(PDFS)} PDFs written.\n")


def ingest_all() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from database.setup_rag_pipeline import RAGPipelineSetup, bump_ingestion_version

    print(f"\nIngesting {CATEGORY} PDFs into ChromaDB...\n")
    pipeline = RAGPipelineSetup(reset_collection=False)

    for filename, _ in PDFS:
        pdf_path = OUTPUT_DIR / filename
        if not pdf_path.exists():
            print(f"  MISSING: {filename} — run 'generate' first")
            continue

        print(f"\n  {filename}")
        pages_data, metadata = pipeline.extract_text_from_pdf(pdf_path)
        if not pages_data:
            print(f"    No text extracted")
            continue

        try:
            existing = pipeline.collection.get(where={"filename": {"$eq": filename}})
            if existing["ids"]:
                pipeline.collection.delete(ids=existing["ids"])
                print(f"    Deleted {len(existing['ids'])} stale chunks")
        except Exception:
            pass

        chunks = pipeline.chunk_text(pages_data, metadata)
        print(f"    Created {len(chunks)} chunks")
        pipeline.embed_and_store(chunks)

    new_ver = bump_ingestion_version()
    total = pipeline.collection.count()
    print(f"\nIngestion complete. Collection size: {total} | Version: {new_ver}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate/ingest NexusIQ enterprise prose PDFs for RAG corpus")
    parser.add_argument("action",
                        choices=["generate", "ingest", "generate-and-ingest"])
    args = parser.parse_args()
    if args.action in ("generate", "generate-and-ingest"):
        generate_all()
    if args.action in ("ingest", "generate-and-ingest"):
        ingest_all()


if __name__ == "__main__":
    main()
