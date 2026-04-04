"""
TIER 5: Strategic Planning Documents (3 documents)
Generates strategic plans, digital transformation roadmap, and expansion studies
Location: data/pdfs/05_strategic_planning/
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
OUTPUT_DIR = "./data/pdfs/05_strategic_planning"


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
# DOCUMENT 1: Strategic Plan 2025
# ========================================

def generate_strategic_plan_2025():
    """Comprehensive 2025 strategic plan with goals and KPIs"""
    filename = f"{OUTPUT_DIR}/Strategic_Plan_2025.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("Strategic Plan 2025", styles['Heading2']))
    story.append(Paragraph("Board Approved: December 15, 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    exec_summary = """
    Building on 2024's strong performance ($170M revenue, 4.6/5 customer satisfaction), 
    NexusIQ's 2025 strategy focuses on three transformational pillars: Digital Acceleration, 
    Regional Expansion, and Operational Excellence.
    <br/><br/>
    <b>2025 Targets:</b><br/>
    • Revenue: $200M (17.6% growth)<br/>
    • Operating Margin: 23.5% (up from 23.1%)<br/>
    • Digital Wallet Adoption: 45% of transactions (from 31%)<br/>
    • Customer Satisfaction: Maintain 4.6/5 or higher<br/>
    • New Store Openings: 3 (West region focus)
    """
    story.append(Paragraph(exec_summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Pillar 1: Digital Acceleration", heading_style))
    digital_accel = """
    <b>Objective:</b> Transform NexusIQ into an omnichannel leader, addressing #1 customer 
    request for online shopping capabilities.
    <br/><br/>
    <b>Initiative 1.1: E-Commerce Platform Launch (Q2 2025)</b><br/>
    Investment: $3.2M | Expected Return: $15M incremental revenue by year-end
    <br/>
    • Phase 1 (Q2): Basic e-commerce with 500 top SKUs, buy online/pick up in store (BOPIS)<br/>
    • Phase 2 (Q3): Full catalog online, home delivery option, product reviews<br/>
    • Phase 3 (Q4): AI-powered recommendations, personalized shopping experience
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • Q2: 5% of sales through online channel<br/>
    • Q3: 12% of sales online<br/>
    • Q4: 18% of sales online (industry benchmark: 28%)
    <br/><br/>
    <b>Initiative 1.2: Mobile App with Loyalty Integration (Q3 2025)</b><br/>
    Investment: $1.8M | Expected Return: 25% increase in customer retention
    <br/>
    • Features: Mobile shopping, digital receipts, loyalty point tracking, exclusive offers<br/>
    • Integration with Digital Wallet for seamless checkout<br/>
    • Push notifications for personalized promotions
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • 40,000 app downloads by Q4<br/>
    • 60% of app users make repeat purchase within 90 days
    <br/><br/>
    <b>Initiative 1.3: Digital Wallet Promotion Expansion</b><br/>
    Investment: $0.9M (marketing campaigns) | Expected Return: 50% adoption rate
    <br/>
    • Increase discount from 3% to 5% for Q1 2025 (acquisition campaign)<br/>
    • In-store demos and staff training on Digital Wallet setup<br/>
    • Partnership with Apple/Google for co-marketing
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • Q1: 38% adoption | Q2: 42% | Q3: 45% | Q4: 50%
    """
    story.append(Paragraph(digital_accel, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Strategic Pillar 2: Regional Expansion", heading_style))
    regional_expansion = """
    <b>Objective:</b> Capitalize on West region success (28% growth in 2024) by opening 
    3 flagship stores in high-potential markets.
    <br/><br/>
    <b>Initiative 2.1: San Diego Flagship Store (Opens March 2025)</b><br/>
    Investment: $3.1M | Expected Revenue: $5.2M annually (full-year run rate)
    <br/>
    • Location: Fashion Valley Mall (high-traffic, affluent demographics)<br/>
    • Store Size: 12,000 sq ft<br/>
    • Product Mix: 40% Electronics, 30% Home, 20% Clothing, 10% Other<br/>
    • Staffing: 18 employees (12 FT, 6 PT)
    <br/><br/>
    <b>Initiative 2.2: San Francisco Flagship Store (Opens June 2025)</b><br/>
    Investment: $3.5M | Expected Revenue: $6.8M annually
    <br/>
    • Location: Union Square district (tech-savvy customer base)<br/>
    • Store Size: 15,000 sq ft (largest NexusIQ location)<br/>
    • Product Mix: 50% Electronics (premium tier focus), 25% Home, 15% Clothing, 10% Other<br/>
    • Staffing: 25 employees (18 FT, 7 PT)
    <br/><br/>
    <b>Initiative 2.3: Las Vegas Flagship Store (Opens September 2025)</b><br/>
    Investment: $1.6M | Expected Revenue: $4.1M annually
    <br/>
    • Location: The District at Green Valley Ranch (growing suburban market)<br/>
    • Store Size: 10,000 sq ft<br/>
    • Product Mix: 35% Electronics, 35% Home, 20% Clothing, 10% Other<br/>
    • Staffing: 15 employees (10 FT, 5 PT)
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • All stores profitable by Month 6 of operation<br/>
    • Customer satisfaction 4.5/5 or higher within first year<br/>
    • West region contribution to total revenue: 32% (from 28.3% in 2024)
    """
    story.append(Paragraph(regional_expansion, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Strategic Pillar 3: Operational Excellence", heading_style))
    operational_excellence = """
    <b>Objective:</b> Improve efficiency, reduce costs, and enhance customer experience 
    through technology and process optimization.
    <br/><br/>
    <b>Initiative 3.1: Supply Chain Modernization</b><br/>
    Investment: $4.8M | Expected Return: $1.8M annual cost savings
    <br/>
    • Warehouse Management System (WMS) upgrade: Real-time inventory visibility<br/>
    • AI-powered demand forecasting: Reduce stockouts 40%, optimize ordering<br/>
    • Supplier Relationship Management (SRM) platform: Streamline procurement
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • Inventory turnover: 22 days (from 15 days current)<br/>
    • Stockout incidents: Reduce by 40%<br/>
    • Carrying costs: Reduce by $1.2M annually
    <br/><br/>
    <b>Initiative 3.2: South Region Recovery Plan</b><br/>
    Investment: $1.2M | Expected Return: $4M revenue recovery
    <br/>
    • Targeted marketing campaigns: "We've Changed" messaging<br/>
    • Store refresh: Merchandising improvements, signage updates<br/>
    • Staff training: Customer service excellence program<br/>
    • Local partnerships: Community engagement, sponsorships
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • Q2 2025: Revenue growth 8%+ vs Q1<br/>
    • Q4 2025: South region contribution 20% of total (from 17.3% in 2024)<br/>
    • Customer satisfaction: 4.1 → 4.4 (match company average)
    <br/><br/>
    <b>Initiative 3.3: Employee Development Program</b><br/>
    Investment: $2.1M | Expected Return: 12% productivity increase
    <br/>
    • Quarterly product knowledge training (especially Electronics, smart Home)<br/>
    • Customer service certification program<br/>
    • Leadership development for high-potential employees<br/>
    • Performance-based incentive structure
    <br/><br/>
    <b>Success Metrics:</b><br/>
    • Employee satisfaction: 4.2/5 (from 3.9/5)<br/>
    • Turnover rate: Reduce to 18% (from 24%)<br/>
    • Internal promotion rate: 30% of management positions filled internally
    """
    story.append(Paragraph(operational_excellence, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("2025 Financial Plan Summary", heading_style))
    
    financial_data = [
        ['Metric', 'Q1', 'Q2', 'Q3', 'Q4', '2025 Total'],
        ['Revenue', '$42M', '$48M', '$52M', '$58M', '$200M'],
        ['Gross Margin', '36%', '37%', '38%', '38%', '37.5%'],
        ['Operating Margin', '22%', '23%', '24%', '24%', '23.5%'],
        ['CapEx', '$5.2M', '$6.1M', '$4.8M', '$2.4M', '$18.5M'],
        ['OpEx', '$5.8M', '$6.2M', '$6.1M', '$5.7M', '$23.8M'],
    ]
    
    t = Table(financial_data, colWidths=[1.3*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1.2*inch])
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
    
    story.append(Paragraph("Key Performance Indicators (KPIs)", heading_style))
    kpis = """
    <b>Customer Metrics:</b><br/>
    • Customer Satisfaction Score: Maintain 4.6/5 or higher<br/>
    • Net Promoter Score (NPS): +65 or higher (currently +58)<br/>
    • Repeat Purchase Rate: 55% (from 48%)
    <br/><br/>
    <b>Digital Metrics:</b><br/>
    • Digital Wallet Adoption: 50% by Q4<br/>
    • Online Sales Contribution: 18% by Q4<br/>
    • Mobile App Active Users: 40,000 by Q4
    <br/><br/>
    <b>Operational Metrics:</b><br/>
    • Inventory Turnover: 22 days (from 15 days)<br/>
    • Employee Turnover: <18% (from 24%)<br/>
    • Shrinkage Rate: <1.2% (from 1.5%)
    <br/><br/>
    <b>Financial Metrics:</b><br/>
    • Revenue Growth: 17.6%<br/>
    • Operating Margin: 23.5%<br/>
    • ROIC (Return on Invested Capital): 22%
    """
    story.append(Paragraph(kpis, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Risk Mitigation Strategies", heading_style))
    risks = """
    <b>Risk 1: Economic Downturn</b><br/>
    Mitigation: 6.4% contingency reserve ($2.7M). Can defer Q3/Q4 store openings and scale 
    back marketing if consumer spending weakens.
    <br/><br/>
    <b>Risk 2: E-Commerce Platform Delays</b><br/>
    Mitigation: Phased rollout approach. MVP launch Q2 with core features only. Full 
    functionality can slip to Q4 if needed without major revenue impact.
    <br/><br/>
    <b>Risk 3: Competitive Pressure (TechGiant, ElectroMart)</b><br/>
    Mitigation: Differentiate through superior customer service (4.6/5 vs 3.9/5 industry), 
    Digital Wallet innovation, and regional expertise. Monitor competitor pricing weekly.
    <br/><br/>
    <b>Risk 4: Talent Acquisition/Retention</b><br/>
    Mitigation: Competitive compensation packages, internal promotion opportunities, and 
    comprehensive training programs. Employee satisfaction target: 4.2/5.
    """
    story.append(Paragraph(risks, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Strategic Plan 2025 | Confidential - Board Approved", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 2: Digital Transformation Roadmap
# ========================================

def generate_digital_transformation_roadmap():
    """Detailed digital transformation implementation plan"""
    filename = f"{OUTPUT_DIR}/Digital_Transformation_Roadmap.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Digital Transformation Roadmap", title_style))
    story.append(Paragraph("2025-2026 Technology Modernization Plan", styles['Heading3']))
    story.append(Paragraph("Project Charter | Approved: January 2025", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Vision Statement", heading_style))
    vision = """
    <i>"Position NexusIQ as a digitally-enabled retail leader that seamlessly blends 
    in-store expertise with online convenience, delivering personalized experiences 
    across all customer touchpoints."</i>
    <br/><br/>
    By end of 2026, NexusIQ will have fully integrated omnichannel capabilities, 
    AI-powered personalization, and a best-in-class digital payment ecosystem.
    """
    story.append(Paragraph(vision, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Current State Assessment", heading_style))
    current_state = """
    <b>Digital Maturity Score: 4.2 / 10</b> (Industry average: 6.1)
    <br/><br/>
    <b>Strengths:</b><br/>
    • Digital Wallet adoption: 31% (above industry 22%)<br/>
    • Modern POS systems with cloud integration<br/>
    • Real-time inventory tracking (in-store only)
    <br/><br/>
    <b>Gaps:</b><br/>
    • No e-commerce platform (0% online sales vs industry 28%)<br/>
    • No mobile app<br/>
    • No customer data platform (CDP) for personalization<br/>
    • Limited analytics capabilities (basic reporting only)<br/>
    • Manual processes in supply chain (no AI/ML)
    """
    story.append(Paragraph(current_state, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Transformation Roadmap (2025-2026)", heading_style))
    
    roadmap_data = [
        ['Phase', 'Timeline', 'Investment', 'Key Deliverables'],
        ['Phase 1: Foundation', 'Q1-Q2 2025', '$4.5M', 'E-commerce MVP, CDP, Analytics'],
        ['Phase 2: Expansion', 'Q3-Q4 2025', '$3.8M', 'Mobile app, AI recommendations'],
        ['Phase 3: Optimization', 'Q1-Q2 2026', '$2.9M', 'Marketing automation, AR/VR'],
        ['Phase 4: Innovation', 'Q3-Q4 2026', '$2.2M', 'Voice commerce, IoT integration'],
    ]
    
    t = Table(roadmap_data, colWidths=[1.5*inch, 1.3*inch, 1.2*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Phase 1: Foundation (Q1-Q2 2025)", heading_style))
    phase1 = """
    <b>Project 1.1: E-Commerce Platform MVP</b><br/>
    Budget: $3.2M | Timeline: 16 weeks | Go-Live: May 2025
    <br/><br/>
    <b>Technology Stack:</b><br/>
    • Platform: Shopify Plus (fast time-to-market, proven scalability)<br/>
    • Payment Gateway: Stripe (supports Digital Wallet, credit/debit cards)<br/>
    • Hosting: AWS (auto-scaling, 99.9% uptime SLA)<br/>
    • CMS: Contentful (headless CMS for flexibility)
    <br/><br/>
    <b>Features (MVP):</b><br/>
    • Product catalog: Top 500 SKUs (expand to full catalog in Phase 2)<br/>
    • Shopping cart and checkout<br/>
    • Buy Online, Pick Up In Store (BOPIS)<br/>
    • Real-time inventory visibility (integrated with POS)<br/>
    • Account creation and order history<br/>
    • Digital Wallet integration (3% discount applied automatically)
    <br/><br/>
    <b>Success Criteria:</b><br/>
    • Site uptime: >99.5%<br/>
    • Page load time: <2 seconds<br/>
    • Conversion rate: >2.5% (industry benchmark)
    <br/><br/>
    <b>Project 1.2: Customer Data Platform (CDP)</b><br/>
    Budget: $0.8M | Timeline: 12 weeks | Go-Live: April 2025
    <br/><br/>
    <b>Technology:</b> Segment (leading CDP, integrates with all major tools)
    <br/><br/>
    <b>Capabilities:</b><br/>
    • Unified customer profiles (online + in-store behavior)<br/>
    • Segmentation engine (demographic, behavioral, predictive)<br/>
    • Real-time event tracking (page views, purchases, cart abandons)<br/>
    • Integration with email marketing, POS, e-commerce platform
    <br/><br/>
    <b>Use Cases:</b><br/>
    • Personalized email campaigns (abandoned cart recovery, product recommendations)<br/>
    • In-store staff can view customer purchase history (better service)<br/>
    • Identify high-value customers for VIP treatment
    <br/><br/>
    <b>Project 1.3: Analytics & Reporting Platform</b><br/>
    Budget: $0.5M | Timeline: 8 weeks | Go-Live: March 2025
    <br/><br/>
    <b>Technology:</b> Google Analytics 4 + Looker (data visualization)
    <br/><br/>
    <b>Dashboards:</b><br/>
    • Executive Dashboard: Revenue, margins, customer acquisition cost (CAC)<br/>
    • Marketing Dashboard: Campaign performance, channel attribution, ROI<br/>
    • Operations Dashboard: Inventory turns, stockouts, shrinkage<br/>
    • Store Manager Dashboard: Daily sales, foot traffic, conversion rates
    """
    story.append(Paragraph(phase1, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Phase 2: Expansion (Q3-Q4 2025)", heading_style))
    phase2 = """
    <b>Project 2.1: Mobile App Launch</b><br/>
    Budget: $1.8M | Timeline: 20 weeks | Go-Live: September 2025
    <br/><br/>
    <b>Technology Stack:</b><br/>
    • Framework: React Native (iOS + Android from single codebase)<br/>
    • Backend: Firebase (real-time sync, push notifications)<br/>
    • Payment: Apple Pay, Google Pay (one-tap checkout)
    <br/><br/>
    <b>Features:</b><br/>
    • Mobile shopping (full product catalog)<br/>
    • Barcode scanner (check prices, read reviews in-store)<br/>
    • Digital receipts (paperless, searchable order history)<br/>
    • Loyalty program integration (track points, redeem rewards)<br/>
    • Push notifications (personalized offers, back-in-stock alerts)<br/>
    • Store locator with real-time inventory by location
    <br/><br/>
    <b>Monetization:</b><br/>
    • 5% app-exclusive discount (drives downloads)<br/>
    • Early access to sales for app users<br/>
    • Gamification (badges, challenges for engagement)
    <br/><br/>
    <b>Success Criteria:</b><br/>
    • 40,000 downloads by Q4 2025<br/>
    • 30% monthly active user rate<br/>
    • 4.2+ star rating in App Store / Google Play
    <br/><br/>
    <b>Project 2.2: AI Recommendation Engine</b><br/>
    Budget: $1.2M | Timeline: 16 weeks | Go-Live: October 2025
    <br/><br/>
    <b>Technology:</b> AWS Personalize (managed machine learning service)
    <br/><br/>
    <b>Recommendation Types:</b><br/>
    • Product recommendations (frequently bought together, similar items)<br/>
    • Personalized homepage (tailored to browsing/purchase history)<br/>
    • Email recommendations (re-engagement campaigns)<br/>
    • In-app recommendations (push notification targeting)
    <br/><br/>
    <b>Expected Impact:</b><br/>
    • 15% increase in average order value (AOV)<br/>
    • 20% increase in cross-sell rate<br/>
    • 10% improvement in email click-through rates
    <br/><br/>
    <b>Project 2.3: E-Commerce Full Catalog Expansion</b><br/>
    Budget: $0.8M | Timeline: 12 weeks | Go-Live: November 2025
    <br/><br/>
    <b>Deliverables:</b><br/>
    • All 2,500+ SKUs available online (from MVP 500)<br/>
    • Product reviews and ratings (integrated with Yotpo)<br/>
    • Advanced search and filtering (faceted search by brand, price, features)<br/>
    • Wishlist functionality<br/>
    • Gift registry (weddings, baby showers)
    """
    story.append(Paragraph(phase2, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Phase 3: Optimization (Q1-Q2 2026)", heading_style))
    phase3 = """
    <b>Project 3.1: Marketing Automation Platform</b><br/>
    Budget: $1.1M | Timeline: 14 weeks | Go-Live: March 2026
    <br/><br/>
    <b>Technology:</b> HubSpot Marketing Hub (enterprise tier)
    <br/><br/>
    <b>Automation Workflows:</b><br/>
    • Welcome series (new customer onboarding, 5-email sequence)<br/>
    • Abandoned cart recovery (3-email sequence, progressive discounts)<br/>
    • Post-purchase follow-up (review requests, cross-sell)<br/>
    • Re-engagement (dormant customers, win-back campaigns)<br/>
    • VIP nurture (high-value customer exclusive offers)
    <br/><br/>
    <b>Expected Impact:</b><br/>
    • Recover 15% of abandoned carts (est. $2.3M annual revenue)<br/>
    • Increase repeat purchase rate from 48% to 60%<br/>
    • Reduce customer acquisition cost (CAC) by 22%
    <br/><br/>
    <b>Project 3.2: Augmented Reality (AR) Try-Before-You-Buy</b><br/>
    Budget: $0.9M | Timeline: 16 weeks | Go-Live: May 2026
    <br/><br/>
    <b>Technology:</b> Google ARCore / Apple ARKit
    <br/><br/>
    <b>Use Cases:</b><br/>
    • Furniture placement (see how couch looks in your living room)<br/>
    • Smart home device visualization (thermostat on your wall)<br/>
    • Virtual try-on for accessories (watches, glasses - future phase)
    <br/><br/>
    <b>Target Categories:</b> Home Goods (Phase 3), expand to other categories in Phase 4
    <br/><br/>
    <b>Expected Impact:</b><br/>
    • Reduce furniture return rate from 12% to 6%<br/>
    • Increase Home category conversion rate by 25%
    <br/><br/>
    <b>Project 3.3: Advanced Inventory Forecasting (AI/ML)</b><br/>
    Budget: $0.9M | Timeline: 12 weeks | Go-Live: April 2026
    <br/><br/>
    <b>Technology:</b> Azure Machine Learning
    <br/><br/>
    <b>Models:</b><br/>
    • Demand forecasting (predict sales 30-90 days out by SKU/location)<br/>
    • Anomaly detection (identify unusual patterns, prevent stockouts)<br/>
    • Price optimization (dynamic pricing based on demand, competition)
    <br/><br/>
    <b>Expected Impact:</b><br/>
    • Reduce stockouts by 50%<br/>
    • Improve inventory turnover from 22 days to 18 days<br/>
    • Increase gross margin by 1.5 percentage points (optimized pricing)
    """
    story.append(Paragraph(phase3, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Phase 4: Innovation (Q3-Q4 2026)", heading_style))
    phase4 = """
    <b>Project 4.1: Voice Commerce Integration</b><br/>
    Budget: $1.2M | Timeline: 18 weeks | Go-Live: October 2026
    <br/><br/>
    <b>Platforms:</b> Amazon Alexa, Google Assistant, Siri Shortcuts
    <br/><br/>
    <b>Capabilities:</b><br/>
    • Voice ordering (reorder frequently purchased items)<br/>
    • Product search and recommendations<br/>
    • Order tracking and customer service queries<br/>
    • Store locator and hours
    <br/><br/>
    <b>Target Adoption:</b> 5% of online orders via voice by end of 2027
    <br/><br/>
    <b>Project 4.2: IoT Integration (Smart Home Ecosystem)</b><br/>
    Budget: $1.0M | Timeline: 16 weeks | Go-Live: December 2026
    <br/><br/>
    <b>Use Cases:</b><br/>
    • Smart fridges: Auto-order groceries when low (Food category)<br/>
    • Smart thermostats: Suggest energy-efficient settings, order replacement filters<br/>
    • Connected devices: Monitor product usage, proactive support
    <br/><br/>
    <b>Strategic Goal:</b> Build NexusIQ ecosystem lock-in (Amazon model)
    """
    story.append(Paragraph(phase4, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Governance & Change Management", heading_style))
    governance = """
    <b>Program Leadership:</b><br/>
    • Executive Sponsor: CTO (Chief Technology Officer)<br/>
    • Program Director: VP of Digital Transformation (new hire Q1 2025)<br/>
    • Steering Committee: CEO, CFO, CMO, CTO (monthly reviews)
    <br/><br/>
    <b>Change Management:</b><br/>
    • Employee training: 40 hours per employee on new systems<br/>
    • Champion network: 2-3 "digital ambassadors" per store<br/>
    • Communication cadence: Weekly updates, monthly town halls<br/>
    • Incentive alignment: 15% of bonus tied to digital KPIs
    """
    story.append(Paragraph(governance, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Digital Transformation Roadmap | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 3: Expansion Feasibility Study
# ========================================

def generate_expansion_feasibility_study():
    """West region expansion market analysis and financial modeling"""
    filename = f"{OUTPUT_DIR}/Expansion_Feasibility_Study.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("West Region Expansion Feasibility Study", title_style))
    story.append(Paragraph("Market Analysis: San Diego, San Francisco, Las Vegas", styles['Heading3']))
    story.append(Paragraph("Prepared by: Strategic Planning Team | December 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Executive Summary", heading_style))
    exec_summary = """
    This study evaluates the feasibility of opening three flagship NexusIQ stores in 
    the West region during 2025. Based on market analysis, demographic trends, and 
    financial modeling, we recommend proceeding with all three locations.
    <br/><br/>
    <b>Key Findings:</b><br/>
    • Combined addressable market: $2.1B annually (our target: 0.8% share = $16M)<br/>
    • Payback period: 18-24 months per store<br/>
    • IRR (Internal Rate of Return): 28% (exceeds 15% hurdle rate)<br/>
    • Risk rating: Moderate (competitive but proven market demand)
    """
    story.append(Paragraph(exec_summary, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market 1: San Diego, California", heading_style))
    san_diego = """
    <b>Demographics:</b><br/>
    • Population: 1.4M (metro area: 3.3M)<br/>
    • Median Household Income: $89,000<br/>
    • Age 25-54 (target demo): 42% of population<br/>
    • Tech employment: 18% (above national 12%)
    <br/><br/>
    <b>Competitive Landscape:</b><br/>
    • TechGiant: 2 stores in metro area<br/>
    • ElectroMart: 3 stores (heavy price competition)<br/>
    • Digital Depot: Online only (no physical presence)<br/>
    • NexusIQ advantage: Premium service, Digital Wallet leadership
    <br/><br/>
    <b>Proposed Location:</b> Fashion Valley Mall
    <br/>
    • Foot traffic: 18M visitors annually<br/>
    • Anchor tenants: Nordstrom, Apple Store, Tesla<br/>
    • Rent: $85/sq ft (12,000 sq ft = $1.02M annual lease cost)
    <br/><br/>
    <b>Financial Projections (Year 1):</b><br/>
    • Revenue: $5.2M<br/>
    • Gross Margin: 38% ($1.98M)<br/>
    • Operating Expenses: $1.65M (including rent, payroll, marketing)<br/>
    • EBITDA: $330K (6.3% margin)
    <br/><br/>
    <b>Payback Period:</b> 22 months<br/>
    <b>5-Year NPV:</b> $2.8M (at 10% discount rate)
    """
    story.append(Paragraph(san_diego, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Market 2: San Francisco, California", heading_style))
    san_francisco = """
    <b>Demographics:</b><br/>
    • Population: 875K (metro area: 4.7M Bay Area)<br/>
    • Median Household Income: $126,000 (highest among 3 markets)<br/>
    • Age 25-54: 48% of population<br/>
    • Tech employment: 31% (Silicon Valley proximity)
    <br/><br/>
    <b>Competitive Landscape:</b><br/>
    • TechGiant: 4 stores (flagship Union Square location)<br/>
    • Premium Electronics Co.: 1 store (luxury positioning)<br/>
    • ElectroMart: 2 stores (suburban locations only)<br/>
    • NexusIQ opportunity: Mid-premium positioning, superior service
    <br/><br/>
    <b>Proposed Location:</b> Union Square District
    <br/>
    • Foot traffic: 24M visitors annually (highest of 3 locations)<br/>
    • Anchor tenants: Apple Store, Nike, Westfield Mall<br/>
    • Rent: $125/sq ft (15,000 sq ft = $1.88M annual lease cost) - EXPENSIVE but justified
    <br/><br/>
    <b>Financial Projections (Year 1):</b><br/>
    • Revenue: $6.8M (highest revenue potential)<br/>
    • Gross Margin: 40% ($2.72M) - premium product mix<br/>
    • Operating Expenses: $2.35M (high rent, but also higher payroll for premium staff)<br/>
    • EBITDA: $370K (5.4% margin)
    <br/><br/>
    <b>Payback Period:</b> 24 months (longest but highest upside)<br/>
    <b>5-Year NPV:</b> $3.6M (highest NPV of 3 locations)
    <br/><br/>
    <b>Strategic Rationale:</b> San Francisco is a "statement" location. Establishes 
    NexusIQ as a serious player in premium tech retail. Halo effect benefits other stores 
    (brand credibility).
    """
    story.append(Paragraph(san_francisco, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Market 3: Las Vegas, Nevada", heading_style))
    las_vegas = """
    <b>Demographics:</b><br/>
    • Population: 650K (metro area: 2.2M)<br/>
    • Median Household Income: $64,000 (lowest of 3, but growing fast)<br/>
    • Age 25-54: 39% of population<br/>
    • Population growth: 2.1% annually (vs US 0.5%) - fastest growing major metro
    <br/><br/>
    <b>Competitive Landscape:</b><br/>
    • ElectroMart: 3 stores (dominant player)<br/>
    • TechGiant: 1 store (Strip location, tourist-focused)<br/>
    • Regional retailers: Limited presence<br/>
    • NexusIQ opportunity: Suburban growth corridor underserved
    <br/><br/>
    <b>Proposed Location:</b> The District at Green Valley Ranch
    <br/>
    • Foot traffic: 12M visitors annually<br/>
    • Anchor tenants: Whole Foods, REI, Crate & Barrel<br/>
    • Rent: $55/sq ft (10,000 sq ft = $550K annual lease cost) - LOWEST cost
    <br/><br/>
    <b>Financial Projections (Year 1):</b><br/>
    • Revenue: $4.1M<br/>
    • Gross Margin: 36% ($1.48M)<br/>
    • Operating Expenses: $1.15M (lowest operating costs of 3)<br/>
    • EBITDA: $330K (8.0% margin - HIGHEST margin)
    <br/><br/>
    <b>Payback Period:</b> 18 months (FASTEST payback)<br/>
    <b>5-Year NPV:</b> $2.3M
    <br/><br/>
    <b>Strategic Rationale:</b> Las Vegas is the "safe bet." Lowest investment risk, 
    fastest payback. Tests our suburban model (vs urban San Diego/SF). If successful, 
    template for future Southwestern expansion (Phoenix, Albuquerque).
    """
    story.append(Paragraph(las_vegas, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Comparative Financial Analysis", heading_style))
    
    comparison_data = [
        ['Metric', 'San Diego', 'San Francisco', 'Las Vegas', 'Combined'],
        ['Investment', '$3.1M', '$3.5M', '$1.6M', '$8.2M'],
        ['Year 1 Revenue', '$5.2M', '$6.8M', '$4.1M', '$16.1M'],
        ['Year 1 EBITDA', '$330K', '$370K', '$330K', '$1.03M'],
        ['EBITDA Margin', '6.3%', '5.4%', '8.0%', '6.4%'],
        ['Payback Period', '22 months', '24 months', '18 months', '21 avg'],
        ['5-Year NPV', '$2.8M', '$3.6M', '$2.3M', '$8.7M'],
        ['IRR', '26%', '24%', '34%', '28%'],
    ]
    
    t = Table(comparison_data, colWidths=[1.5*inch, 1.1*inch, 1.3*inch, 1.1*inch, 1.1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Risk Assessment", heading_style))
    risk_assessment = """
    <b>Market Risk (Moderate):</b><br/>
    • San Diego/SF: Competitive markets but proven demand. Our differentiation (service, 
    Digital Wallet) resonates with target demographics.<br/>
    • Las Vegas: Less competitive, but lower income levels may pressure margins.
    <br/><br/>
    <b>Execution Risk (Moderate):</b><br/>
    • Opening 3 stores in 6 months strains resources (hiring, training, inventory)<br/>
    • Mitigation: Stagger openings (Mar, Jun, Sep), hire experienced store managers early
    <br/><br/>
    <b>Financial Risk (Low):</b><br/>
    • 28% IRR well above hurdle rate (15%)<br/>
    • Payback within 2 years provides cushion<br/>
    • Diversified across 3 markets reduces concentration risk
    <br/><br/>
    <b>Cannibalization Risk (Low):</b><br/>
    • Existing West region stores (Seattle, Portland, LA) 300+ miles from new locations<br/>
    • Different trade areas, minimal overlap
    """
    story.append(Paragraph(risk_assessment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Recommendations", heading_style))
    recommendations = """
    <b>1. PROCEED with all three locations</b> - Financial returns exceed hurdle rates, 
    strategic benefits (West region dominance) justify investment.
    <br/><br/>
    <b>2. Prioritize Las Vegas (September opening)</b> - Allow time to learn from San Diego/SF 
    before launching lowest-risk, highest-margin location.
    <br/><br/>
    <b>3. Invest in pre-opening marketing</b> - Allocate $300K per location (90 days prior) 
    for brand awareness, grand opening events.
    <br/><br/>
    <b>4. Staff early and train well</b> - Hire store managers 120 days before opening, 
    staff 60 days before. Intensive training on NexusIQ service standards.
    <br/><br/>
    <b>5. Monitor KPIs weekly (first 6 months)</b> - Foot traffic, conversion rate, average 
    transaction value, customer satisfaction. Course-correct quickly if underperforming.
    """
    story.append(Paragraph(recommendations, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Expansion Feasibility Study | Confidential - Strategic Planning", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 5 Strategic Planning PDFs"""
    print("\n" + "="*70)
    print("📄 TIER 5: Strategic Planning Documents")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 Generating 3 strategic planning documents...\n")
    
    generate_strategic_plan_2025()
    generate_digital_transformation_roadmap()
    generate_expansion_feasibility_study()
    
    print("\n" + "="*70)
    print("✅ SUCCESS: All 3 Strategic Planning Documents Generated!")
    print("="*70)
    print(f"\n📁 Location: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  1. Strategic_Plan_2025.pdf")
    print("  2. Digital_Transformation_Roadmap.pdf")
    print("  3. Expansion_Feasibility_Study.pdf")
    
    print("\n📊 Progress Update:")
    print("├── ✅ Financial Documents (5/5)")
    print("├── ✅ Market Intelligence (5/5)")
    print("├── ✅ Contracts & Legal (4/4)")
    print("├── ✅ Products & Operations (4/4)")
    print("├── ✅ Strategic Planning (3/3)")
    print("└── ⏳ HR & Compliance (0/2)")
    print("\n📈 Total Progress: 21/23 PDFs (91.3%)")
    print("\n💡 FINAL TIER: Run database/generate_tier6_hr_compliance.py\n")


if __name__ == "__main__":
    main()
