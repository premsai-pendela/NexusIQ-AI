"""
generate_financial_pdfs.py
--------------------------
Auto-reads from PostgreSQL nexusiq_db and generates 5 financial PDFs:
  01_Q4_2024_Financial_Report.pdf
  02_Q3_2024_Financial_Report.pdf
  05_Investor_Presentation_Dec2024.pdf
  06_Q1_2024_Financial_Report.pdf   (new)
  07_Q2_2024_Financial_Report.pdf   (new)

Re-run whenever DB changes — numbers pull from SQL every time.
"""

import psycopg2
import os
from urllib.parse import urlsplit, urlunsplit
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

DB_URL = os.getenv("NEXUSIQ_FINANCIAL_DB_URL") or os.getenv("DATABASE_URL")
PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "pdfs", "01_financial")


def redact_db_url(db_url: str) -> str:
    """Hide credentials before logging a database URL."""
    try:
        parts = urlsplit(db_url)
        if "@" not in parts.netloc:
            return db_url
        host = parts.netloc.rsplit("@", 1)[1]
        return urlunsplit((parts.scheme, f"[redacted]@{host}", parts.path, parts.query, parts.fragment))
    except Exception:
        return "[redacted database url]"

# ─── Styles ─────────────────────────────────────────────────────────────────

styles = getSampleStyleSheet()

BLUE = colors.HexColor('#1f77b4')
DARK = colors.HexColor('#2c3e50')
LIGHT_BLUE = colors.HexColor('#d6eaf8')
HEADER_BLUE = colors.HexColor('#2980b9')

title_style = ParagraphStyle(
    'Title', parent=styles['Heading1'],
    fontSize=22, textColor=BLUE, spaceAfter=6, alignment=1
)
subtitle_style = ParagraphStyle(
    'Subtitle', parent=styles['Normal'],
    fontSize=11, textColor=DARK, spaceAfter=4, alignment=1
)
heading_style = ParagraphStyle(
    'Heading', parent=styles['Heading2'],
    fontSize=13, textColor=DARK, spaceAfter=8, spaceBefore=14
)
body_style = styles['BodyText']
small_style = ParagraphStyle(
    'Small', parent=styles['Normal'],
    fontSize=8, textColor=colors.grey
)

TABLE_STYLE = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HEADER_BLUE),
    ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
    ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE',   (0, 0), (-1, 0), 10),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
    ('FONTSIZE',   (0, 1), (-1, -1), 9),
    ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
    ('ALIGN',      (1, 0), (-1, -1), 'RIGHT'),
    ('ALIGN',      (0, 0), (0, -1), 'LEFT'),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
])


# ─── SQL helpers ────────────────────────────────────────────────────────────

def get_quarter_metrics(cur, year: int, q: int) -> dict:
    """Pull all metrics for one quarter from sales_transactions."""
    m_map = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
    m_start, m_end = m_map[q]
    where = f"""
        WHERE EXTRACT(YEAR FROM transaction_date) = {year}
        AND EXTRACT(MONTH FROM transaction_date) BETWEEN {m_start} AND {m_end}
    """

    cur.execute(f"SELECT COUNT(*), ROUND(SUM(total_amount)::numeric, 0) FROM sales_transactions {where}")
    txns, revenue = cur.fetchone()
    avg = round(revenue / txns) if txns else 0

    cur.execute(f"""
        SELECT region, ROUND(SUM(total_amount)::numeric, 0) as rev
        FROM sales_transactions {where} GROUP BY region ORDER BY rev DESC
    """)
    regions = cur.fetchall()

    cur.execute(f"""
        SELECT product_category, ROUND(SUM(total_amount)::numeric, 0) as rev
        FROM sales_transactions {where} GROUP BY product_category ORDER BY rev DESC
    """)
    categories = cur.fetchall()

    cur.execute(f"""
        SELECT payment_method,
               COUNT(*) as cnt,
               ROUND(COUNT(*)*100.0::numeric/(SELECT COUNT(*) FROM sales_transactions {where}), 1) as pct
        FROM sales_transactions {where} GROUP BY payment_method ORDER BY cnt DESC
    """)
    payments = cur.fetchall()

    cur.execute(f"""
        SELECT product_name, ROUND(SUM(total_amount)::numeric, 0) as rev
        FROM sales_transactions {where} GROUP BY product_name ORDER BY rev DESC LIMIT 5
    """)
    top_products = cur.fetchall()

    return dict(
        year=year, quarter=q, txns=txns, revenue=revenue, avg=avg,
        regions=regions, categories=categories, payments=payments,
        top_products=top_products
    )


