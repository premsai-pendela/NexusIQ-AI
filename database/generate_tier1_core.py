"""
TIER 1: Core 23 High-Quality PDFs
Production-grade business documents for NexusIQ RAG Agent
Python 3.13 compatible | ChromaDB 1.5.5 | sentence-transformers 5.3.0
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, 
    TableStyle, PageBreak
)
from reportlab.lib import colors
from datetime import datetime
import os

OUTPUT_DIR = "./data/pdfs"

def create_output_dir():
    """Ensure PDF directory exists"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✅ Created directory: {OUTPUT_DIR}")


# ========================================
# CATEGORY 1: FINANCIAL DOCUMENTS (5 PDFs)
# ========================================

def generate_q4_2024_financial_report():
    """Q4 2024 Financial Report - Aligns with SQL database Q4 data"""
    filename = f"{OUTPUT_DIR}/01_Q4_2024_Financial_Report.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=30,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c5282'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("Q4 2024 Financial Report", styles['Heading2']))
    story.append(Paragraph("Report Date: December 31, 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    summary = """
    Q4 2024 marked a transformational quarter for NexusIQ Corporation, with total revenue 
    reaching $45.2M, representing 23% year-over-year growth. Our strategic focus on 
    Electronics and Home categories drove unprecedented market share gains across all regions.
    <br/><br/>
    <b>Key Highlights:</b><br/>
    • Total Transactions: 25,000 (Q4 subset of annual 100K)<br/>
    • Average Transaction Value: $1,808<br/>
    • Digital Wallet adoption increased to 31% of transactions<br/>
    • West region outperformed with 28% revenue growth<br/>
    • Electronics category accounted for 34% of total revenue
    """
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Performance Analysis", heading_style))
    regional = """
    <b>West Region:</b> Exceeded targets with $12.8M revenue (28.3% of total). 
    Electronics sales surged 45% compared to Q3 2024. Seattle and Portland stores 
    drove growth with premium product mix.
    <br/><br/>
    <b>East Region:</b> Delivered $10.5M (23.2%). New York and Boston stores showed 
    resilience. Clothing category growth of 18% offset slower Electronics sales.
    <br/><br/>
    <b>Central Region:</b> Generated $9.2M (20.4%). Chicago and Dallas benefited 
    from holiday promotions. Digital Wallet penetration highest at 38%.
    <br/><br/>
    <b>South Region:</b> Contributed $7.8M (17.3%). Miami flagship underperformed 
    due to weather disruptions. Recovery plan initiated for Q1 2025.
    <br/><br/>
    <b>North Region:</b> $4.9M (10.8%). Smallest region but highest growth rate 
    at 31% YoY. Home category dominated with 42% of regional sales.
    """
    story.append(Paragraph(regional, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Category Revenue Breakdown", heading_style))
    category_data = [
        ['Category', 'Q4 Revenue', '% of Total', 'YoY Growth'],
        ['Electronics', '$15.4M', '34.1%', '+27%'],
        ['Home', '$11.2M', '24.8%', '+19%'],
        ['Clothing', '$9.8M', '21.7%', '+15%'],
        ['Food', '$5.6M', '12.4%', '+8%'],
        ['Sports', '$3.2M', '7.1%', '+22%'],
    ]
    
    t = Table(category_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Payment Method Trends", heading_style))
    payment = """
    Digital transformation accelerated in Q4 2024:<br/>
    • <b>Digital Wallet:</b> 31% of transactions (up from 24% in Q3)<br/>
    • <b>Credit Card:</b> 28% (stable)<br/>
    • <b>Debit Card:</b> 26% (down from 30%)<br/>
    • <b>Cash:</b> 15% (declining trend continues)
    <br/><br/>
    Recommendation: Expand Digital Wallet partnerships to capture younger demographics. 
    Cash transactions concentrated in Food category - opportunity for incentivized digital adoption.
    """
    story.append(Paragraph(payment, styles['Normal']))
    
    story.append(PageBreak())
    story.append(Paragraph("Strategic Initiatives for 2025", heading_style))
    initiatives = """
    <b>1. Premium Electronics Expansion</b><br/>
    West region Electronics surge (45%) justifies premium product line. 
    Projected incremental revenue: $8M annually.
    <br/><br/>
    <b>2. South Region Recovery Plan</b><br/>
    Targeted marketing and promotional offers. Budget allocated: $1.2M for Q1-Q2 2025.
    <br/><br/>
    <b>3. Digital-First Customer Experience</b><br/>
    Increase Digital Wallet adoption target to 45% by Q4 2025. Loyalty rewards 
    and exclusive discounts for digital payments.
    <br/><br/>
    <b>4. Home Category Innovation</b><br/>
    Leverage North region's 42% Home share as model. Pilot smart home product bundles Q1 2025.
    """
    story.append(Paragraph(initiatives, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2025 Financial Outlook", heading_style))
    outlook = """
    Based on Q4 momentum and strategic initiatives, we project:<br/>
    • <b>Full Year 2025 Revenue:</b> $195M - $205M (15-20% growth)<br/>
    • <b>Target Transaction Volume:</b> 115,000 transactions<br/>
    • <b>Average Transaction Value:</b> $1,750<br/>
    • <b>Operating Margin:</b> 22-24%
    """
    story.append(Paragraph(outlook, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Confidential - Internal Use Only | Page 1-2", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


def generate_q3_2024_financial_report():
    """Q3 2024 Financial Report - For temporal comparison queries"""
    filename = f"{OUTPUT_DIR}/02_Q3_2024_Financial_Report.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
        fontSize=24, textColor=colors.HexColor('#1a365d'), spaceAfter=30, alignment=1)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#2c5282'), spaceAfter=12, spaceBefore=12)
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("Q3 2024 Financial Report", styles['Heading2']))
    story.append(Paragraph("Report Date: September 30, 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    summary = """
    Q3 2024 showed steady growth with total revenue of $38.7M, up 18% year-over-year. 
    Back-to-school season drove strong Electronics and Clothing performance.
    <br/><br/>
    <b>Key Highlights:</b><br/>
    • Total Transactions: 23,500<br/>
    • Average Transaction Value: $1,647<br/>
    • Digital Wallet adoption: 24% of transactions<br/>
    • West region led with $10.2M revenue<br/>
    • Electronics category: 31% of total revenue
    """
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Performance vs Q2", heading_style))
    regional = """
    <b>West:</b> $10.2M (26.4% of total), +12% from Q2. Seattle store became top performer.
    <br/><br/>
    <b>East:</b> $9.1M (23.5%), +8% from Q2. Boston back-to-school promotions exceeded expectations.
    <br/><br/>
    <b>Central:</b> $8.5M (22.0%), +15% from Q2. Chicago expansion paying off.
    <br/><br/>
    <b>South:</b> $7.2M (18.6%), +6% from Q2. Hurricane season disruptions in September.
    <br/><br/>
    <b>North:</b> $3.7M (9.6%), +22% from Q2. Consistent outperformance.
    """
    story.append(Paragraph(regional, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Category Performance", heading_style))
    cat_data = [
        ['Category', 'Q3 Revenue', '% of Total', 'vs Q2'],
        ['Electronics', '$12.0M', '31.0%', '+15%'],
        ['Clothing', '$9.3M', '24.0%', '+25%'],
        ['Home', '$9.1M', '23.5%', '+10%'],
        ['Food', '$5.2M', '13.4%', '+5%'],
        ['Sports', '$3.1M', '8.0%', '+18%'],
    ]
    
    t = Table(cat_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Payment Trends", heading_style))
    payment = """
    Digital payment adoption continues:<br/>
    • Digital Wallet: 24% (up from 20% in Q2)<br/>
    • Credit Card: 29%<br/>
    • Debit Card: 30%<br/>
    • Cash: 17%
    <br/><br/>
    Notable: West and Central regions show 30%+ Digital Wallet usage, while South lags at 14%.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Q4 Outlook and Preparations", heading_style))
    outlook = """
    <b>Holiday Season Readiness:</b><br/>
    Inventory increased 35% in Electronics and Home for Q4 demand. Early promotional 
    calendar finalized for Black Friday through New Year's.
    <br/><br/>
    <b>Staffing:</b> Hired 200 seasonal employees. Training completed on new POS systems 
    and Digital Wallet programs.
    <br/><br/>
    <b>Q4 Revenue Target:</b> $42M - $46M (25-30% of annual revenue)
    """
    story.append(Paragraph(outlook, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Confidential - Internal Use Only | Page 1-2", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


def generate_annual_report_2023():
    """Annual Report 2023 - Historical context for YoY comparisons"""
    filename = f"{OUTPUT_DIR}/03_Annual_Report_2023.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
        fontSize=24, textColor=colors.HexColor('#1a365d'), spaceAfter=30, alignment=1)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#2c5282'), spaceAfter=12, spaceBefore=12)
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("2023 Annual Report", styles['Heading2']))
    story.append(Paragraph("Fiscal Year Ended December 31, 2023", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Letter from the CEO", heading_style))
    ceo = """
    Dear Shareholders,
    <br/><br/>
    2023 was a year of strategic transformation for NexusIQ Corporation. We achieved 
    $152M in revenue, growing 15% year-over-year despite challenging macroeconomic conditions.
    <br/><br/>
    Our Digital Wallet pilot, launched Q2 2023, now represents 18% of transactions—
    exceeding our year-end target of 15%. This positions us ahead of industry trends.
    <br/><br/>
    Looking to 2024, we will double down on regional expansion, particularly in the 
    high-performing West region, while implementing recovery plans for underperforming markets.
    <br/><br/>
    <i>Michael J. Patterson, Chief Executive Officer</i>
    """
    story.append(Paragraph(ceo, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2023 Financial Highlights", heading_style))
    fin_data = [
        ['Metric', '2023', '2022', 'Change'],
        ['Total Revenue', '$152.0M', '$132.1M', '+15.1%'],
        ['Gross Profit', '$54.7M', '$46.2M', '+18.4%'],
        ['Operating Income', '$18.2M', '$14.8M', '+23.0%'],
        ['Net Income', '$12.8M', '$10.1M', '+26.7%'],
        ['Transactions', '95,000', '87,500', '+8.6%'],
        ['Avg Transaction', '$1,600', '$1,510', '+6.0%'],
    ]
    
    t = Table(fin_data, colWidths=[2.2*inch, 1.4*inch, 1.4*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Distribution (2023)", heading_style))
    regional = """
    Five-region structure delivered balanced growth:<br/>
    • <b>West:</b> $39.5M (26.0%) - Strongest performer<br/>
    • <b>East:</b> $35.7M (23.5%) - Stable, mature market<br/>
    • <b>Central:</b> $32.3M (21.2%) - Emerging growth<br/>
    • <b>South:</b> $29.6M (19.5%) - Recovery focus needed<br/>
    • <b>North:</b> $14.9M (9.8%) - Small but growing
    """
    story.append(Paragraph(regional, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Strategic Priorities for 2024", heading_style))
    priorities = """
    <b>1. Digital Transformation Acceleration</b><br/>
    Target: 30% Digital Wallet adoption by end 2024. Launch mobile app with loyalty program.
    <br/><br/>
    <b>2. West Region Expansion</b><br/>
    Open 3 new stores (San Diego, San Francisco, Las Vegas). Expected revenue: $12M annually.
    <br/><br/>
    <b>3. Category Mix Optimization</b><br/>
    Expand Electronics premium tier (28% margin vs 22% average). Pilot smart home bundles.
    <br/><br/>
    <b>4. South Region Turnaround</b><br/>
    Targeted promotions and inventory management. Goal: 12%+ growth rates.
    """
    story.append(Paragraph(priorities, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market Position", heading_style))
    market = """
    NexusIQ holds 8% share of North American retail electronics/home goods market.
    <br/><br/>
    <b>Competitive Advantages:</b><br/>
    • Customer satisfaction: 4.4/5 vs industry 3.7/5<br/>
    • Payment flexibility: Leading Digital Wallet integration<br/>
    • Regional expertise in core territories
    <br/><br/>
    <b>Areas for Improvement:</b><br/>
    • Online presence: 8% of sales vs industry 28%<br/>
    • Supply chain: 15-day inventory turns vs best-in-class 22 days
    """
    story.append(Paragraph(market, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("2023 Annual Report | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


def generate_budget_forecast_2025():
    """Budget Forecast 2025 - Forward-looking planning"""
    filename = f"{OUTPUT_DIR}/04_Budget_Forecast_2025.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
        fontSize=24, textColor=colors.HexColor('#1a365d'), spaceAfter=30, alignment=1)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#2c5282'), spaceAfter=12, spaceBefore=12)
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("2025 Budget Forecast & Financial Plan", styles['Heading2']))
    story.append(Paragraph("Approved: Board Meeting January 15, 2025", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    summary = """
    2025 budget allocates $42.3M across strategic initiatives targeting 18-22% revenue growth. 
    Key investments in digital transformation, regional expansion, and operational efficiency.
    <br/><br/>
    <b>Revenue Target:</b> $195M - $205M (baseline: $200M)<br/>
    <b>Operating Margin:</b> 22-24%<br/>
    <b>Capital Expenditure:</b> $18.5M<br/>
    <b>Operating Expenditure:</b> $23.8M
    """
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Budget Allocation by Initiative", heading_style))
    budget_data = [
        ['Initiative', 'Budget', '% Total', 'Expected ROI'],
        ['West Region Expansion', '$8.2M', '19.4%', '$15M incremental revenue'],
        ['Digital Transformation', '$6.5M', '15.4%', '2.5x customer LTV'],
        ['South Region Recovery', '$1.2M', '2.8%', '$4M revenue recovery'],
        ['Supply Chain Optimization', '$4.8M', '11.3%', '25% inventory improvement'],
        ['Technology Infrastructure', '$5.6M', '13.2%', '$2.1M/year cost avoid'],
        ['Marketing & Promotions', '$7.4M', '17.5%', '15% customer acquisition'],
        ['Employee Training', '$2.1M', '5.0%', '+12% productivity'],
        ['Store Renovations', '$3.8M', '9.0%', '8-10% sales lift'],
        ['Contingency Reserve', '$2.7M', '6.4%', 'Risk mitigation'],
    ]
    
    t = Table(budget_data, colWidths=[2.1*inch, 1.1*inch, 1.1*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Detailed Breakdown", heading_style))
    
    story.append(Paragraph("<b>West Region Expansion ($8.2M)</b>", styles['Normal']))
    west = """
    • New stores: San Diego ($3.1M), San Francisco ($3.5M), Las Vegas ($1.6M)<br/>
    • Real estate deposits and lease agreements<br/>
    • Initial inventory stocking (Electronics premium tier)<br/>
    • Staff recruitment: 45 new employees<br/>
    <b>Timeline:</b> SD (Mar), SF (Jun), LV (Sep) | <b>Payback:</b> 18-24 months
    """
    story.append(Paragraph(west, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Digital Transformation ($6.5M)</b>", styles['Normal']))
    digital = """
    • E-commerce platform: $3.2M<br/>
    • Mobile app + loyalty: $1.8M<br/>
    • Digital Wallet campaigns: $0.9M<br/>
    • AI recommendation engine: $0.6M
    <br/><br/>
    <b>Targets:</b> 45% Digital Wallet adoption | 18% online sales | 25% retention improvement
    """
    story.append(Paragraph(digital, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("<b>South Region Recovery ($1.2M)</b>", styles['Normal']))
    south = """
    Addressing Q4 2024 underperformance (17.3% vs 21% target):<br/>
    • Marketing campaigns: $0.5M<br/>
    • Store refresh: $0.4M<br/>
    • Local partnerships: $0.2M<br/>
    • Staff incentives: $0.1M
    <br/><br/>
    <b>Success Criteria:</b> Q2: 8%+ growth | Q4: 20% revenue contribution | Satisfaction: 4.1→4.4
    """
    story.append(Paragraph(south, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Quarterly Budget Phasing", heading_style))
    quarterly_data = [
        ['Quarter', 'CapEx', 'OpEx', 'Total', 'Expected Revenue'],
        ['Q1 2025', '$5.2M', '$5.8M', '$11.0M', '$42M'],
        ['Q2 2025', '$6.1M', '$6.2M', '$12.3M', '$48M'],
        ['Q3 2025', '$4.8M', '$6.1M', '$10.9M', '$52M'],
        ['Q4 2025', '$2.4M', '$5.7M', '$8.1M', '$58M'],
        ['Total 2025', '$18.5M', '$23.8M', '$42.3M', '$200M'],
    ]
    
    t = Table(quarterly_data, colWidths=[1.3*inch, 1.3*inch, 1.3*inch, 1.3*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4e6f1')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Risk Factors & Mitigation", heading_style))
    risk = """
    <b>Risk 1:</b> Economic downturn → 6.4% contingency reserve, defer Q3/Q4 stores<br/>
    <b>Risk 2:</b> Digital platform delays → Phased MVP launch (Q2 core, Q4 full)<br/>
    <b>Risk 3:</b> Supplier constraints → TechVendor contract flexibility clause<br/>
    <b>Risk 4:</b> South execution → Monthly reviews, pivot if Q2 targets missed
    """
    story.append(Paragraph(risk, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("2025 Budget Forecast | Confidential - Board Approved", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


def generate_investor_presentation():
    """Investor Presentation Dec 2024 - Executive summary"""
    filename = f"{OUTPUT_DIR}/05_Investor_Presentation_Dec2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
        fontSize=28, textColor=colors.HexColor('#1a365d'), spaceAfter=30, alignment=1)
    slide_title = ParagraphStyle('SlideTitle', parent=styles['Heading2'],
        fontSize=18, textColor=colors.HexColor('#2c5282'), spaceAfter=20, alignment=1,
        borderWidth=2, borderColor=colors.HexColor('#2c5282'), borderPadding=10)
    
    # Slide 1
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("Investor Update - December 2024", styles['Heading2']))
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph("<i>Transforming Retail Through Digital Innovation</i>", styles['Italic']))
    story.append(PageBreak())
    
    # Slide 2
    story.append(Paragraph("Company Overview", slide_title))
    story.append(Spacer(1, 0.3*inch))
    overview = """
    <b>Who We Are:</b> Leading regional retailer in Electronics, Home, Clothing, Food, Sports
    <br/><br/>
    <b>Market Position:</b> 8% North American market share<br/>
    <b>Regions:</b> West, East, Central, South, North<br/>
    <b>Annual Revenue:</b> $170M+ (2024 est.)<br/>
    <b>Customer Satisfaction:</b> 4.6/5 vs industry 3.9/5
    <br/><br/>
    <b>Competitive Advantages:</b><br/>
    • Digital payment leadership (31% Digital Wallet)<br/>
    • Regional expertise<br/>
    • Premium product mix (28% Electronics margins)
    """
    story.append(Paragraph(overview, styles['Normal']))
    story.append(PageBreak())
    
    # Slide 3
    story.append(Paragraph("2024 Performance Highlights", slide_title))
    story.append(Spacer(1, 0.3*inch))
    
    perf_data = [
        ['Metric', '2024 Actual', '2024 Target', 'vs Target'],
        ['Revenue', '$170M', '$165M', '+3.0%'],
        ['Operating Margin', '23.1%', '22.0%', '+1.1 pts'],
        ['Transactions', '100,000', '98,000', '+2.0%'],
        ['Digital Wallet %', '31%', '25%', '+6 pts'],
        ['Satisfaction', '4.6/5', '4.4/5', '+0.2'],
    ]
    
    t = Table(perf_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    highlights = """
    <b>Key Wins:</b><br/>
    ✅ Revenue +$5M vs target | ✅ Digital Wallet +24% vs plan<br/>
    ✅ West region 28% growth | ✅ Electronics margin expansion 28%
    """
    story.append(Paragraph(highlights, styles['Normal']))
    story.append(PageBreak())
    
    # Slide 4
    story.append(Paragraph("2025 Strategic Priorities", slide_title))
    story.append(Spacer(1, 0.3*inch))
    priorities = """
    <b>1. West Region Expansion</b> ($8.2M → $15M return)<br/>
    3 new stores: San Diego, San Francisco, Las Vegas
    <br/><br/>
    <b>2. Digital Transformation</b> ($6.5M → 2.5x customer LTV)<br/>
    E-commerce platform Q2, mobile app, 18% online sales target
    <br/><br/>
    <b>3. South Region Recovery</b> ($1.2M → $4M recovery)<br/>
    Marketing + store improvements, 17.3% → 20% contribution
    <br/><br/>
    <b>4. Operational Excellence</b> ($4.8M → $1.8M/yr savings)<br/>
    Supply chain optimization, inventory turns 15 → 22 days
    """
    story.append(Paragraph(priorities, styles['Normal']))
    story.append(PageBreak())
    
    # Slide 5
    story.append(Paragraph("2025 Financial Outlook", slide_title))
    story.append(Spacer(1, 0.3*inch))
    
    outlook_data = [
        ['Metric', '2024', '2025 Target', 'Growth'],
        ['Revenue', '$170M', '$200M', '+17.6%'],
        ['Gross Margin', '36%', '38%', '+2 pts'],
        ['Operating Margin', '23.1%', '23.5%', '+0.4 pts'],
        ['Net Income', '$15.2M', '$18.5M', '+21.7%'],
        ['EPS', '$1.52', '$1.85', '+21.7%'],
    ]
    
    t = Table(outlook_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    assumptions = """
    <b>Assumptions:</b> Stable economy, on-time store launches, 15% e-commerce contribution, 
    45% Digital Wallet adoption<br/>
    <b>Risks:</b> See Budget Forecast document for mitigation strategies
    """
    story.append(Paragraph(assumptions, styles['Normal']))
    story.append(PageBreak())
    
    # Slide 6
    story.append(Paragraph("Investment Highlights", slide_title))
    story.append(Spacer(1, 0.3*inch))
    investment = """
    <b>1. Digital Payment Leadership</b><br/>
    31% Digital Wallet vs industry 22%. Early mover advantage.
    <br/><br/>
    <b>2. Proven Regional Execution</b><br/>
    West delivers 28% growth. Expansion playbook ready.
    <br/><br/>
    <b>3. Customer Loyalty</b><br/>
    4.6/5 satisfaction. 78% would recommend (vs industry 62%).
    <br/><br/>
    <b>4. Strong Unit Economics</b><br/>
    23% operating margins. Best-in-class regional retailer.
    <br/><br/>
    <b>5. Digital Transformation Upside</b><br/>
    8% online sales today. Reaching industry 28% adds $40M+ revenue.
    """
    story.append(Paragraph(investment, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Investor Relations | December 2024", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 1 Core PDFs (23 total)"""
    print("\n" + "="*70)
    print("📄 TIER 1: Generating 23 Core High-Quality PDFs")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 CATEGORY 1: Financial Documents (5 PDFs)")
    generate_q4_2024_financial_report()
    generate_q3_2024_financial_report()
    generate_annual_report_2023()
    generate_budget_forecast_2025()
    generate_investor_presentation()
    
    print("\n✅ Financial documents complete (5/23)")
    print("\n📊 Progress: 21.7% | Remaining: 18 PDFs")
    print("\nNext: Run Part 2 for Market Intelligence + other categories")


if __name__ == "__main__":
    main()
