# scripts/generate_sample_pdfs.py
"""
Generate realistic business PDF documents for RAG Agent testing.
Creates 8 diverse business documents with realistic content.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime
import os

# Ensure data/pdfs directory exists
os.makedirs("data/pdfs", exist_ok=True)

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor=colors.HexColor('#1f77b4'),
    spaceAfter=30,
    alignment=1  # Center
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=14,
    textColor=colors.HexColor('#2c3e50'),
    spaceAfter=12,
    spaceBefore=12
)


# ════════════════════════════════════════════════════════════
#  DOCUMENT 1: Q4 2024 Sales Performance Report
# ════════════════════════════════════════════════════════════

def create_q4_sales_report():
    """Quarterly sales report with regional breakdowns"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Q4_2024_Sales_Report.pdf",
        pagesize=letter,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Q4 2024 Sales Performance Report", title_style))
    story.append(Paragraph("NexusIQ Corporation", styles['Heading3']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph("""
        Q4 2024 exceeded expectations with total revenue of $42.3M, representing a 23% year-over-year 
        growth. The Electronics category led performance with $18.7M in sales, while the West region 
        emerged as our strongest market with $12.1M in revenue. Digital wallet adoption surged to 34% 
        of all transactions, indicating successful implementation of our contactless payment initiative.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    # Regional Performance
    story.append(Paragraph("Regional Performance Breakdown", heading_style))
    
    regional_data = [
        ['Region', 'Revenue', 'Growth YoY', 'Top Category'],
        ['West', '$12.1M', '+28%', 'Electronics'],
        ['East', '$9.8M', '+19%', 'Clothing'],
        ['Central', '$8.9M', '+21%', 'Home'],
        ['South', '$6.2M', '+24%', 'Food'],
        ['North', '$5.3M', '+18%', 'Sports']
    ]
    
    table = Table(regional_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*inch))
    
    # Category Analysis
    story.append(Paragraph("Product Category Analysis", heading_style))
    story.append(Paragraph("""
        <b>Electronics ($18.7M, 44% of total):</b> Smartphones and laptops drove 67% of electronics 
        revenue. Premium tier products (>$500) showed 31% growth, while budget tier declined 8%.
        <br/><br/>
        <b>Clothing ($9.2M, 22% of total):</b> Seasonal winter collection outperformed summer by 42%. 
        Online sales represented 61% of clothing revenue, up from 48% in Q3.
        <br/><br/>
        <b>Home ($7.1M, 17% of total):</b> Smart home devices category launched in October contributed 
        $1.9M. Furniture and décor segments remained stable with modest 6% growth.
        <br/><br/>
        <b>Food ($4.8M, 11% of total):</b> Organic product line expansion resulted in 29% category 
        growth. Subscription meal kits reached 12,000 active subscribers.
        <br/><br/>
        <b>Sports ($2.5M, 6% of total):</b> Fitness equipment sales surged 47% following Q4 marketing 
        campaign. Team sports equipment declined 12% seasonally.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    # Payment Trends
    story.append(Paragraph("Payment Method Trends", heading_style))
    story.append(Paragraph("""
        Digital wallet adoption reached 34% of transactions (up from 22% in Q3), driven by our 
        5% cashback promotion. Credit card usage declined to 38% (from 45%), while debit card 
        remained stable at 19%. Cash transactions decreased to 9%, lowest on record.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    # Strategic Recommendations
    story.append(Paragraph("Strategic Recommendations for Q1 2025", heading_style))
    story.append(Paragraph("""
        1. <b>Expand Electronics Inventory:</b> Increase premium smartphone SKUs by 25% given 
        strong demand and 31% growth trajectory.
        <br/><br/>
        2. <b>Double Down on Digital Wallets:</b> Extend cashback promotion through Q1 to 
        accelerate adoption toward 50% target.
        <br/><br/>
        3. <b>Strengthen East Region Presence:</b> Open 3 additional stores in East region 
        to capitalize on 19% growth momentum.
        <br/><br/>
        4. <b>Optimize Sports Category:</b> Reduce team sports inventory by 20% during Q1-Q2 
        off-season, reallocate budget to fitness equipment.
        <br/><br/>
        5. <b>Launch Clothing Subscription Service:</b> Replicate food subscription success 
        with quarterly fashion box service targeting online customer base.
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Q4_2024_Sales_Report.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 2: Competitor Analysis - MarketPulse
# ════════════════════════════════════════════════════════════

def create_competitor_analysis():
    """Market research on top 3 competitors"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Competitor_Analysis_2024.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("Competitive Landscape Analysis 2024", title_style))
    story.append(Paragraph("MarketPulse Research Division", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market Overview", heading_style))
    story.append(Paragraph("""
        The retail landscape has consolidated around three major players: TechMart (32% market share), 
        ValueHub (28% market share), and our company NexusIQ (24% market share). The remaining 16% 
        is fragmented across regional players. Total addressable market grew 14% to $182B in 2024.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Competitor 1: TechMart (Market Leader)", heading_style))
    story.append(Paragraph("""
        <b>Strengths:</b>
        • Dominant in Electronics (47% category share) with exclusive supplier partnerships
        • Superior logistics network enables 24-hour delivery in 89% of US zip codes
        • Loyalty program has 28M active members (vs our 14M)
        • AI-powered recommendation engine drives 41% of sales
        <br/><br/>
        <b>Weaknesses:</b>
        • Premium pricing strategy limits budget-conscious segment penetration
        • Customer service satisfaction scores declined to 3.2/5 (industry avg 3.8/5)
        • Recent data breach affected 2.1M customers, damaged brand trust
        • Limited physical store presence (87 locations vs our 312)
        <br/><br/>
        <b>Recent Moves:</b>
        • Acquired DroneDeliver Inc for $1.2B to pilot drone delivery
        • Launched TechMart Pay (digital wallet) with 2% cashback
        • Opened 4 flagship "experience centers" in major metros
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Competitor 2: ValueHub (Price Leader)", heading_style))
    story.append(Paragraph("""
        <b>Strengths:</b>
        • Aggressive pricing: average 12% below market on comparable products
        • Strong private label portfolio (34% of sales vs our 8%)
        • Excellent inventory turnover (8.2x annually vs our 6.1x)
        • Rapid store expansion: opened 47 new locations in 2024
        <br/><br/>
        <b>Weaknesses:</b>
        • Product quality perception issues (42% of reviews mention "cheap feel")
        • Weak online presence: e-commerce only 18% of revenue vs our 34%
        • Limited product selection in premium categories
        • High employee turnover (31% annually) impacts service quality
        <br/><br/>
        <b>Recent Moves:</b>
        • Partnered with Instacart for same-day grocery delivery
        • Launched "ValueHub Pro" subscription ($49/year) with free shipping
        • Testing autonomous checkout technology in 12 pilot stores
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Strategic Gaps & Opportunities for NexusIQ", heading_style))
    story.append(Paragraph("""
        <b>Opportunity 1 - Omnichannel Excellence:</b> Neither competitor effectively bridges online 
        and offline. Our 312 stores + robust e-commerce platform positions us to dominate "buy online, 
        pick up in store" segment (currently only 8% market penetration).
        <br/><br/>
        <b>Opportunity 2 - Mid-Market Sweet Spot:</b> Gap exists between TechMart's premium positioning 
        and ValueHub's budget focus. Our quality-at-fair-price strategy can capture the underserved 
        middle 40% of customers.
        <br/><br/>
        <b>Opportunity 3 - Customer Experience:</b> With TechMart's service decline and ValueHub's 
        quality issues, investing in superior customer experience can drive differentiation. Target 
        4.5/5 satisfaction score.
        <br/><br/>
        <b>Opportunity 4 - Private Label Growth:</b> Our 8% private label penetration has significant 
        runway. Expanding to 20% (halfway to ValueHub's 34%) could improve margins by 4-6 percentage points.
        <br/><br/>
        <b>Threat - Digital Wallet Wars:</b> TechMart Pay's 2% cashback vs our 5% suggests they're 
        willing to operate at loss to gain market share. Monitor competitive intensity and adjust 
        promotion strategy accordingly to avoid unsustainable cashback arms race.
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Competitor_Analysis_2024.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 3: Customer Satisfaction Survey Results
# ════════════════════════════════════════════════════════════

def create_customer_survey():
    """Customer satisfaction and NPS analysis"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Customer_Survey_Report_2024.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("2024 Annual Customer Satisfaction Survey", title_style))
    story.append(Paragraph("Response Rate: 18,429 customers (12% of active base)", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Net Promoter Score (NPS)", heading_style))
    story.append(Paragraph("""
        <b>Overall NPS: 42</b> (Industry Average: 38)
        <br/>
        Promoters (9-10 rating): 58%
        <br/>
        Passives (7-8 rating): 26%
        <br/>
        Detractors (0-6 rating): 16%
        <br/><br/>
        Year-over-year improvement of +7 points driven by faster shipping (NPS +12) and improved 
        product availability (NPS +9). Customer service NPS declined -3 points due to longer wait 
        times during peak holiday season.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Top Satisfaction Drivers (What We're Doing Right)", heading_style))
    story.append(Paragraph("""
        1. <b>Product Quality (4.6/5):</b> 87% of customers rated product quality as "excellent" 
        or "very good". Electronics and Home categories scored highest at 4.7/5.
        <br/><br/>
        2. <b>Pricing Competitiveness (4.4/5):</b> 79% agree prices are "fair" or "better than 
        competitors". Price-match guarantee mentioned in 34% of positive reviews.
        <br/><br/>
        3. <b>Store Cleanliness & Layout (4.5/5):</b> Physical stores scored 91% on cleanliness. 
        Customers appreciate wide aisles and clear signage (mentioned in 42% of store visit feedback).
        <br/><br/>
        4. <b>Easy Returns Process (4.3/5):</b> 30-day return policy with no-questions-asked approach 
        drives loyalty. 88% of customers who made returns rated the process as "hassle-free".
        <br/><br/>
        5. <b>Website Usability (4.2/5):</b> Recent redesign improved navigation scores from 3.8 to 
        4.2. Mobile app usage grew 34% with 4.4/5 rating.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Top Pain Points (Where We're Falling Short)", heading_style))
    story.append(Paragraph("""
        1. <b>Customer Service Wait Times (2.9/5):</b> Average hold time of 8.7 minutes (target: 
        <3 minutes). 64% of detractors cited "long wait for support" as primary frustration.
        <br/><br/>
        2. <b>Out-of-Stock Issues (3.1/5):</b> 23% of customers encountered out-of-stock products 
        in past 6 months. Electronics category had worst availability at 18% stockout rate.
        <br/><br/>
        3. <b>Checkout Speed In-Store (3.4/5):</b> Average wait time of 4.2 minutes during peak hours. 
        Self-checkout lanes helped but only available in 67% of stores.
        <br/><br/>
        4. <b>Delivery Time Communication (3.2/5):</b> 31% of customers complained about "vague 
        delivery windows". Want real-time tracking like Amazon provides.
        <br/><br/>
        5. <b>Limited Product Selection in Sports (3.3/5):</b> Customers compare unfavorably to 
        specialty sports retailers. Request for more premium athletic brand partnerships.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Demographic Insights", heading_style))
    story.append(Paragraph("""
        <b>Age Segmentation:</b>
        • 18-34 (Gen Z/Millennial): 38% of customers, NPS 51 (highest), prefer mobile app (72% usage)
        • 35-54 (Gen X): 41% of customers, NPS 42, balanced online/offline (54% online)
        • 55+ (Boomer+): 21% of customers, NPS 31 (lowest), prefer in-store (68% of purchases)
        <br/><br/>
        <b>Regional Differences:</b>
        • West region: NPS 48 (highest) - correlates with newer store formats and faster delivery
        • East region: NPS 43 - strong digital wallet adoption helps
        • Central region: NPS 39 - older stores need renovation (avg age 12 years)
        • South region: NPS 38 - limited product selection cited frequently
        • North region: NPS 35 (lowest) - harsh winters impact delivery reliability
        <br/><br/>
        <b>Spending Tier Analysis:</b>
        • High-value customers (>$2,500/year): NPS 62, want premium loyalty perks
        • Mid-value customers ($500-$2,500/year): NPS 41, price-sensitive, value promotions
        • Low-value customers (<$500/year): NPS 28, high churn risk, need engagement programs
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Action Items for 2025", heading_style))
    story.append(Paragraph("""
        <b>Priority 1 - Fix Customer Service:</b> Hire 120 additional support agents to reduce 
        hold time to <3 minutes. Implement AI chatbot for FAQ handling (target: resolve 40% of 
        inquiries without human agent).
        <br/><br/>
        <b>Priority 2 - Improve Inventory Management:</b> Deploy predictive analytics to reduce 
        stockouts by 50%. Focus on Electronics category first given highest customer impact.
        <br/><br/>
        <b>Priority 3 - Modernize North & Central Stores:</b> Allocate $12M capex to renovate 
        28 oldest stores. Add self-checkout, update layouts, improve lighting.
        <br/><br/>
        <b>Priority 4 - Enhance Delivery Tracking:</b> Partner with logistics provider to enable 
        real-time GPS tracking. Send proactive SMS updates at 3 milestones (shipped, out for delivery, 
        delivered).
        <br/><br/>
        <b>Priority 5 - Launch Premium Loyalty Tier:</b> Create "NexusIQ Elite" for high-value 
        customers: dedicated support line, early access to sales, free expedited shipping, exclusive 
        events. Target 15% of high-value segment enrollment.
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Customer_Survey_Report_2024.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 4: Supplier Contract - TechSource Electronics
# ════════════════════════════════════════════════════════════

def create_supplier_contract():
    """Sample supplier agreement with pricing terms"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Supplier_Contract_TechSource.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("MASTER SUPPLY AGREEMENT", title_style))
    story.append(Paragraph("Between NexusIQ Corporation and TechSource Electronics Ltd.", styles['Normal']))
    story.append(Paragraph("Effective Date: January 1, 2024 | Contract Term: 3 Years", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. Product Categories & Pricing", heading_style))
    story.append(Paragraph("""
        <b>1.1 Smartphones:</b>
        • Premium tier (>$800 retail): Wholesale price = 62% of MSRP, minimum order 500 units/month
        • Mid-tier ($400-$800): Wholesale price = 68% of MSRP, minimum order 1,000 units/month
        • Budget tier (<$400): Wholesale price = 74% of MSRP, minimum order 1,500 units/month
        <br/><br/>
        <b>1.2 Laptops & Tablets:</b>
        • Business-grade laptops: Wholesale price = 65% of MSRP, minimum order 300 units/month
        • Consumer laptops: Wholesale price = 70% of MSRP, minimum order 600 units/month
        • Tablets: Wholesale price = 72% of MSRP, minimum order 400 units/month
        <br/><br/>
        <b>1.3 Accessories (cables, chargers, cases):</b>
        • Wholesale price = 58% of MSRP (higher margin category)
        • No minimum order quantity
        • Bundling discounts: 5% additional discount when purchased with devices
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("2. Volume Incentives", heading_style))
    story.append(Paragraph("""
        <b>Tier 1:</b> $5M - $10M quarterly spend → 2% rebate on total purchases
        <br/>
        <b>Tier 2:</b> $10M - $20M quarterly spend → 3.5% rebate + priority allocation during shortages
        <br/>
        <b>Tier 3:</b> >$20M quarterly spend → 5% rebate + co-marketing fund ($200K/quarter) + 
        exclusive SKUs
        <br/><br/>
        Current Status: NexusIQ qualified for Tier 3 in Q3 2024 with $23.7M spend.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("3. Payment Terms", heading_style))
    story.append(Paragraph("""
        • Standard: Net 45 days from invoice date
        • Early payment discount: 2% if paid within 10 days
        • Payment method: ACH transfer to TechSource account #4782-9912-3301
        • Late payment penalty: 1.5% monthly interest on overdue balances
        • Credit limit: $8M (reviewed quarterly)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("4. Delivery & Logistics", heading_style))
    story.append(Paragraph("""
        • Lead time: 14-21 business days from PO submission
        • Expedited orders: 7-10 business days (5% surcharge applies)
        • Shipping: FOB Origin (NexusIQ responsible for freight costs from TechSource warehouse)
        • Delivery to NexusIQ regional distribution centers (Seattle, Chicago, Atlanta, Dallas, Boston)
        • TechSource retains title until payment received
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("5. Quality & Warranty", heading_style))
    story.append(Paragraph("""
        • All products covered by manufacturer's standard warranty (typically 1 year)
        • Defect rate guarantee: <2% DOA (Dead On Arrival)
        • If defect rate exceeds 2% in any calendar month, TechSource issues 10% credit on that 
        month's invoice
        • RMA process: NexusIQ submits return authorization request within 30 days of receipt, 
        TechSource provides replacement or credit within 10 business days
        • Extended warranty programs available: NexusIQ can purchase at 8% of wholesale cost
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("6. Exclusivity & Competition", heading_style))
    story.append(Paragraph("""
        • Non-exclusive agreement: NexusIQ may source from other suppliers
        • TechSource agrees not to supply direct competitors (TechMart, ValueHub) with better pricing 
        or terms than provided to NexusIQ
        • If TechSource offers competitor better terms, NexusIQ entitled to most-favored-nation 
        pricing matching those terms
        • TechSource grants NexusIQ right of first refusal on new product launches (48-hour window)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("7. Termination & Renewal", heading_style))
    story.append(Paragraph("""
        • Initial term: 3 years (expires December 31, 2026)
        • Auto-renewal: Automatically renews for 1-year terms unless either party provides 180 days 
        written notice
        • Termination for cause: Either party may terminate with 30 days notice if other party 
        breaches material terms
        • Termination for convenience: Either party may terminate without cause with 180 days notice 
        and payment of early termination fee equal to 3 months average purchases
        • Upon termination: NexusIQ has 90 days to sell through existing inventory before exclusivity 
        restrictions lift
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Strategic Notes (Internal)", heading_style))
    story.append(Paragraph("""
        <b>Negotiation Wins:</b>
        • Achieved Tier 3 pricing faster than projected (Q3 vs Q4 target)
        • Extended payment terms from Net 30 to Net 45 (improved cash flow by ~$2.1M)
        • Secured most-favored-nation clause to prevent competitor advantage
        <br/><br/>
        <b>Areas for Renegotiation (2025):</b>
        • Push for 55% wholesale price on accessories (currently 58%) given high margins
        • Request 10-day lead time for standard orders (currently 14-21 days)
        • Negotiate co-marketing fund increase to $300K/quarter (currently $200K)
        • Explore consignment inventory model for slow-moving SKUs to reduce carrying costs
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Supplier_Contract_TechSource.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 5: 2025 Marketing Strategy
# ════════════════════════════════════════════════════════════

def create_marketing_strategy():
    """Annual marketing plan and budget allocation"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Marketing_Strategy_2025.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("2025 Marketing Strategy & Budget Plan", title_style))
    story.append(Paragraph("Total Budget: $28.5M (8.2% of projected revenue)", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Objectives", heading_style))
    story.append(Paragraph("""
        1. Increase brand awareness from 67% to 75% in key demographics (25-54 age group)
        2. Grow customer acquisition by 22% (target: 280,000 new customers)
        3. Improve customer retention rate from 68% to 73%
        4. Achieve $52M in revenue from digital channels (up from $38M in 2024)
        5. Launch brand refresh campaign emphasizing sustainability and community
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Budget Allocation by Channel", heading_style))
    
    budget_data = [
        ['Channel', 'Budget', '% of Total', 'Target ROAS'],
        ['Digital Advertising', '$9.8M', '34%', '4.2:1'],
        ['Social Media Marketing', '$4.2M', '15%', '3.8:1'],
        ['Email & SMS Campaigns', '$2.1M', '7%', '8.1:1'],
        ['Content Marketing & SEO', '$3.5M', '12%', '5.2:1'],
        ['Traditional (TV, Radio, Print)', '$5.4M', '19%', '2.9:1'],
        ['Influencer Partnerships', '$1.8M', '6%', '4.5:1'],
        ['Events & Sponsorships', '$1.7M', '6%', 'Brand Building']
    ]
    
    table = Table(budget_data, colWidths=[2*inch, 1.2*inch, 1*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Campaign Calendar (Key Initiatives)", heading_style))
    story.append(Paragraph("""
        <b>Q1 2025 (Jan-Mar): "New Year, New You"</b>
        • Focus: Fitness equipment, home organization, fresh food subscriptions
        • Channels: Digital ads (Google, Meta), email nurture sequences, influencer partnerships 
        with fitness creators
        • Budget: $6.2M | Target: 68,000 new customers
        <br/><br/>
        <b>Q2 2025 (Apr-Jun): Brand Refresh Launch</b>
        • Focus: Introduce new logo, sustainability messaging, community initiatives
        • Channels: TV commercials (primetime slots), outdoor billboards in top 15 metros, 
        social media takeover
        • Partnerships: Co-branding with eco-friendly product manufacturers
        • Budget: $8.9M | Target: Brand awareness lift to 72%
        <br/><br/>
        <b>Q3 2025 (Jul-Sep): Back-to-School Blitz</b>
        • Focus: Electronics (laptops, tablets), clothing, sports equipment
        • Channels: Programmatic display ads, YouTube pre-roll, Snapchat/TikTok targeting Gen Z parents
        • Promotions: Trade-in program for old electronics (15% bonus credit)
        • Budget: $5.8M | Target: 72,000 new customers, $14M incremental revenue
        <br/><br/>
        <b>Q4 2025 (Oct-Dec): Holiday Season Dominance</b>
        • Focus: Gift-giving across all categories, emphasis on premium electronics
        • Channels: Omnichannel blitz (TV, digital, social, email, SMS), retargeting heavy focus
        • Promotions: Black Friday/Cyber Monday doorbuster deals, extended return policy (60 days)
        • Budget: $7.6M | Target: 112,000 new customers, $24M incremental revenue
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Digital Marketing Deep Dive", heading_style))
    story.append(Paragraph("""
        <b>Paid Search ($4.2M):</b>
        • Google Ads: 70% of budget, focus on high-intent keywords ("buy laptop online", 
        "best smartphone deals")
        • Bing Ads: 20% of budget, often lower CPC and underutilized by competitors
        • Shopping campaigns: 10% of budget, target ROAS 5.5:1 on product listing ads
        • Strategy: Aggressive bidding on competitor brand terms, smart bidding for conversions
        <br/><br/>
        <b>Paid Social ($3.6M):</b>
        • Meta (Facebook/Instagram): 55% of budget, carousel ads for product discovery, 
        retargeting campaigns
        • TikTok: 25% of budget, short-form video content showcasing products in lifestyle contexts
        • Pinterest: 15% of budget, high-intent platform for home décor and fashion
        • LinkedIn: 5% of budget, target B2B customers for bulk/corporate purchases
        <br/><br/>
        <b>Display & Programmatic ($2.0M):</b>
        • Retargeting: 60% of budget, show ads to website visitors who didn't convert
        • Prospecting: 30% of budget, lookalike audiences based on best customers
        • Contextual targeting: 10% of budget, ads on tech blogs, lifestyle sites
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Retention & Loyalty Marketing ($3.2M)", heading_style))
    story.append(Paragraph("""
        <b>Email Marketing ($1.8M):</b>
        • Welcome series: 7-email sequence for new customers (avg open rate target: 42%)
        • Win-back campaigns: Re-engage customers who haven't purchased in 90+ days (15% reactivation rate)
        • Promotional emails: Weekly deals, flash sales, seasonal campaigns (avg CTR target: 3.8%)
        • Personalized recommendations: AI-powered product suggestions based on browse/purchase history
        <br/><br/>
        <b>SMS Marketing ($0.4M):</b>
        • Transactional: Order confirmations, shipping updates (opt-in rate: 34%)
        • Promotional: Flash sale alerts, exclusive SMS-only discounts (avg CTR: 12%)
        • Reminder: Abandoned cart recovery (conversion rate target: 8%)
        <br/><br/>
        <b>Loyalty Program Enhancements ($1.0M):</b>
        • Gamification: Points accelerators, achievement badges, tier progression rewards
        • Exclusive perks: Early access to sales, birthday bonuses, VIP customer service line
        • Referral program: $20 credit for referrer + referee (target: 15,000 referrals in 2025)
        • Partner integrations: Earn points at partner merchants (coffee shops, gas stations)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Success Metrics & KPIs", heading_style))
    story.append(Paragraph("""
        <b>Primary KPIs:</b>
        • Customer Acquisition Cost (CAC): Target $42 (down from $48 in 2024)
        • Blended ROAS: Target 4.5:1 (up from 4.1:1 in 2024)
        • Email opt-in rate: Target 22% of website visitors (currently 18%)
        • Social media engagement rate: Target 4.2% (currently 3.6%)
        • Brand awareness (aided): Target 75% in key demos (currently 67%)
        <br/><br/>
        <b>Monthly Reporting Cadence:</b>
        • Week 1: Channel performance review (spend, ROAS, conversions)
        • Week 2: Creative performance analysis (CTR, engagement, A/B test results)
        • Week 3: Customer cohort analysis (retention rates, LTV trends)
        • Week 4: Strategic planning session (next month priorities, budget reallocation)
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Marketing_Strategy_2025.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 6: Industry Trends Report - Retail Tech 2025
# ════════════════════════════════════════════════════════════

def create_industry_trends():
    """External research report on retail technology trends"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Retail_Tech_Trends_2025.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("Retail Technology Trends 2025", title_style))
    story.append(Paragraph("Forrester Research Industry Report", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph("""
        The retail industry stands at an inflection point as AI, automation, and changing consumer 
        behaviors reshape the competitive landscape. Our research identifies 7 mega-trends that will 
        define retail success in 2025-2027. Early adopters will gain 15-20% efficiency advantages, 
        while laggards risk 8-12% market share erosion.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 1: Generative AI in Customer Experience", heading_style))
    story.append(Paragraph("""
        <b>What's Happening:</b> 67% of retailers now deploy AI chatbots, up from 34% in 2023. 
        Advanced implementations use GPT-4/Claude for personalized shopping assistance, size 
        recommendations, and visual search.
        <br/><br/>
        <b>Business Impact:</b> AI-assisted customer service reduces support costs by 35-40% while 
        improving CSAT scores. Conversion rates increase 12-18% when AI provides personalized 
        product discovery.
        <br/><br/>
        <b>Implementation Considerations:</b> Start with FAQ automation (quick ROI), expand to 
        personalized recommendations, eventually full conversational commerce. Ensure human escalation 
        paths for complex issues.
        <br/><br/>
        <b>ROI Timeline:</b> Break-even in 4-6 months, full payback in 12-14 months.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 2: Autonomous Checkout & Cashierless Stores", heading_style))
    story.append(Paragraph("""
        <b>What's Happening:</b> Amazon Go technology now available via 3rd-party providers. 
        Computer vision + sensor fusion tracks shoppers, auto-charges upon exit. 450+ cashierless 
        stores globally (up from 120 in 2023).
        <br/><br/>
        <b>Business Impact:</b> Labor costs reduced 60-70% per store. Transaction time drops from 
        4.2 minutes to 0.3 minutes (13x faster). Theft rates surprisingly low at 1.8% vs 2.4% 
        traditional checkout.
        <br/><br/>
        <b>Challenges:</b> High upfront capex ($500K-$1.2M per store), complex SKU management, 
        occasional system errors requiring manual intervention.
        <br/><br/>
        <b>Best Fit:</b> High-traffic urban locations, convenience store formats, corporate cafeterias.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 3: Hyper-Personalization via Real-Time Data", heading_style))
    story.append(Paragraph("""
        <b>What's Happening:</b> CDPs (Customer Data Platforms) unify online/offline behavior. 
        Real-time decisioning engines trigger personalized offers within 200ms of customer action.
        <br/><br/>
        <b>Examples in Action:</b>
        • Dynamic pricing: Adjust product prices based on inventory, demand, competitor pricing (legally compliant)
        • Contextual recommendations: Show winter coats to Chicago customer when temperature drops below 40°F
        • Predictive reordering: Auto-suggest restock of frequently purchased items based on usage patterns
        <br/><br/>
        <b>Privacy Considerations:</b> 78% of consumers comfortable with personalization IF value 
        exchange is clear and data usage is transparent. Requires robust consent management and 
        opt-out mechanisms.
        <br/><br/>
        <b>Technology Stack:</b> Segment/mParticle (CDP) + Braze/Iterable (activation) + Snowflake 
        (data warehouse) = ~$180K-$350K annual cost for mid-market retailer.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 4: Social Commerce & Livestream Shopping", heading_style))
    story.append(Paragraph("""
        <b>What's Happening:</b> TikTok Shop, Instagram Shopping, Pinterest Shopping Ads enable 
        in-app purchases. Livestream shopping (QVC for Gen Z) growing 340% YoY in US.
        <br/><br/>
        <b>Demographics:</b> 62% of Gen Z made social commerce purchase in past 6 months vs 28% 
        of Boomers. Average order value $67, impulse-driven.
        <br/><br/>
        <b>Success Factors:</b>
        • Authentic influencer partnerships (micro-influencers outperform celebrities 3:1 on engagement)
        • Shoppable video content (product tags embedded in Instagram Reels, TikTok videos)
        • Limited-time offers create urgency ("only 50 units left" messaging)
        <br/><br/>
        <b>Cautionary Tale:</b> Facebook Shops largely failed due to poor discovery and checkout friction. 
        Focus on platforms where your customers already spend time.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 5: Sustainability as Competitive Differentiator", heading_style))
    story.append(Paragraph("""
        <b>Consumer Sentiment Shift:</b> 73% willing to pay 5-10% premium for sustainable products 
        (up from 58% in 2022). Gen Z/Millennials demand transparency on carbon footprint, ethical 
        sourcing, circular economy practices.
        <br/><br/>
        <b>Regulatory Pressure:</b> EU mandates supply chain due diligence reporting by 2026. 
        California requires climate-related financial disclosures for large retailers.
        <br/><br/>
        <b>Credible Actions:</b>
        • Carbon-neutral shipping options (customers pay $1-2 extra, offset via reforestation)
        • Packaging reduction: eliminate single-use plastics, shift to recycled/biodegradable materials
        • Product takeback programs: accept old products for recycling, offer store credit
        • Transparent sourcing: publish supplier lists, audit reports, certifications (B Corp, Fair Trade)
        <br/><br/>
        <b>Greenwashing Risk:</b> Vague claims ("eco-friendly") without substantiation damage trust. 
        Use third-party certifications and specific metrics (e.g., "30% recycled content").
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 6: Inventory Optimization via AI/ML", heading_style))
    story.append(Paragraph("""
        <b>Problem Statement:</b> Average retailer holds 32% excess inventory (ties up cash) while 
        experiencing 8% stockouts (lost sales). Traditional forecasting models fail to account for 
        rapidly changing consumer preferences.
        <br/><br/>
        <b>AI Solution:</b> Machine learning models ingest 50+ signals (weather, social trends, 
        local events, competitor pricing, search trends) to predict demand at SKU-store-week level.
        <br/><br/>
        <b>Results:</b>
        • Inventory turns improve 22-28% (free up working capital)
        • Stockouts reduced 35-42% (capture more sales)
        • Markdown optimization: clear slow-moving inventory at optimal price points (maximize gross margin)
        <br/><br/>
        <b>Vendor Landscape:</b> Blue Yonder, o9 Solutions, Relex Solutions dominate enterprise market. 
        Mid-market options: Inventory Planner, Lokad (lower cost, faster deployment).
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Trend 7: Augmented Reality (AR) Try-Before-You-Buy", heading_style))
    story.append(Paragraph("""
        <b>What's Happening:</b> AR-powered virtual try-on for apparel, makeup, furniture. IKEA Place 
        app lets customers visualize furniture in their home. Sephora Virtual Artist for makeup simulation.
        <br/><br/>
        <b>Impact Metrics:</b>
        • Return rates decrease 25-35% (better fit/visualization reduces buyer's remorse)
        • Conversion rates increase 40-94% for products with AR enabled
        • Engagement: Users spend 2.7x longer on product pages with AR features
        <br/><br/>
        <b>Technology Readiness:</b> WebAR (browser-based) now works on 85% of smartphones, no app 
        download required. 3D asset creation cost dropped 60% via AI-powered photogrammetry.
        <br/><br/>
        <b>Implementation Roadmap:</b>
        1. Start with high-return categories (furniture, apparel, eyewear)
        2. Pilot with 20-30 SKUs, measure conversion/return impact
        3. Scale to full catalog if ROI validated
        4. Integrate with social commerce (AR try-on directly in Instagram/Snapchat)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Strategic Recommendations", heading_style))
    story.append(Paragraph("""
        <b>Priority 1 (Immediate - Q1 2025):</b> Deploy AI chatbot for customer service FAQ 
        automation. Lowest risk, fastest ROI, builds organizational AI competency.
        <br/><br/>
        <b>Priority 2 (6-Month Horizon):</b> Implement CDP for unified customer view. Foundation 
        for personalization, essential for omnichannel excellence.
        <br/><br/>
        <b>Priority 3 (12-Month Horizon):</b> Pilot autonomous checkout in 2-3 high-traffic stores. 
        Evaluate customer reception and unit economics before broader rollout.
        <br/><br/>
        <b>Priority 4 (18-Month Horizon):</b> Launch AR try-on for top 3 product categories. 
        Differentiate from competitors, reduce return rates.
        <br/><br/>
        <b>Avoid:</b> Blockchain for supply chain (overhyped, limited ROI), VR shopping experiences 
        (low adoption, high friction), voice commerce (plateaued at 4% of e-commerce).
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Retail_Tech_Trends_2025.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 7: HR Policy - Remote Work Guidelines
# ════════════════════════════════════════════════════════════

def create_hr_policy():
    """Internal HR policy document"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Remote_Work_Policy_2025.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("Remote & Hybrid Work Policy", title_style))
    story.append(Paragraph("NexusIQ Corporation | Effective January 1, 2025", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. Policy Overview", heading_style))
    story.append(Paragraph("""
        NexusIQ embraces flexible work arrangements to attract top talent, improve work-life balance, 
        and reduce environmental impact. This policy outlines eligibility, expectations, and guidelines 
        for remote and hybrid work models.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("2. Work Model Options", heading_style))
    story.append(Paragraph("""
        <b>Fully Remote:</b> Work from any US location 5 days/week. Must attend quarterly all-hands 
        meetings in person (travel covered by company). Available to: Corporate roles, Tech/IT, 
        Marketing, Finance.
        <br/><br/>
        <b>Hybrid (3/2):</b> In-office 3 days (Tue/Wed/Thu core days), remote 2 days (Mon/Fri). 
        Available to: Most departments. Manager approval required.
        <br/><br/>
        <b>Hybrid (2/3):</b> In-office 2 days, remote 3 days. Reserved for senior IC contributors 
        and specialized roles. Director approval required.
        <br/><br/>
        <b>Fully In-Office:</b> Required for: Store operations, warehouse/logistics, retail sales, 
        customer service (phone support center). Some customer service agents may qualify for remote 
        after 6 months tenure with performance rating ≥ "Meets Expectations".
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("3. Eligibility Requirements", heading_style))
    story.append(Paragraph("""
        • Tenure: 90 days minimum employment (successful completion of probationary period)
        • Performance: Most recent review rating ≥ "Meets Expectations"
        • Role suitability: Job can be performed effectively without daily in-person collaboration
        • Manager approval: Direct manager and department head sign off
        • Technology readiness: Reliable high-speed internet (minimum 25 Mbps download, 5 Mbps upload), 
        suitable workspace free from distractions
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("4. Equipment & Expenses", heading_style))
    story.append(Paragraph("""
        <b>Provided by Company:</b>
        • Laptop (Dell XPS 15 or MacBook Pro, depending on role)
        • Monitor (27" 4K display), keyboard, mouse, webcam, headset
        • VPN access, collaboration software licenses (Zoom, Slack, Microsoft 365)
        • Ergonomic chair (up to $400 reimbursement with receipt)
        <br/><br/>
        <b>Monthly Stipends:</b>
        • Internet: $50/month
        • Phone: $40/month (if using personal phone for work)
        • Home office: $75/month (utilities, supplies)
        <br/><br/>
        <b>Not Covered:</b>
        • Rent/mortgage, home insurance, furniture beyond chair, décor
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("5. Performance Expectations", heading_style))
    story.append(Paragraph("""
        • Availability: Core hours 10am-3pm local time (all time zones). Respond to Slack/email within 
        2 hours during core hours.
        • Meetings: Camera on for video calls (builds team cohesion), mute when not speaking
        • Productivity: Measured by outcomes (project delivery, KPIs) not hours logged. Trust-based system.
        • Communication: Over-communicate progress, blockers, schedule changes. Don't let geographic distance 
        create information gaps.
        • Collaboration: Proactively reach out to colleagues, don't work in isolation. Use asynchronous 
        tools (Loom videos, detailed Slack updates) to keep remote teammates informed.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("6. Data Security & Compliance", heading_style))
    story.append(Paragraph("""
        • Use company-provided laptop ONLY (no personal devices for work)
        • Enable full disk encryption, screen lock after 5 min inactivity
        • Connect via company VPN when accessing internal systems
        • Do not work from public WiFi (coffee shops, airports) when handling sensitive data
        • Report lost/stolen equipment within 2 hours to IT Security (security@nexusiq.com)
        • Confidential documents must be stored in encrypted cloud (Google Drive, SharePoint), never local desktop
        • Video call backgrounds: Blur or use virtual background if home environment visible
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("7. Tax & Legal Considerations", heading_style))
    story.append(Paragraph("""
        • Permanent remote workers must reside in states where NexusIQ has nexus (currently: CA, TX, 
        NY, IL, WA, FL, GA, NC, AZ, CO, MA, VA, PA, OH, MI, NJ)
        • Notify HR within 30 days if relocating to new state
        • Some states require company registration before employee can work there (HR will handle)
        • Working abroad: Not permitted for more than 2 weeks/year without special approval (visa, 
        tax treaty, data sovereignty issues)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("8. Policy Violations & Termination", heading_style))
    story.append(Paragraph("""
        Remote/hybrid privilege may be revoked for:
        • Performance decline: 2 consecutive reviews below "Meets Expectations"
        • Unresponsiveness: Pattern of missing meetings, delayed responses, unavailability during core hours
        • Security breach: Sharing credentials, working from insecure locations, losing company equipment
        • Policy violation: Working from unapproved location, unauthorized equipment use
        <br/><br/>
        Process: Verbal warning → written warning → 30-day probation (return to office) → privilege 
        revoked. In severe cases (security breach), immediate revocation.
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Remote_Work_Policy_2025.pdf")


# ════════════════════════════════════════════════════════════
#  DOCUMENT 8: Product Catalog - Electronics 2025
# ════════════════════════════════════════════════════════════

def create_product_catalog():
    """Product specifications and pricing"""
    
    doc = SimpleDocTemplate(
        "data/pdfs/Product_Catalog_Electronics_2025.pdf",
        pagesize=letter,
        topMargin=0.75*inch
    )
    
    story = []
    
    story.append(Paragraph("2025 Electronics Product Catalog", title_style))
    story.append(Paragraph("NexusIQ Retail | Updated Monthly", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Premium Smartphones", heading_style))
    
    smartphone_data = [
        ['Model', 'SKU', 'Retail Price', 'Wholesale Cost', 'Margin'],
        ['TechPro X14 (512GB)', 'TP-X14-512', '$1,199', '$743', '38%'],
        ['TechPro X14 (256GB)', 'TP-X14-256', '$999', '$619', '38%'],
        ['Galaxy Ultra S24', 'SAM-S24U-256', '$1,099', '$681', '38%'],
        ['Pixel Supreme 9', 'GOO-PS9-256', '$899', '$575', '36%']
    ]
    
    table = Table(smartphone_data, colWidths=[2.2*inch, 1.3*inch, 1*inch, 1.2*inch, 0.8*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9)
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Laptops - Business Grade", heading_style))
    story.append(Paragraph("""
        <b>WorkPro Elite 15 (SKU: WP-E15-I7):</b>
        • Processor: Intel Core i7-13700H (14 cores)
        • RAM: 32GB DDR5
        • Storage: 1TB NVMe SSD
        • Display: 15.6" 4K OLED touchscreen
        • Graphics: NVIDIA RTX 4060 (8GB VRAM)
        • Retail: $1,899 | Wholesale: $1,234 | Margin: 35%
        • Warranty: 3 years on-site service
        • Target: Power users, creative professionals, engineers
        <br/><br/>
        <b>WorkPro Standard 14 (SKU: WP-S14-I5):</b>
        • Processor: Intel Core i5-1340P (12 cores)
        • RAM: 16GB DDR4
        • Storage: 512GB NVMe SSD
        • Display: 14" FHD IPS (1080p)
        • Graphics: Intel Iris Xe integrated
        • Retail: $899 | Wholesale: $611 | Margin: 32%
        • Warranty: 1 year mail-in service
        • Target: General business users, students
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Smart Home Devices", heading_style))
    story.append(Paragraph("""
        <b>NexusHub Pro (Voice Assistant Speaker):</b>
        • Features: 360° audio, smart home hub (controls lights, thermostat, locks), Alexa + Google 
        Assistant compatible
        • Retail: $129 | Wholesale: $75 | Margin: 42%
        • Promotion: Buy 2 get 15% off (drives multi-room adoption)
        <br/><br/>
        <b>SecureVision Doorbell Camera:</b>
        • Features: 1080p video, night vision, motion alerts, two-way audio, cloud storage (subscription)
        • Retail: $179 | Wholesale: $104 | Margin: 42%
        • Subscription: $4.99/month cloud storage (90% gross margin recurring revenue)
        <br/><br/>
        <b>ClimateControl Smart Thermostat:</b>
        • Features: Learning algorithm, remote control via app, energy usage reports, works with HVAC systems
        • Retail: $249 | Wholesale: $149 | Margin: 40%
        • Energy savings: Customers save avg $180/year on heating/cooling (strong value prop)
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Accessories & Peripherals", heading_style))
    story.append(Paragraph("""
        <b>High-Margin Opportunities:</b>
        • USB-C cables (6ft): Retail $19.99, Wholesale $8.50 (57% margin) ← Huge opportunity
        • Phone cases: Retail $29.99, Wholesale $12.00 (60% margin)
        • Screen protectors: Retail $24.99, Wholesale $9.00 (64% margin)
        • Wireless chargers: Retail $39.99, Wholesale $18.50 (54% margin)
        <br/><br/>
        <b>Bundling Strategy:</b>
        • "New Phone Starter Kit": Phone + case + screen protector + charger bundled at 10% discount 
        (still nets 48% margin due to accessory pull-through)
        • Attach rate: Currently 34% of smartphone buyers purchase at least 1 accessory. Target: 50% 
        via bundling + checkout prompts.
    """, styles['BodyText']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Inventory Management Notes", heading_style))
    story.append(Paragraph("""
        <b>Fast-Movers (Reorder Weekly):</b>
        • TechPro X14 (both variants): Avg 240 units/week sold
        • USB-C cables: Avg 1,100 units/week sold
        • Phone cases: Avg 890 units/week sold
        <br/><br/>
        <b>Seasonal Patterns:</b>
        • Laptops: Back-to-school spike (July-August), holiday spike (November-December)
        • Smart home: Holiday gifting drives 40% of annual sales (Oct-Dec)
        • Smartphones: New model launches (typically Sep/Oct) cannibalize older models - markdown 
        previous gen by 15-20%
        <br/><br/>
        <b>Slow-Movers (At-Risk for Markdown):</b>
        • Budget tablets: Avg 12 units/week sold, 180-day inventory on hand (reduce orders)
        • Desktop computers: Declining category, only 8 units/week sold (consider discontinuing)
    """, styles['BodyText']))
    
    doc.build(story)
    print("✅ Created: Product_Catalog_Electronics_2025.pdf")


# ════════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  📄 GENERATING BUSINESS PDF DOCUMENTS FOR RAG AGENT")
    print("="*60 + "\n")
    
    create_q4_sales_report()
    create_competitor_analysis()
    create_customer_survey()
    create_supplier_contract()
    create_marketing_strategy()
    create_industry_trends()
    create_hr_policy()
    create_product_catalog()
    
    print("\n" + "="*60)
    print("  ✅ ALL 8 PDF DOCUMENTS CREATED SUCCESSFULLY")
    print("="*60)
    print("\nDocuments created in: data/pdfs/")
    print("\nNext steps:")
    print("1. Review PDFs to ensure content quality")
    print("2. Run RAG ingestion pipeline to create embeddings")
    print("3. Test semantic search with sample questions")
    print("\n")
