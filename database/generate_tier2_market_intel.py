"""
TIER 2: Market Intelligence PDFs (5 documents)
Generates market research, competitor analysis, and customer insights
Location: data/pdfs/02_market_intelligence/
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, 
    TableStyle, PageBreak
)
from reportlab.lib import colors
import os

# Output directory
OUTPUT_DIR = "./data/pdfs/02_market_intelligence"


def create_output_dir():
    """Ensure output directory exists"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✅ Created directory: {OUTPUT_DIR}")


def get_custom_styles():
    """Reusable custom styles for consistent formatting"""
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=20,
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
    
    return styles, title_style, heading_style


# ========================================
# DOCUMENT 1: Market Analysis Electronics
# ========================================

def generate_market_analysis_electronics():
    """Electronics market trends and forecasts"""
    filename = f"{OUTPUT_DIR}/Market_Analysis_Electronics_2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Electronics Market Analysis 2024", title_style))
    story.append(Paragraph("Industry Report - North American Retail Sector", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market Overview", heading_style))
    overview = """
    North American electronics retail market reached $385B in 2024, growing 12% YoY. 
    Key drivers:<br/>
    • Smartphone replacement cycle acceleration (18-month average)<br/>
    • Smart home device adoption (68% household penetration)<br/>
    • Gaming console demand (new generation releases)<br/>
    • Remote work technology investments
    <br/><br/>
    <b>Market Share by Category:</b><br/>
    Smartphones & Accessories: 32% | Computers & Tablets: 28% | Smart Home: 18% | 
    Gaming: 12% | Audio: 10%
    """
    story.append(Paragraph(overview, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Market Dynamics", heading_style))
    regional = """
    <b>West Coast Leadership:</b> West region dominates electronics sales, driven by 
    tech-savvy demographics and higher disposable incomes. Average electronics purchase: 
    $1,245 (vs national $987).
    <br/><br/>
    <b>East Coast Stabilization:</b> Mature market, single-digit growth. Opportunities 
    in premium segment (>$1,500 devices). Urban centers show 3x higher smart home adoption.
    <br/><br/>
    <b>Central Region Growth:</b> Emerging market, 15% CAGR. Mid-tier products ($300-$800) 
    perform best. Digital payment adoption correlates with electronics purchases.
    <br/><br/>
    <b>Southern Market Challenges:</b> High price sensitivity. Budget electronics (<$300) 
    account for 52% of sales. Opportunity: Trade-in programs to upgrade customers.
    """
    story.append(Paragraph(regional, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Competitive Landscape", heading_style))
    competitor = """
    <b>Market Leaders:</b><br/>
    1. TechGiant Retail: 24% share, flagship store strength<br/>
    2. ElectroMart: 19% share, competitive pricing strategy<br/>
    3. NexusIQ Corporation: 8% share, regional strength in West<br/>
    4. Digital Depot: 7% share, online-first model
    <br/><br/>
    <b>NexusIQ Positioning:</b> Outperforms in customer service (4.6/5 vs industry 3.9/5) 
    and payment flexibility. Primary weakness: limited online presence (12% sales vs industry 34%).
    """
    story.append(Paragraph(competitor, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Consumer Behavior Insights", heading_style))
    behavior = """
    <b>Digital Payment Preference:</b> 67% of electronics buyers prefer digital payments. 
    Cash usage dropped to 8% in electronics category specifically.
    <br/><br/>
    <b>Purchase Drivers:</b><br/>
    Product quality: 89% | Price: 76% | Payment flexibility: 64% | 
    In-store experience: 58% | Online availability: 52%
    <br/><br/>
    <b>Seasonal Patterns:</b> Q4 accounts for 38% of annual electronics sales (holiday). 
    Back-to-school (Aug-Sep): 18%. Spring (Mar-May): 12% (slowest).
    """
    story.append(Paragraph(behavior, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Recommendations", heading_style))
    recommendations = """
    <b>For Regional Retailers (NexusIQ Profile):</b>
    <br/><br/>
    1. <b>Double Down on West Region:</b> Market data supports aggressive expansion in 
    high-growth markets (San Francisco, San Diego).
    <br/><br/>
    2. <b>Premium Product Mix:</b> Shift inventory toward $800+ devices in West/East regions. 
    Data shows 32% higher margins and lower return rates.
    <br/><br/>
    3. <b>Digital Wallet Partnerships:</b> Electronics buyers are early adopters. Exclusive 
    Digital Wallet promotions could drive 15-20% sales lift.
    <br/><br/>
    4. <b>Omnichannel Integration:</b> Critical gap. Competitors with online presence capture 
    2.4x more customer lifetime value. Recommend phased rollout starting Q2 2025.
    """
    story.append(Paragraph(recommendations, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Market Intelligence Report | Electronics Sector 2024", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 2: Competitor Pricing Strategy
# ========================================

def generate_competitor_pricing_strategy():
    """Competitive pricing analysis and positioning"""
    filename = f"{OUTPUT_DIR}/Competitor_Pricing_Strategy.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Competitor Pricing Strategy Analysis", title_style))
    story.append(Paragraph("Q4 2024 Market Intelligence Report", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market Positioning Overview", heading_style))
    intro = """
    Analysis of NexusIQ's top 4 competitors across Electronics category (our highest 
    revenue contributor at 34%). Data from mystery shopping, price matching, and industry sources.
    <br/><br/>
    <b>Competitors Analyzed:</b><br/>
    • TechGiant Retail (market leader, 24% share)<br/>
    • ElectroMart (price leader, 19% share)<br/>
    • Digital Depot (online specialist, 7% share)<br/>
    • Premium Electronics Co. (luxury positioning, 5% share)
    """
    story.append(Paragraph(intro, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Electronics Pricing Comparison", heading_style))
    
    pricing_data = [
        ['Product', 'NexusIQ', 'TechGiant', 'ElectroMart', 'Digital', 'Premium'],
        ['Smartphone Pro 15', '$799', '$799', '$749', '$729', '$849'],
        ['UltraBook X5', '$1,349', '$1,299', '$1,249', '$1,199', '$1,399'],
        ['Tablet Pro 12"', '$649', '$649', '$599', '$579', '$699'],
        ['SmartWatch S6', '$429', '$399', '$379', '$359', '$449'],
        ['Earbuds Pro', '$279', '$249', '$229', '$219', '$299'],
    ]
    
    t = Table(pricing_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (1, 1), (1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<i>Prices as of December 15, 2024. Excludes promotional periods.</i>", 
                          styles['Italic']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Key Pricing Insights", heading_style))
    insights = """
    <b>NexusIQ Positioning: Mid-Premium Tier</b><br/>
    Our prices average 8% higher than ElectroMart (price leader) but 12% lower than 
    Premium Electronics Co. This positions us as "quality without luxury markup."
    <br/><br/>
    <b>Competitive Gaps:</b><br/>
    • Smartphones: Pricing parity with TechGiant, but they offer trade-in programs we lack<br/>
    • Laptops: Our $1,349 undercuts Premium Co. but 12% above Digital Depot's online-only price<br/>
    • Accessories: Largest gap (28% above Digital Depot) - opportunity for adjustment
    <br/><br/>
    <b>Regional Price Variations:</b> ElectroMart uses dynamic regional pricing - West Coast 
    prices 5% higher than Midwest. NexusIQ maintains consistent national pricing (potential 
    strategic advantage).
    """
    story.append(Paragraph(insights, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Competitor Promotional Strategies", heading_style))
    promo = """
    <b>TechGiant Retail:</b><br/>
    • Bundles: "Buy laptop + accessories, save 15%"<br/>
    • Loyalty program: 5% back on all electronics purchases<br/>
    • Trade-in: Up to $300 credit for old devices<br/>
    • Frequency: Major promotions every 6-8 weeks
    <br/><br/>
    <b>ElectroMart:</b><br/>
    • Everyday low pricing (EDLP) strategy<br/>
    • Price matching guarantee (honors competitors + 10% difference)<br/>
    • Flash sales: Weekend "Lightning Deals" (limited quantity)<br/>
    • Frequency: Constant promotional pressure
    <br/><br/>
    <b>Digital Depot:</b><br/>
    • Free shipping on all orders (no minimum)<br/>
    • Digital-only discounts: 5-7% lower than in-store competitors<br/>
    • Email exclusive deals for subscribers<br/>
    • Frequency: Daily "Deal of the Day"
    <br/><br/>
    <b>Premium Electronics Co.:</b><br/>
    • Minimal promotions (protects brand positioning)<br/>
    • Concierge service included (white-glove delivery)<br/>
    • Extended warranties (3 years vs industry standard 1 year)<br/>
    • Frequency: Only Black Friday and annual sale
    """
    story.append(Paragraph(promo, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Payment Strategy Comparison", heading_style))
    payment = """
    <b>Digital Wallet Incentives:</b><br/>
    • <b>NexusIQ:</b> 3% discount on Digital Wallet purchases (Q4 2024 pilot)<br/>
    • <b>TechGiant:</b> 2% cashback via proprietary app wallet<br/>
    • <b>ElectroMart:</b> No Digital Wallet incentives<br/>
    • <b>Digital Depot:</b> 5% discount for new Digital Wallet users
    <br/><br/>
    <b>Financing Options:</b><br/>
    • <b>TechGiant:</b> 0% APR for 12 months on purchases >$500<br/>
    • <b>ElectroMart:</b> 6-month financing (18% APR)<br/>
    • <b>NexusIQ:</b> No proprietary financing (third-party credit card only)<br/>
    • <b>Digital Depot:</b> "Buy Now, Pay Later" partnerships (Affirm, Klarna)
    <br/><br/>
    <b>Strategic Implication:</b> NexusIQ's lack of financing options may deter high-ticket 
    purchases ($1,000+). Recommend exploring BNPL partnerships to match Digital Depot's offering.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Pricing Recommendations", heading_style))
    recs = """
    <b>1. Maintain Mid-Premium Positioning</b><br/>
    Our customer satisfaction scores (4.6/5) justify moderate price premium over ElectroMart. 
    Avoid race to bottom - focus on value differentiation.
    <br/><br/>
    <b>2. Introduce Trade-In Program</b><br/>
    TechGiant captures upgrade cycles we're missing. Estimated impact: 15% increase in 
    repeat Electronics purchases.
    <br/><br/>
    <b>3. Adjust Accessory Pricing</b><br/>
    28% premium over Digital Depot unsustainable. Recommend 10-15% reduction to drive 
    attachment sales (accessories are impulse buys).
    <br/><br/>
    <b>4. Launch "Buy Now, Pay Later"</b><br/>
    Critical gap vs competitors. Target launch Q1 2025 - could unlock $8-10M in incremental 
    sales (customers purchasing products they'd otherwise delay).
    <br/><br/>
    <b>5. Expand Digital Wallet Incentives</b><br/>
    Our 3% discount pilot successful (31% adoption in Q4). Make permanent and promote 
    aggressively - helps offset online price disadvantage.
    <br/><br/>
    <b>6. Test Regional Pricing (West Coast)</b><br/>
    West region shows price insensitivity (highest satisfaction despite premium positioning). 
    Pilot 3-5% increase on high-margin categories.
    """
    story.append(Paragraph(recs, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Competitive Intelligence | Confidential - Do Not Distribute", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 3: Customer Satisfaction Survey
# ========================================

def generate_customer_satisfaction_survey():
    """Annual customer feedback analysis"""
    filename = f"{OUTPUT_DIR}/Customer_Satisfaction_Survey_2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Customer Satisfaction Survey 2024", title_style))
    story.append(Paragraph("Annual Customer Feedback Report", styles['Heading3']))
    story.append(Paragraph("Survey Period: January - December 2024 | Respondents: 8,547", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    summary = """
    NexusIQ Corporation achieved an overall customer satisfaction score of <b>4.6 out of 5.0</b> 
    in 2024, exceeding the retail industry average of 3.9. Key findings:
    <br/><br/>
    • <b>Highest Satisfaction:</b> West region customers (4.8/5)<br/>
    • <b>Lowest Satisfaction:</b> South region customers (4.1/5)<br/>
    • <b>Top Strength:</b> Product quality and payment flexibility<br/>
    • <b>Primary Complaint:</b> Limited online shopping options<br/>
    • <b>Loyalty Rate:</b> 78% would recommend NexusIQ to friends
    """
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Satisfaction Breakdown", heading_style))
    
    regional_data = [
        ['Region', 'Satisfaction Score', 'Response Rate', 'Net Promoter Score'],
        ['West', '4.8 / 5.0', '34%', '+72'],
        ['East', '4.6 / 5.0', '28%', '+58'],
        ['Central', '4.5 / 5.0', '22%', '+54'],
        ['North', '4.4 / 5.0', '9%', '+48'],
        ['South', '4.1 / 5.0', '7%', '+31'],
    ]
    
    t = Table(regional_data, colWidths=[1.5*inch, 1.7*inch, 1.5*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Satisfaction by Product Category", heading_style))
    category = """
    <b>Electronics (4.7/5):</b> "High-quality products" and "latest technology" frequently 
    mentioned. Customers appreciate knowledgeable staff. Complaint: "Prices higher than 
    online competitors."
    <br/><br/>
    <b>Home (4.6/5):</b> Strong satisfaction with product variety. North region customers 
    particularly enthusiastic about smart home offerings. Request: "More installation services."
    <br/><br/>
    <b>Clothing (4.5/5):</b> Positive feedback on seasonal collections. East region customers 
    value in-store fitting rooms. Suggestion: "Expand plus-size options."
    <br/><br/>
    <b>Food (4.4/5):</b> Convenience appreciated but margins perceived as high. Central region 
    customers request "more organic and local options."
    <br/><br/>
    <b>Sports (4.3/5):</b> Smallest category with mixed reviews. Customers want "better brand 
    selection" and "expert advice on equipment."
    """
    story.append(Paragraph(category, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Payment Experience Feedback", heading_style))
    payment = """
    <b>Digital Wallet Users (4.9/5 satisfaction):</b><br/>
    "Love the speed and convenience!" - West region customer<br/>
    "Exclusive Digital Wallet discounts are a great perk." - Central region customer<br/>
    "Wish more stores offered Apple Pay." - East region customer
    <br/><br/>
    <b>Credit/Debit Card Users (4.6/5):</b><br/>
    Generally satisfied but noted "checkout lines can be slow during peak hours."
    <br/><br/>
    <b>Cash Users (4.2/5):</b><br/>
    Older demographic, primarily in South and Central regions. Concerns about "stores 
    discouraging cash" and "ATM availability in stores."
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Selected Customer Comments", heading_style))
    comments = """
    <b>Positive Feedback:</b>
    <br/><br/>
    <i>"NexusIQ has the best customer service I've experienced at any retail store. Staff 
    in the Seattle location went above and beyond to help me choose the right laptop."</i> 
    - West region, Electronics customer
    <br/><br/>
    <i>"I love that I can use my Digital Wallet and earn points. The whole experience feels 
    modern and convenient."</i> - Central region, Home category customer
    <br/><br/>
    <i>"Product quality is consistently excellent. I've never had to return anything, unlike 
    other stores."</i> - East region, Clothing customer
    <br/><br/>
    <b>Constructive Criticism:</b>
    <br/><br/>
    <i>"Please add online ordering! I want to browse at home and pick up in store."</i> 
    - South region customer (<b>mentioned 847 times</b>)
    <br/><br/>
    <i>"Miami store was understocked during the holidays. Frustrated I couldn't find the 
    product I wanted."</i> - South region, Electronics customer
    <br/><br/>
    <i>"Prices are a bit higher than Amazon, but I'm willing to pay for the in-store 
    experience. Just don't let the gap widen."</i> - West region customer
    """
    story.append(Paragraph(comments, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Actionable Recommendations", heading_style))
    recommendations = """
    <b>1. Priority: Launch E-Commerce Platform</b><br/>
    847 customers explicitly requested online ordering. Estimated revenue impact: $12-15M 
    annually based on industry benchmarks.
    <br/><br/>
    <b>2. Address South Region Challenges</b><br/>
    Lower satisfaction (4.1/5) correlates with Q4 revenue underperformance. Recommend 
    inventory optimization and targeted staff training.
    <br/><br/>
    <b>3. Expand Digital Wallet Adoption</b><br/>
    Highest satisfaction segment (4.9/5). Promote aggressively in East/South regions where 
    penetration lags (18% vs 38% in Central).
    <br/><br/>
    <b>4. Enhance Sports Category</b><br/>
    Lowest satisfaction (4.3/5). Consider partnerships with specialty brands or exit category 
    if margins don't justify investment.
    <br/><br/>
    <b>5. Leverage West Region Best Practices</b><br/>
    Highest NPS (+72) and satisfaction (4.8/5). Study staff training, store layout, and 
    product mix for replication in other regions.
    """
    story.append(Paragraph(recommendations, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Customer Insights Report 2024 | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 4: Industry Trends Report
# ========================================

def generate_industry_trends_report():
    """Retail industry macro trends analysis"""
    filename = f"{OUTPUT_DIR}/Industry_Trends_Retail_2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Retail Industry Trends 2024", title_style))
    story.append(Paragraph("North American Market Analysis", styles['Heading3']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    summary = """
    2024 retail landscape characterized by digital acceleration, payment method evolution, 
    and consumer expectation shifts. Total North American retail: $5.2T (+8.3% YoY).
    <br/><br/>
    <b>Top Trends:</b><br/>
    • Digital payment adoption: 42% of all transactions (vs 35% in 2023)<br/>
    • Omnichannel expectations: 73% want online + in-store integration<br/>
    • Sustainability focus: 58% willing to pay premium for eco-friendly<br/>
    • Personalization demand: 64% expect tailored recommendations<br/>
    • Same-day delivery: 31% consider it essential (vs 19% in 2023)
    """
    story.append(Paragraph(summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Digital Payment Revolution", heading_style))
    payment = """
    <b>2024 Payment Method Distribution:</b><br/>
    • Digital Wallet: 22% (up from 15% in 2022)<br/>
    • Credit Card: 31% (stable)<br/>
    • Debit Card: 28% (down from 33%)<br/>
    • Cash: 14% (down from 23% in 2022)<br/>
    • BNPL (Buy Now Pay Later): 5% (new category)
    <br/><br/>
    <b>Key Insight:</b> Digital Wallet adoption accelerating fastest among 25-40 age group 
    (38% usage) and in Electronics/Home categories. Retailers offering Digital Wallet 
    exclusive promotions see 18% higher transaction values.
    <br/><br/>
    <b>Regional Variations:</b> West Coast leads at 28% Digital Wallet penetration. 
    South/Midwest lag at 16%. Urban centers 2.3x higher adoption than rural areas.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Omnichannel Imperative", heading_style))
    omnichannel = """
    <b>Consumer Expectations (2024 Survey):</b><br/>
    • Buy online, pick up in store (BOPIS): 67% want this option<br/>
    • Browse online, buy in store: 58% regularly do this<br/>
    • Return online purchases in-store: 72% expect this<br/>
    • Check in-store inventory online: 81% consider essential
    <br/><br/>
    <b>Impact on Retailers:</b> Companies with integrated omnichannel experience report 
    2.7x higher customer lifetime value. However, 42% of mid-size retailers (500-2000 
    employees) still lack basic e-commerce capabilities.
    <br/><br/>
    <b>Implementation Reality:</b> Average omnichannel platform cost: $2-5M. Payback 
    period: 18-24 months for retailers with existing customer base.
    """
    story.append(Paragraph(omnichannel, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Category-Specific Insights", heading_style))
    categories = """
    <b>Electronics:</b> Fastest-growing category (+12% YoY). Premium tier ($1,000+) outpacing 
    budget segment. Trade-in programs driving repeat purchases (27% higher than retailers 
    without trade-ins).
    <br/><br/>
    <b>Home Goods:</b> Smart home devices surging (+24% YoY). Customers increasingly expect 
    installation services (62% willing to pay for setup). Bundle discounts effective 
    (15% sales lift).
    <br/><br/>
    <b>Clothing:</b> Sustainable materials gaining traction. 41% consumers check sustainability 
    credentials before purchase. Plus-size demand outpacing supply (opportunity for expansion).
    <br/><br/>
    <b>Food/Grocery:</b> Convenience premium accepted. Customers pay 8-12% more for local/organic 
    options. Digital coupons drive 23% higher basket sizes.
    <br/><br/>
    <b>Sports/Outdoor:</b> Experiential retail winning. Stores with try-before-buy programs 
    see 34% higher conversion. Expert staff consultation critical (mentioned by 71% of 
    satisfied customers).
    """
    story.append(Paragraph(categories, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Competitive Landscape Shifts", heading_style))
    competitive = """
    <b>Winners:</b><br/>
    • Retailers with omnichannel integration (+18% revenue growth)<br/>
    • Digital Wallet early adopters (+12% customer acquisition)<br/>
    • Premium product focus (+15% margin expansion)<br/>
    • Regional specialists with local expertise (+9% loyalty rates)
    <br/><br/>
    <b>Losers:</b><br/>
    • Cash-only retailers (-22% customer base)<br/>
    • Pure brick-and-mortar, no online (-8% revenue)<br/>
    • Generic product mix, no differentiation (-5% market share)<br/>
    • Poor customer service (NPS <30) (-14% repeat purchases)
    <br/><br/>
    <b>Emerging Threats:</b> AI-powered recommendation engines becoming table stakes. Amazon's 
    "Just Walk Out" technology expanding. Direct-to-consumer brands bypassing retailers.
    """
    story.append(Paragraph(competitive, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2025 Predictions", heading_style))
    predictions = """
    1. <b>Digital Wallet dominance:</b> Will surpass credit cards as #1 payment method by Q3 2025
    <br/><br/>
    2. <b>Omnichannel mandatory:</b> Retailers without e-commerce will lose 15-20% market share
    <br/><br/>
    3. <b>AI personalization:</b> 50% of retailers will deploy AI recommendation engines
    <br/><br/>
    4. <b>Sustainability premium:</b> Eco-friendly products will command 10-15% price premium
    <br/><br/>
    5. <b>Regional consolidation:</b> Mid-size retailers will merge or exit due to competitive pressures
    """
    story.append(Paragraph(predictions, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Industry Trends Report 2024 | Market Research", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 5: Brand Perception Study
# ========================================

def generate_brand_perception_study():
    """Qualitative brand research and positioning analysis"""
    filename = f"{OUTPUT_DIR}/Brand_Perception_Study.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("NexusIQ Brand Perception Study", title_style))
    story.append(Paragraph("Qualitative Research Report - Q3 2024", styles['Heading3']))
    story.append(Paragraph("Focus Groups: 12 | In-depth Interviews: 45 | Online Survey: 2,200", 
                          styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Research Objectives", heading_style))
    objectives = """
    1. Understand NexusIQ brand positioning in competitive landscape<br/>
    2. Identify key differentiators and vulnerabilities<br/>
    3. Assess digital payment perception and adoption barriers<br/>
    4. Explore online shopping expectations<br/>
    5. Map customer journey pain points
    """
    story.append(Paragraph(objectives, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Brand Positioning: Key Findings", heading_style))
    positioning = """
    <b>How Customers Describe NexusIQ (Word Cloud Top 10):</b><br/>
    1. "Friendly" (mentioned 487 times)<br/>
    2. "Quality" (423 times)<br/>
    3. "Reliable" (398 times)<br/>
    4. "Convenient" (312 times)<br/>
    5. "Modern" (289 times - driven by Digital Wallet association)
    <br/><br/>
    <b>Competitive Comparison:</b><br/>
    • vs TechGiant: "More personal, less corporate"<br/>
    • vs ElectroMart: "Better quality, worth the price difference"<br/>
    • vs Digital Depot: "Prefer touching products before buying"<br/>
    • vs Premium Co.: "Almost as good, better value"
    <br/><br/>
    <b>Brand Archetype:</b> NexusIQ positioned as "Trusted Friend" - approachable, dependable, 
    but not cutting-edge innovative. Opportunity to add "Forward-Thinking" dimension.
    """
    story.append(Paragraph(positioning, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Digital Payment Perceptions", heading_style))
    digital_payment = """
    <b>Digital Wallet Users (31% of customers):</b><br/>
    <i>"I didn't know NexusIQ offered Digital Wallet until I saw the sign at checkout. 
    Now I use it every time."</i> - West region customer
    <br/><br/>
    <i>"The 3% discount makes a real difference on big Electronics purchases. I saved $40 
    on my laptop!"</i> - Central region customer
    <br/><br/>
    <b>Non-Users (69%):</b><br/>
    Barriers to adoption:<br/>
    • "Don't know how to set it up" (38%)<br/>
    • "Security concerns" (29%)<br/>
    • "Prefer credit card rewards" (21%)<br/>
    • "Works fine with what I have" (12%)
    <br/><br/>
    <b>Recommendation:</b> In-store demos, security education, and competitive reward programs 
    could convert 40-50% of non-users.
    """
    story.append(Paragraph(digital_payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Online Shopping Expectations", heading_style))
    online = """
    <b>The #1 Request (unprompted):</b><br/>
    <i>"I want to check online if you have something in stock before I drive to the store."</i> 
    - Mentioned by 68% of respondents
    <br/><br/>
    <b>Desired Features (ranked):</b><br/>
    1. Check in-store inventory online (81%)<br/>
    2. Buy online, pick up in store (73%)<br/>
    3. Full e-commerce (order for delivery) (67%)<br/>
    4. Product reviews and ratings (64%)<br/>
    5. Digital receipts/order history (59%)
    <br/><br/>
    <b>Competitor Comparison:</b><br/>
    TechGiant has features #1-5. ElectroMart has #1-3. <b>NexusIQ has NONE.</b>
    <br/><br/>
    <i>"I love shopping at NexusIQ, but sometimes I check TechGiant's website first to see 
    if the product exists, then come to NexusIQ to buy it."</i> - East region customer
    <br/><br/>
    <b>Opportunity Cost:</b> Estimated 15-20% of potential customers abandon purchase journey 
    before reaching store due to lack of online inventory visibility.
    """
    story.append(Paragraph(online, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Regional Perception Differences", heading_style))
    regional = """
    <b>West Region (Highest Satisfaction):</b><br/>
    "NexusIQ feels like a West Coast company - modern, tech-forward, friendly." Digital Wallet 
    adoption and Electronics purchases drive positive sentiment.
    <br/><br/>
    <b>East Region (Mature Market):</b><br/>
    "Solid, dependable, but nothing special." Opportunity to differentiate through premium 
    product curation and exclusive brands.
    <br/><br/>
    <b>Central Region (Emerging):</b><br/>
    "Great alternative to big box stores. I feel valued here." Loyalty highest in this region - 
    protect through continued personalized service.
    <br/><br/>
    <b>South Region (Improvement Needed):</b><br/>
    "Used to shop here more, but lately they're out of stock on what I want." Inventory issues 
    and Q4 weather disruptions damaged perception. Recovery critical.
    <br/><br/>
    <b>North Region (Small but Passionate):</b><br/>
    "My go-to for Home products. They understand what we need up here." Niche strength in 
    smart home - can replicate model elsewhere.
    """
    story.append(Paragraph(regional, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Customer Journey Pain Points", heading_style))
    journey = """
    <b>Pre-Purchase (Research Phase):</b><br/>
    Pain Point: "Can't browse products online before visiting store"<br/>
    Impact: 20% of potential customers visit competitor websites first, 30% don't visit at all
    <br/><br/>
    <b>In-Store (Shopping Phase):</b><br/>
    Pain Point: "Long checkout lines during weekends" (mentioned by 42%)<br/>
    Pain Point: "Hard to find staff when I need help" (23%)<br/>
    Strength: "Staff are knowledgeable when I find them" (78% positive)
    <br/><br/>
    <b>Purchase (Payment Phase):</b><br/>
    Pain Point: "Didn't know about Digital Wallet discount until after paying" (18%)<br/>
    Strength: "Multiple payment options appreciated" (84% positive)
    <br/><br/>
    <b>Post-Purchase (Retention Phase):</b><br/>
    Pain Point: "No order history or digital receipts" (37%)<br/>
    Pain Point: "Can't track loyalty points or rewards" (29%)<br/>
    Strength: "Easy returns process" (72% positive)
    """
    story.append(Paragraph(journey, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Recommendations", heading_style))
    recommendations = """
    <b>Priority 1: Digital Infrastructure (High Impact, High Effort)</b><br/>
    Launch basic e-commerce platform with inventory visibility by Q2 2025. This addresses 
    #1 customer request and prevents competitor leakage.
    <br/><br/>
    <b>Priority 2: Digital Wallet Education (High Impact, Low Effort)</b><br/>
    In-store demos, signage, staff training to increase adoption from 31% to 50%. Low cost, 
    immediate ROI.
    <br/><br/>
    <b>Priority 3: South Region Perception Repair (Medium Impact, Medium Effort)</b><br/>
    Inventory improvements + targeted "We've Changed" marketing campaign. Critical to prevent 
    further erosion.
    <br/><br/>
    <b>Priority 4: Loyalty Program Formalization (Medium Impact, Medium Effort)</b><br/>
    Customers want to track rewards. Digital Wallet integration provides foundation. Launch 
    by Q3 2025.
    <br/><br/>
    <b>Long-term Vision:</b> Position NexusIQ as "Local expertise meets modern convenience" - 
    bridge between impersonal online giants and outdated traditional retail.
    """
    story.append(Paragraph(recommendations, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Brand Perception Study Q3 2024 | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 2 Market Intelligence PDFs"""
    print("\n" + "="*70)
    print("📄 TIER 2: Market Intelligence Documents")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 Generating 5 market intelligence PDFs...\n")
    
    generate_market_analysis_electronics()
    generate_competitor_pricing_strategy()
    generate_customer_satisfaction_survey()
    generate_industry_trends_report()
    generate_brand_perception_study()
    
    print("\n" + "="*70)
    print("✅ SUCCESS: All 5 Market Intelligence PDFs Generated!")
    print("="*70)
    print(f"\n📁 Location: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  1. Market_Analysis_Electronics_2024.pdf")
    print("  2. Competitor_Pricing_Strategy.pdf")
    print("  3. Customer_Satisfaction_Survey_2024.pdf")
    print("  4. Industry_Trends_Retail_2024.pdf")
    print("  5. Brand_Perception_Study.pdf")
    
    print("\n📊 Progress Update:")
    print("├── ✅ Financial Documents (5/5)")
    print("├── ✅ Market Intelligence (5/5)")
    print("├── ⏳ Contracts & Legal (0/4)")
    print("├── ⏳ Products & Operations (0/4)")
    print("├── ⏳ Strategic Planning (0/3)")
    print("└── ⏳ HR & Compliance (0/2)")
    print("\n📈 Total Progress: 10/23 PDFs (43.5%)")
    print("\n💡 Next: Run database/generate_tier3_contracts.py\n")


if __name__ == "__main__":
    main()