def get_full_year(cur, year: int) -> dict:
    yw = f"WHERE EXTRACT(YEAR FROM transaction_date) = {year}"
    cur.execute(f"SELECT COUNT(*), ROUND(SUM(total_amount)::numeric, 0) FROM sales_transactions {yw}")
    txns, revenue = cur.fetchone()

    cur.execute(f"""
        SELECT product_category, ROUND(SUM(total_amount)::numeric, 0) as rev
        FROM sales_transactions {yw}
        GROUP BY product_category ORDER BY rev DESC
    """)
    categories = cur.fetchall()

    cur.execute(f"""
        SELECT payment_method,
               ROUND(COUNT(*)*100.0::numeric/(SELECT COUNT(*) FROM sales_transactions {yw}), 1) as pct
        FROM sales_transactions {yw}
        GROUP BY payment_method ORDER BY pct DESC
    """)
    payments = cur.fetchall()

    return dict(year=year, txns=txns, revenue=revenue, categories=categories, payments=payments)


# ─── Table builder ──────────────────────────────────────────────────────────

def build_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TABLE_STYLE)
    return t


def fmt_m(n):
    """Format number as $XX.XM"""
    return f"${float(n)/1_000_000:.1f}M"


def fmt_pct(part, total):
    return f"{float(part)/float(total)*100:.1f}%"


# ─── PDF builders ────────────────────────────────────────────────────────────

QUARTER_NAMES = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
QUARTER_END_DATES = {
    1: "March 31", 2: "June 30", 3: "September 30", 4: "December 31"
}
QUARTER_SEASON_NOTE = {
    1: "New Year momentum and post-holiday recovery characterized Q1.",
    2: "Spring promotions and seasonal demand lift drove Q2 performance.",
    3: "Back-to-school season fueled Electronics and Clothing strength in Q3.",
    4: "Holiday season and Black Friday drove record Q4 transaction volumes.",
}
QUARTER_OUTLOOK = {
    1: (
        "Q2 Revenue Target", "$34M – $36M", "10–12% sequential growth",
        "Focus: Spring promotions in Clothing and Home categories. "
        "Digital Wallet adoption target: 18%. "
        "West region expansion pilot launches Q2."
    ),
    2: (
        "Q3 Revenue Target", "$37M – $40M", "7–15% sequential growth",
        "Focus: Back-to-school Electronics campaign. "
        "Expand Digital Wallet incentives to South region. "
        "Inventory build-up for Q4 holiday season begins."
    ),
    3: (
        "Q4 Revenue Target", "$42M – $46M", "8–19% sequential growth",
        "Holiday Season Readiness: Inventory increased 35% in Electronics and Home. "
        "200 seasonal employees hired. "
        "Black Friday promotional calendar finalized."
    ),
    4: (
        "Full Year 2025 Target", "$185M – $200M", "23–33% annual growth",
        "West region: 3 new stores (San Diego, San Francisco, Las Vegas). "
        "E-commerce platform launch Q2 2025. "
        "Digital Wallet adoption target 45% by Q4 2025. "
        "South region recovery budget: $1.2M."
    ),
}

REGION_CITY_MAP = {
    "West": "Seattle, Portland, Los Angeles",
    "East": "New York, Boston, Philadelphia",
    "Central": "Chicago, Dallas, Denver",
    "South": "Miami, Atlanta, Houston",
    "North": "Minneapolis, Detroit, Cleveland",
}


