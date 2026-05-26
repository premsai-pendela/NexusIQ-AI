"""
Generate and ingest a realistic noise corpus for NexusIQ RAG stress-testing.

Creates three PDFs in data/pdfs/07_communications/:
  01_Slack_Business_Communications_2024.pdf  — 200 Slack-style messages
  02_Email_Business_Threads_2024.pdf         — 50 email threads
  03_Returns_Policy_Outdated_v1.pdf          — old 14-day policy (conflicts with current 30-day)

All content is grounded in NexusIQ business context: products, regions, revenue,
categories, store IDs. Tests retrieval precision under noise and conflict resolution.

Usage:
    python -m database.generate_noise_corpus plan
    python -m database.generate_noise_corpus generate
    python -m database.generate_noise_corpus ingest
    python -m database.generate_noise_corpus generate-and-ingest
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "pdfs" / "07_communications"
CATEGORY = "07_communications"

REGIONS = ["North", "South", "East", "West", "Central"]
PRODUCTS = ["Laptop", "Phone", "Tablet", "Headphones", "Jacket", "Jeans",
            "Shoes", "T-Shirt", "Bedding", "Decor", "Furniture", "Kitchen",
            "Accessories", "Apparel", "Equipment", "Footwear",
            "Drinks", "Frozen", "Produce", "Snacks"]
CATEGORIES = ["Electronics", "Clothing", "Home", "Sports", "Food"]
STORES = [f"{r[0]}{str(i).zfill(3)}" for r in REGIONS for i in range(1, 21)]
NAMES = ["Sarah", "James", "Priya", "David", "Maria", "Kevin", "Linda",
         "Tom", "Aisha", "Carlos", "Rachel", "Ben", "Yuki", "Omar", "Emma"]
DEPTS = ["Finance", "Operations", "Sales", "Marketing", "Supply Chain", "Analytics"]

_rng = random.Random(99)

# ─── Revenue figures consistent with live data ───────────────────────────────
QUARTERLY_REVENUE = {
    "Q1": "$38.2M",
    "Q2": "$41.7M",
    "Q3": "$44.9M",
    "Q4": "$50.7M",
}
CATEGORY_REVENUE = {
    "Electronics": "$62.4M",
    "Clothing": "$41.1M",
    "Home": "$28.7M",
    "Sports": "$24.9M",
    "Food": "$18.5M",
}

# ─── Slack message templates ──────────────────────────────────────────────────

SLACK_TEMPLATES = [
    # Financial discussions
    "hey team — {q} revenue came in at {rev}. {region} region led the quarter again.",
    "{q} {cat} numbers look strong at {rev}. anyone see a breakdown by store?",
    "just pulled the SQL — {q} has {rev} total across all 5 regions. sanity check looks good.",
    "reminder: {q} review call is tomorrow. prep your regional numbers. {region} is presenting first.",
    "quick heads up: {q} {cat} underperformed vs forecast by ~4%. ops team is looking into it.",
    "{region} store {store} had their best week in Q3. {cat} sales up 12% week over week.",
    "checked the DB — {cat} return rate is around 3% this year. Bedding slightly higher.",
    "who owns the {q} investor deck? finance needs the {cat} revenue breakdown by EOD.",
    "FYI: {store} just flagged low inventory on {product}. reorder point hit.",
    "West vs South comparison for {q}: West outperformed by ~18%. consistent with last year.",
    # Operations
    "inventory alert: {store} has {product} stock below reorder threshold. escalate?",
    "{product} return rate in {region} region spiked this week. checking if it's a batch issue.",
    "store {store} ops manual says to reorder when stock < 25 units. current level is critical.",
    "supply chain: {cat} products in {region} have 4-day lead time. plan accordingly for {q}.",
    "anyone have the {q} transaction count? need it for the board deck. should be ~25K.",
    # Support / Customer
    "support queue: 42 open cases this week. most are about late delivery in {region}.",
    "customer {cust} opened 3 tickets in 30 days. flag for CS team review.",
    "return policy question came up again — remind customers returns are accepted within 30 days.",
    "billing discrepancy reported for {product} orders in {store}. finance reviewing.",
    "urgent priority cases up 15% this month. CS team needs reinforcement.",
    # Strategy
    "{region} region showing consistent 18% outperformance. expansion feasibility study underway.",
    "Digital transformation roadmap update: phase 2 targets {cat} supply chain automation.",
    "competitor just dropped {product} price by 8%. our pricing team is reviewing response.",
    "strategic plan 2025 draft circulated. {region} expansion is the key growth lever.",
    "market analysis: Electronics demand up 12% YoY in Q4. timing aligns with our {q} data.",
    # HR / Compliance
    "compliance training deadline is end of month. all regional managers need to complete.",
    "employee handbook updated — new PTO policy effective Q1 2025.",
    "performance reviews start next week. use Q3 + Q4 transaction data as baseline.",
    "HR: onboarding 15 new CS reps next month. {region} getting 6 of them.",
    "vendor contract with {cat} supplier up for renewal. procurement team taking lead.",
    # Noise / ambiguous (realistic office chatter about business)
    "quick question: does the {q} report include {store} pilot data or just main stores?",
    "the numbers in the PDF don't match what SQL returns for {q}. anyone else seeing this?",
    "heads up: {product} is back in stock at {store}. update the website listing.",
    "can someone pull the {cat} revenue for all 4 quarters? CEO wants YoY comparison.",
    "the {q} board presentation uses $M format but the SQL query returns raw numbers. normalize.",
]

EMAIL_TEMPLATES = [
    {
        "subject": "{q} Business Review — {cat} Performance Summary",
        "body": (
            "Team,\n\n"
            "Attached is the {q} performance summary for the {cat} category.\n\n"
            "Key highlights:\n"
            "- Total revenue: {rev} ({q})\n"
            "- {region} region led with 18% above target\n"
            "- Return rate held steady at ~3% across all stores\n"
            "- Top performing store: {store} (+22% vs prior quarter)\n\n"
            "Action items:\n"
            "1. Review inventory levels for {product} ahead of next quarter\n"
            "2. CS team to address the 15% uptick in support cases\n"
            "3. Finance to reconcile {store} billing discrepancy\n\n"
            "Let me know if you have questions.\n\n"
            "Best,\n{name} ({dept})"
        ),
    },
    {
        "subject": "RE: {q} SQL vs PDF Revenue Discrepancy — RESOLVED",
        "body": (
            "All,\n\n"
            "Following up on the earlier thread about {q} revenue numbers.\n\n"
            "Root cause found: the PDF report rounds to nearest $0.1M while SQL returns\n"
            "exact figures. Both sources are correct — the difference is presentation only.\n\n"
            "SQL exact: {rev} ({q})\n"
            "PDF reported: same figure, rounded to 1 decimal place\n\n"
            "No data issue. Closing this thread.\n\n"
            "{name} | {dept}"
        ),
    },
    {
        "subject": "{region} Region Performance Alert — {q}",
        "body": (
            "Hi team,\n\n"
            "Flagging an anomaly in {region} region data for {q}.\n\n"
            "{cat} sales in stores {store} are running 12% below forecast.\n"
            "Possible causes under investigation:\n"
            "  - Supply chain delay on {product} replenishment\n"
            "  - Competitor pricing pressure (see attached market analysis)\n"
            "  - Seasonal demand shift\n\n"
            "Operations team is reviewing inventory levels. Will update by EOW.\n\n"
            "Regards,\n{name}\n{dept} Team"
        ),
    },
    {
        "subject": "Customer Support Escalation — {q} Volume Spike",
        "body": (
            "CS Leadership,\n\n"
            "We've seen a 15% increase in support case volume during {q}.\n\n"
            "Breakdown by priority:\n"
            "  - Urgent: 257 cases\n"
            "  - High: 244 cases\n"
            "  - Medium: 198 cases\n"
            "  - Low: 254 cases (many are order status inquiries)\n\n"
            "Top subjects:\n"
            "  1. Order not received\n"
            "  2. Return requests (30-day policy applies)\n"
            "  3. Billing discrepancy\n\n"
            "Recommend adding 6 CS reps to {region} team for Q3.\n\n"
            "{name} | CS Operations"
        ),
    },
    {
        "subject": "Inventory Reorder Alert — {product} at {store}",
        "body": (
            "Supply Chain Team,\n\n"
            "Automated alert: {product} stock at store {store} ({region} region)\n"
            "has fallen below the reorder threshold of 25 units.\n\n"
            "Current stock: {stock} units\n"
            "Reorder point: 25 units\n"
            "Recommended order quantity: 150 units\n"
            "Lead time: 4 business days\n\n"
            "Please initiate the vendor reorder process per the Inventory Management Policy.\n\n"
            "Automated alert — {dept} System"
        ),
    },
    {
        "subject": "Annual Performance Review Data — {q} Baseline",
        "body": (
            "Managers,\n\n"
            "As we enter performance review season, please use the following\n"
            "{q} data as your baseline for regional and team assessments:\n\n"
            "  - Total transactions: ~25,000 ({q})\n"
            "  - Revenue: {rev}\n"
            "  - {cat} category contribution: {cat_rev}\n"
            "  - Top region: {region} (+18% vs average)\n"
            "  - Customer satisfaction: 4.2/5.0 (survey data, Q3 2024)\n\n"
            "Full data available in the SQL dashboard. PDF summary in shared drive.\n\n"
            "{name}\nHR & Analytics"
        ),
    },
]


def _slack_row(template: str) -> str:
    q = _rng.choice(list(QUARTERLY_REVENUE.keys()))
    cat = _rng.choice(CATEGORIES)
    name = _rng.choice(NAMES)
    region = _rng.choice(REGIONS)
    store = _rng.choice(STORES)
    product = _rng.choice(PRODUCTS)
    cust = f"CUST{_rng.randint(1,15000):05d}"
    return template.format(
        q=q, rev=QUARTERLY_REVENUE[q], cat=cat, region=region,
        store=store, product=product, cust=cust,
        cat_rev=CATEGORY_REVENUE.get(cat, "$30M"),
    )


def _email_row(template: dict) -> tuple[str, str]:
    q = _rng.choice(list(QUARTERLY_REVENUE.keys()))
    cat = _rng.choice(CATEGORIES)
    name = _rng.choice(NAMES)
    region = _rng.choice(REGIONS)
    store = _rng.choice(STORES)
    product = _rng.choice(PRODUCTS)
    dept = _rng.choice(DEPTS)
    stock = _rng.randint(5, 24)
    subj = template["subject"].format(
        q=q, cat=cat, region=region, store=store, product=product,
        rev=QUARTERLY_REVENUE[q], name=name, dept=dept,
    )
    body = template["body"].format(
        q=q, cat=cat, region=region, store=store, product=product,
        rev=QUARTERLY_REVENUE[q], name=name, dept=dept, stock=stock,
        cat_rev=CATEGORY_REVENUE.get(cat, "$30M"),
    )
    return subj, body


def _build_slack_pdf(out_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    styles = getSampleStyleSheet()
    channel_style = ParagraphStyle("chan", parent=styles["Normal"],
                                    fontSize=8, textColor=colors.grey)
    msg_style = ParagraphStyle("msg", parent=styles["Normal"], fontSize=9,
                                leading=13, spaceAfter=4)
    sender_style = ParagraphStyle("sender", parent=styles["Normal"],
                                   fontSize=8, textColor=colors.HexColor("#0066cc"),
                                   spaceBefore=6)

    channels = ["#sales-ops", "#finance-team", "#operations", "#support-escalations",
                "#inventory-alerts", "#strategy", "#hr-announcements", "#regional-leads"]

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = [
        Paragraph("NexusIQ Corporation — Internal Slack Communications Archive 2024",
                  styles["Heading1"]),
        Paragraph("Source: internal Slack export, 2024 | Classification: Internal",
                  styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    base_date = datetime(2024, 1, 15, 9, 0)
    for i in range(200):
        template = _rng.choice(SLACK_TEMPLATES)
        message = _slack_row(template)
        channel = _rng.choice(channels)
        sender = _rng.choice(NAMES)
        ts = base_date + timedelta(hours=_rng.randint(0, 8000))
        ts_str = ts.strftime("%b %d, %Y %I:%M %p")

        story.append(Paragraph(f"{channel} · {ts_str}", channel_style))
        story.append(Paragraph(f"<b>{sender}:</b>", sender_style))
        story.append(Paragraph(message, msg_style))
        if i % 10 == 9:
            story.append(HRFlowable(width="100%", thickness=0.5,
                                     color=colors.lightgrey))

    doc.build(story)


def _build_email_pdf(out_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    styles = getSampleStyleSheet()
    subj_style = ParagraphStyle("subj", parent=styles["Heading3"],
                                 fontSize=10, textColor=colors.HexColor("#1a1a1a"),
                                 spaceBefore=12)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"],
                                 fontSize=8, textColor=colors.grey)
    body_style = ParagraphStyle("body", parent=styles["Normal"],
                                 fontSize=9, leading=14)

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = [
        Paragraph("NexusIQ Corporation — Business Email Thread Archive 2024",
                  styles["Heading1"]),
        Paragraph("Source: internal email export, 2024 | Classification: Internal",
                  styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]

    base_date = datetime(2024, 1, 20, 8, 0)
    for i in range(50):
        tmpl = _rng.choice(EMAIL_TEMPLATES)
        subj, body = _email_row(tmpl)
        sender = _rng.choice(NAMES)
        ts = base_date + timedelta(hours=_rng.randint(0, 6000))
        ts_str = ts.strftime("%B %d, %Y")
        recipients = ", ".join(_rng.sample(NAMES, 3))

        story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
        story.append(Paragraph(f"Subject: {subj}", subj_style))
        story.append(Paragraph(
            f"From: {sender} &nbsp;|&nbsp; To: {recipients} &nbsp;|&nbsp; Date: {ts_str}",
            meta_style))
        story.append(Spacer(1, 0.05 * inch))
        for line in body.split("\n"):
            story.append(Paragraph(line or "&nbsp;", body_style))

    doc.build(story)


def _build_outdated_policy_pdf(out_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    styles = getSampleStyleSheet()
    warn_style = ParagraphStyle("warn", parent=styles["Normal"],
                                 fontSize=10, textColor=colors.red,
                                 borderColor=colors.red, borderWidth=1,
                                 borderPadding=6, backColor=colors.HexColor("#fff3f3"))

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                             leftMargin=inch, rightMargin=inch)
    story = [
        Paragraph("NexusIQ Corporation", styles["Normal"]),
        Paragraph("Returns and Refunds Policy — Version 1.0 (SUPERSEDED)",
                  styles["Heading1"]),
        Paragraph("Effective: January 1, 2022 | Status: OUTDATED — Superseded by v2.0 (2023)",
                  styles["Normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "⚠ NOTICE: This document is outdated. Current policy (v2.0) supersedes all terms below. "
            "For current return window, see Returns_Refunds_Policy.pdf (v2.0).",
            warn_style,
        ),
        Spacer(1, 0.2 * inch),
        Paragraph("1. Return Window", styles["Heading2"]),
        Paragraph(
            "Customers may return eligible products within <b>14 calendar days</b> of delivery. "
            "Returns after 14 days will not be accepted under this policy version.",
            styles["BodyText"],
        ),
        Spacer(1, 0.1 * inch),
        Paragraph("2. Eligible Products", styles["Heading2"]),
        Paragraph(
            "All product categories (Electronics, Clothing, Home, Sports, Food) are eligible "
            "for return within the 14-day window, provided items are unused and in original packaging.",
            styles["BodyText"],
        ),
        Spacer(1, 0.1 * inch),
        Paragraph("3. Refund Processing", styles["Heading2"]),
        Paragraph(
            "Approved refunds are processed within 5-7 business days to the original payment method. "
            "Debit Card and Credit Card refunds may take an additional 2-3 days to appear.",
            styles["BodyText"],
        ),
        Spacer(1, 0.1 * inch),
        Paragraph("4. Non-Returnable Items", styles["Heading2"]),
        Paragraph(
            "Food category items (Drinks, Frozen, Produce, Snacks) are non-returnable once opened.",
            styles["BodyText"],
        ),
        Spacer(1, 0.3 * inch),
        Paragraph(
            "IMPORTANT: This policy was updated to a 30-day return window in Version 2.0 (2023). "
            "All customer-facing communications must reference the current 30-day policy. "
            "This document is archived for historical reference only.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)


def generate_corpus(output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "slack": output_dir / "01_Slack_Business_Communications_2024.pdf",
        "email": output_dir / "02_Email_Business_Threads_2024.pdf",
        "outdated_policy": output_dir / "03_Returns_Policy_Outdated_v1.pdf",
    }
    print("Generating Slack communications PDF...")
    _build_slack_pdf(files["slack"])
    print("Generating email threads PDF...")
    _build_email_pdf(files["email"])
    print("Generating outdated policy PDF...")
    _build_outdated_policy_pdf(files["outdated_policy"])
    return {k: str(v) for k, v in files.items()}


def ingest_corpus(output_dir: Path = OUTPUT_DIR) -> dict:
    from database.ingestion_pipeline import add_single_pdf

    results = {}
    for pdf in sorted(output_dir.glob("*.pdf")):
        print(f"Ingesting {pdf.name}...")
        result = add_single_pdf(pdf, CATEGORY)
        results[pdf.name] = result
        if result.get("error"):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result.get('chunks_added', '?')} chunks")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and ingest NexusIQ noise corpus")
    parser.add_argument(
        "command",
        choices=["plan", "generate", "ingest", "generate-and-ingest"],
        help="Action to perform",
    )
    args = parser.parse_args()

    if args.command == "plan":
        plan = {
            "output_dir": str(OUTPUT_DIR),
            "category": CATEGORY,
            "files": [
                {"name": "01_Slack_Business_Communications_2024.pdf",
                 "content": "200 Slack messages grounded in NexusIQ products/regions/revenue"},
                {"name": "02_Email_Business_Threads_2024.pdf",
                 "content": "50 email threads about Q1-Q4 performance, inventory, support"},
                {"name": "03_Returns_Policy_Outdated_v1.pdf",
                 "content": "Old 14-day policy — conflicts with current 30-day policy"},
            ],
            "purpose": "Stress-test retrieval precision under realistic business noise and policy conflict",
        }
        print(json.dumps(plan, indent=2))

    elif args.command == "generate":
        files = generate_corpus()
        print(json.dumps({"generated": files}, indent=2))

    elif args.command == "ingest":
        results = ingest_corpus()
        print(json.dumps({"ingested": results}, indent=2, default=str))

    elif args.command == "generate-and-ingest":
        files = generate_corpus()
        print("Generated:", list(files.values()))
        results = ingest_corpus()
        print(json.dumps({"generated": files, "ingested": results}, indent=2, default=str))


if __name__ == "__main__":
    main()