def create_quarterly_report(cur, year: int, q: int, prev_q_metrics: dict | None, out_path: str):
    m = get_quarter_metrics(cur, year, q)
    q_name = QUARTER_NAMES[q]
    q_label = f"{q_name} {year}"

    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=inch, rightMargin=inch)
    story = []

    # Header
    story.append(Paragraph(f"NexusIQ Corporation", subtitle_style))
    story.append(Paragraph(f"{q_label} Financial Report", title_style))
    story.append(Paragraph(f"Report Date: {QUARTER_END_DATES[q]}, {year}", subtitle_style))
    story.append(Spacer(1, 0.25*inch))

    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))

    top_region = m['regions'][0][0]
    top_cat = m['categories'][0][0]
    top_cat_rev = m['categories'][0][1]
    top_cat_pct = fmt_pct(top_cat_rev, m['revenue'])
    top_payment = m['payments'][0][0]
    top_payment_pct = m['payments'][0][2]

    if prev_q_metrics:
        seq_growth = (m['revenue'] - prev_q_metrics['revenue']) / prev_q_metrics['revenue'] * 100
        growth_line = f"sequential growth of {seq_growth:.1f}% vs {QUARTER_NAMES[prev_q_metrics['quarter']]} {year}"
    else:
        growth_line = "strong start to fiscal 2024"

    season_note = QUARTER_SEASON_NOTE[q]
    story.append(Paragraph(
        f"{q_label} delivered total revenue of <b>{fmt_m(m['revenue'])}</b> across "
        f"{m['txns']:,} transactions ({growth_line}). "
        f"{season_note} "
        f"{top_region} region led performance; {top_cat} accounted for {top_cat_pct} of revenue. "
        f"{top_payment} represented {top_payment_pct}% of payment volume.",
        body_style
    ))
    story.append(Spacer(1, 0.1*inch))

    # Key Highlights bullet table
    story.append(Paragraph("Key Highlights", heading_style))
    highlight_data = [
        ["Metric", "Value"],
        ["Total Revenue", fmt_m(m['revenue'])],
        ["Total Transactions", f"{m['txns']:,}"],
        ["Average Transaction Value", f"${m['avg']:,}"],
        ["Top Region", f"{top_region}  ({fmt_m(m['regions'][0][1])})"],
        ["Top Category", f"{top_cat}  ({fmt_m(top_cat_rev)}, {top_cat_pct})"],
        ["Top Payment Method", f"{top_payment}  ({top_payment_pct}%)"],
    ]
    story.append(build_table(highlight_data, col_widths=[3*inch, 3.5*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Regional Performance
    story.append(Paragraph("Regional Performance", heading_style))
    compare_label = f"vs {QUARTER_NAMES[prev_q_metrics['quarter']]}" if prev_q_metrics else "Notes"

    reg_header = ["Region", "Revenue", "% of Total", compare_label, "Key Cities"]

    prev_reg = {r: v for r, v in prev_q_metrics['regions']} if prev_q_metrics else {}
    reg_rows = []
    for region, rev in m['regions']:
        pct = fmt_pct(rev, m['revenue'])
        if prev_q_metrics and region in prev_reg:
            delta = (rev - prev_reg[region]) / prev_reg[region] * 100
            cmp = f"{'+' if delta >= 0 else ''}{delta:.1f}%"
        else:
            cmp = "Baseline"
        cities = REGION_CITY_MAP.get(region, "")
        reg_rows.append([region, fmt_m(rev), pct, cmp, cities])

    story.append(build_table([reg_header] + reg_rows,
                             col_widths=[0.8*inch, 0.9*inch, 0.85*inch, 0.8*inch, 2.65*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Category Breakdown
    story.append(Paragraph("Category Revenue Breakdown", heading_style))
    prev_cat = {c: v for c, v in prev_q_metrics['categories']} if prev_q_metrics else {}
    cat_header = ["Category", "Revenue", "% of Total", compare_label]
    cat_rows = []
    for cat, rev in m['categories']:
        pct = fmt_pct(rev, m['revenue'])
        if prev_q_metrics and cat in prev_cat:
            delta = (rev - prev_cat[cat]) / prev_cat[cat] * 100
            cmp = f"{'+' if delta >= 0 else ''}{delta:.1f}%"
        else:
            cmp = "Baseline"
        cat_rows.append([cat, fmt_m(rev), pct, cmp])

    story.append(build_table([cat_header] + cat_rows,
                             col_widths=[1.8*inch, 1.2*inch, 1.2*inch, 1.8*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Payment Methods
    story.append(Paragraph("Payment Method Distribution", heading_style))
    pay_header = ["Payment Method", "% of Transactions", "Trend"]
    pay_trend = {"Digital Wallet": "↑ Growing", "Credit Card": "→ Stable",
                 "Debit Card": "↓ Declining", "Cash": "↓ Declining"}
    pay_rows = [[pm, f"{pct}%", pay_trend.get(pm, "→ Stable")]
                for pm, _, pct in m['payments']]
    story.append(build_table([pay_header] + pay_rows,
                             col_widths=[2.2*inch, 2*inch, 2*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Top Products
    story.append(Paragraph("Top 5 Products by Revenue", heading_style))
    prod_header = ["Product", "Revenue"]
    prod_rows = [[name, fmt_m(rev)] for name, rev in m['top_products']]
    story.append(build_table([prod_header] + prod_rows, col_widths=[4*inch, 2.2*inch]))
    story.append(Spacer(1, 0.25*inch))

    # Outlook
    story.append(Paragraph(f"Outlook & Next Quarter Priorities", heading_style))
    target_label, target_val, target_note, initiatives = QUARTER_OUTLOOK[q]
    outlook_data = [
        ["Item", "Detail"],
        [target_label, f"{target_val}  ({target_note})"],
        ["Key Initiatives", initiatives],
    ]
    story.append(build_table(outlook_data, col_widths=[2.2*inch, 4*inch]))

    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Confidential – Internal Use Only", small_style))

    doc.build(story)
    print(f"  ✓ {os.path.basename(out_path)}")


def create_investor_presentation(cur, year: int, out_path: str):
    fy = get_full_year(cur, year)
    quarters = [get_quarter_metrics(cur, year, q) for q in range(1, 5)]
    total_rev = fy['revenue']

    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=inch, rightMargin=inch)
    story = []

    # Cover
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("NexusIQ Corporation", subtitle_style))
    story.append(Paragraph("Investor Update – December 2024", title_style))
    story.append(Paragraph("Transforming Retail Through Digital Innovation", subtitle_style))
    story.append(Spacer(1, 0.4*inch))

    # Company Overview
    story.append(Paragraph("Company Overview", heading_style))
    top_payment_fy = fy['payments'][0][0]
    top_payment_pct_fy = fy['payments'][0][1]
    overview_data = [
        ["Attribute", "Detail"],
        ["Who We Are", "Leading regional retailer in Electronics, Home, Clothing, Food, Sports"],
        ["Market Position", "8% North American market share"],
        ["Regions", "West, East, Central, South, North"],
        ["Annual Revenue", f"{fmt_m(total_rev)} ({year} actual)"],
        ["Total Transactions", f"{fy['txns']:,}"],
        ["Digital Payment Lead", f"{top_payment_pct_fy}% {top_payment_fy} adoption (Q4)"],
        ["Customer Satisfaction", "4.6 / 5  vs industry 3.9 / 5"],
    ]
    story.append(build_table(overview_data, col_widths=[2.2*inch, 4*inch]))
    story.append(Spacer(1, 0.2*inch))

    # 2024 Performance Highlights
    story.append(Paragraph("2024 Full-Year Performance", heading_style))

    q4 = quarters[3]
    q4_dw = next((pct for pm, _, pct in q4['payments'] if pm == 'Digital Wallet'), 0)

    perf_data = [
        ["Metric", f"{year} Actual", f"{year} Target", "vs Target"],
        ["Annual Revenue", fmt_m(total_rev), "$155M", f"{(total_rev-155_000_000)/155_000_000*100:+.1f}%"],
        ["Total Transactions", f"{fy['txns']:,}", "92,000", f"{(fy['txns']-92000)/92000*100:+.1f}%"],
        ["Q4 Revenue", fmt_m(q4['revenue']), "$43M", f"{(q4['revenue']-43_000_000)/43_000_000*100:+.1f}%"],
        ["Digital Wallet (Q4)", f"{q4_dw}%", "28%", f"{q4_dw-28:+.1f} pts"],
        ["Customer Satisfaction", "4.6 / 5", "4.4 / 5", "+0.2"],
    ]
    story.append(build_table(perf_data, col_widths=[2.2*inch, 1.4*inch, 1.4*inch, 1.2*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Quarterly Progression
    story.append(Paragraph("2024 Quarterly Revenue Progression", heading_style))
    qtr_data = [
        ["Quarter", "Revenue", "Transactions", "Avg Order", "QoQ Growth"],
        *[
            [
                f"Q{i+1} {year}",
                fmt_m(quarters[i]['revenue']),
                f"{quarters[i]['txns']:,}",
                f"${quarters[i]['avg']:,}",
                f"{(quarters[i]['revenue']-quarters[i-1]['revenue'])/quarters[i-1]['revenue']*100:+.1f}%"
                if i > 0 else "—"
            ]
            for i in range(4)
        ]
    ]
    story.append(build_table(qtr_data, col_widths=[1.1*inch, 1.1*inch, 1.3*inch, 1.1*inch, 1.5*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Category annual breakdown
    story.append(Paragraph("Annual Category Performance", heading_style))
    cat_header = ["Category", "Annual Revenue", "% of Total"]
    cat_rows = [[cat, fmt_m(rev), fmt_pct(rev, total_rev)] for cat, rev in fy['categories']]
    story.append(build_table([cat_header] + cat_rows, col_widths=[2.2*inch, 2*inch, 2*inch]))
    story.append(Spacer(1, 0.2*inch))

    # 2025 Strategic Priorities
    story.append(Paragraph("2025 Strategic Priorities", heading_style))
    priorities = [
        ["Priority", "Investment", "Expected Return"],
        ["West Region Expansion (3 new stores)", "$8.2M", "$15M annual uplift"],
        ["Digital Transformation (e-commerce + mobile)", "$6.5M", "2.5x customer LTV"],
        ["South Region Recovery (marketing + stores)", "$1.2M", "$4M revenue recovery"],
        ["Operational Excellence (supply chain)", "$4.8M", "$1.8M/yr savings"],
    ]
    story.append(build_table(priorities, col_widths=[3*inch, 1.2*inch, 2*inch]))
    story.append(Spacer(1, 0.2*inch))

    # 2025 Financial Outlook
    story.append(Paragraph("2025 Financial Outlook", heading_style))
    outlook = [
        ["Metric", "2024 Actual", "2025 Target", "Growth"],
        ["Revenue", fmt_m(total_rev), "$185M", f"{(185_000_000-total_rev)/total_rev*100:+.1f}%"],
        ["Gross Margin", "36%", "38%", "+2 pts"],
        ["Operating Margin", "23.1%", "23.5%", "+0.4 pts"],
        ["Net Income", f"${float(total_rev)*0.101/1e6:.1f}M", "$18.5M", "+21%"],
        ["Digital Wallet %", f"{q4_dw}% (Q4)", "45%", f"+{45-q4_dw:.1f} pts target"],
    ]
    story.append(build_table(outlook, col_widths=[2.2*inch, 1.4*inch, 1.4*inch, 1.2*inch]))
    story.append(Spacer(1, 0.2*inch))

    # Investment Highlights
    story.append(Paragraph("Investment Highlights", heading_style))
    q4_west_rev = next((r for reg, r in q4['regions'] if reg == 'West'), 0)
    top_cat_fy = fy['categories'][0][0]
    highlights = [
        ["#", "Highlight", "Evidence"],
        ["1", "Digital Payment Leadership",
         f"Q4: {q4_dw}% Digital Wallet vs industry 22%. Early-mover advantage."],
        ["2", "Proven Regional Execution",
         f"West Q4: {fmt_m(q4_west_rev)}. Expansion playbook validated."],
        ["3", "Customer Loyalty",
         "4.6/5 satisfaction. 78% recommend (vs industry 62%)."],
        ["4", "Category Depth",
         f"{top_cat_fy} leads at {fmt_pct(fy['categories'][0][1], total_rev)} of revenue. Margins 28%+."],
        ["5", "Digital Upside",
         "8% online today. Reaching industry 28% adds $40M+ revenue."],
    ]
    story.append(build_table(highlights, col_widths=[0.3*inch, 2*inch, 3.9*inch]))

    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Investor Relations | December 2024  —  Confidential", small_style))

    doc.build(story)
    print(f"  ✓ {os.path.basename(out_path)}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not DB_URL:
        raise RuntimeError(
            "Set DATABASE_URL or NEXUSIQ_FINANCIAL_DB_URL before generating financial PDFs."
        )

    os.makedirs(PDF_DIR, exist_ok=True)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("Reading from:", redact_db_url(DB_URL))
    print("Writing to: ", PDF_DIR)
    print()

    # Pull quarter data once — reused for sequential deltas
    q1 = get_quarter_metrics(cur, 2024, 1)
    q2 = get_quarter_metrics(cur, 2024, 2)
    q3 = get_quarter_metrics(cur, 2024, 3)
    q4 = get_quarter_metrics(cur, 2024, 4)

    print("Generating quarterly reports...")
    create_quarterly_report(cur, 2024, 1, None, os.path.join(PDF_DIR, "06_Q1_2024_Financial_Report.pdf"))
    create_quarterly_report(cur, 2024, 2, q1,   os.path.join(PDF_DIR, "07_Q2_2024_Financial_Report.pdf"))
    create_quarterly_report(cur, 2024, 3, q2,   os.path.join(PDF_DIR, "02_Q3_2024_Financial_Report.pdf"))
    create_quarterly_report(cur, 2024, 4, q3,   os.path.join(PDF_DIR, "01_Q4_2024_Financial_Report.pdf"))

    print("Generating investor presentation...")
    create_investor_presentation(cur, 2024, os.path.join(PDF_DIR, "05_Investor_Presentation_Dec2024.pdf"))

    conn.close()
    print("\nDone. All 5 PDFs regenerated from live DB data.")


if __name__ == "__main__":
    main()
