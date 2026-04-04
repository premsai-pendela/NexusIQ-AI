"""
TIER 4: Products & Operations Documents (4 documents)
Generates product catalogs, inventory policies, operations manuals, and customer policies
Location: data/pdfs/04_products_operations/
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
OUTPUT_DIR = "./data/pdfs/04_products_operations"


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
# DOCUMENT 1: Product Catalog Electronics
# ========================================

def generate_product_catalog_electronics():
    """Electronics product catalog with SKUs and specifications"""
    filename = f"{OUTPUT_DIR}/Product_Catalog_Electronics_2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("NexusIQ Electronics Product Catalog", title_style))
    story.append(Paragraph("2024 Edition - Premium Tier Products", styles['Heading3']))
    story.append(Paragraph("Effective: January 1, 2024 | Valid through December 31, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Catalog Overview", heading_style))
    overview = """
    This catalog contains NexusIQ's curated selection of premium Electronics products 
    across five subcategories. All products carry full manufacturer warranties and are 
    eligible for NexusIQ's 30-day satisfaction guarantee.
    <br/><br/>
    <b>Total SKUs in Catalog:</b> 47<br/>
    <b>Average Retail Price:</b> $847<br/>
    <b>Supplier Partners:</b> TechVendor Inc. (primary), Samsung, Apple, Sony, LG
    """
    story.append(Paragraph(overview, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Category 1: Smartphones & Accessories", heading_style))
    
    smartphones_data = [
        ['SKU', 'Product Name', 'Specs', 'Cost', 'MSRP', 'Margin'],
        ['EL-SM-001', 'Smartphone Pro 15', '256GB, 5G, OLED', '$749', '$799', '6.3%'],
        ['EL-SM-002', 'Smartphone Pro 15 Max', '512GB, 5G, OLED', '$949', '$1,099', '13.6%'],
        ['EL-SM-003', 'Budget Smartphone X3', '128GB, 4G, LCD', '$299', '$399', '25.1%'],
        ['EL-AC-101', 'Wireless Earbuds Pro', 'ANC, 30hr battery', '$249', '$279', '10.8%'],
        ['EL-AC-102', 'Phone Case Premium', 'Leather, MagSafe', '$39', '$59', '33.9%'],
    ]
    
    t = Table(smartphones_data, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
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
    
    story.append(Paragraph("Category 2: Computers & Tablets", heading_style))
    
    computers_data = [
        ['SKU', 'Product Name', 'Specs', 'Cost', 'MSRP', 'Margin'],
        ['EL-LP-001', 'UltraBook X5', 'i7, 16GB, 512GB SSD', '$1,299', '$1,349', '3.7%'],
        ['EL-LP-002', 'Gaming Laptop Z9', 'i9, 32GB, RTX 4070', '$1,899', '$2,199', '13.6%'],
        ['EL-TB-001', 'Tablet Pro 12"', 'M2, 256GB, WiFi', '$599', '$649', '7.7%'],
        ['EL-TB-002', 'Tablet Pro 12" 5G', 'M2, 512GB, 5G', '$849', '$949', '10.5%'],
        ['EL-AC-201', 'Wireless Mouse Pro', 'Ergonomic, USB-C', '$69', '$89', '22.5%'],
    ]
    
    t = Table(computers_data, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
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
    
    story.append(PageBreak())
    story.append(Paragraph("Category 3: Smart Home Devices", heading_style))
    
    smarthome_data = [
        ['SKU', 'Product Name', 'Specs', 'Cost', 'MSRP', 'Margin'],
        ['EL-SH-001', 'Smart Thermostat Pro', 'WiFi, Alexa/Google', '$189', '$229', '17.5%'],
        ['EL-SH-002', 'Smart Lighting Kit', '4 bulbs, Hub included', '$129', '$159', '18.9%'],
        ['EL-SH-003', 'Security Camera 4K', 'Indoor/Outdoor, Cloud', '$299', '$349', '14.3%'],
        ['EL-SH-004', 'Smart Door Lock', 'Keyless, Fingerprint', '$219', '$279', '21.5%'],
        ['EL-SH-005', 'Smart Speaker Pro', 'Premium audio, Alexa', '$179', '$219', '18.3%'],
    ]
    
    t = Table(smarthome_data, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
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
    
    story.append(Paragraph("Category 4: Gaming Consoles & Accessories", heading_style))
    
    gaming_data = [
        ['SKU', 'Product Name', 'Specs', 'Cost', 'MSRP', 'Margin'],
        ['EL-GM-001', 'Gaming Console Pro', '1TB, 4K/120fps', '$449', '$499', '10.0%'],
        ['EL-GM-002', 'Gaming Console Digital', '512GB, Digital only', '$349', '$399', '12.5%'],
        ['EL-GM-101', 'Pro Controller', 'Wireless, Haptic', '$59', '$79', '25.3%'],
        ['EL-GM-102', 'VR Headset Pro', '4K OLED, 120Hz', '$549', '$649', '15.4%'],
        ['EL-GM-103', 'Gaming Headset', '7.1 Surround, USB-C', '$149', '$189', '21.2%'],
    ]
    
    t = Table(gaming_data, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
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
    
    story.append(Paragraph("Category 5: Audio Equipment", heading_style))
    
    audio_data = [
        ['SKU', 'Product Name', 'Specs', 'Cost', 'MSRP', 'Margin'],
        ['EL-AU-001', 'Wireless Headphones', 'ANC, 40hr battery', '$279', '$329', '15.2%'],
        ['EL-AU-002', 'Soundbar Pro', 'Dolby Atmos, 500W', '$449', '$549', '18.2%'],
        ['EL-AU-003', 'Portable Speaker', 'Waterproof, 20hr', '$129', '$169', '23.7%'],
        ['EL-AU-004', 'Studio Monitors (pair)', 'Reference quality', '$599', '$749', '20.0%'],
        ['EL-AU-005', 'Turntable Premium', 'Bluetooth, USB out', '$349', '$449', '22.3%'],
    ]
    
    t = Table(audio_data, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
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
    
    story.append(Paragraph("Pricing Guidelines", heading_style))
    pricing_guidelines = """
    <b>Regional Pricing Adjustments:</b><br/>
    • West Region: +3% premium on all SKUs (higher COL adjustment)<br/>
    • East Region: Standard pricing as listed<br/>
    • Central Region: Standard pricing<br/>
    • South Region: -2% promotional discount (market penetration strategy)<br/>
    • North Region: +5% logistics surcharge on heavy items (furniture, large appliances)
    <br/><br/>
    <b>Promotional Bundling Recommendations:</b><br/>
    • Laptop + Mouse + Case: 10% bundle discount<br/>
    • Smart Home Starter (Thermostat + Lighting + Speaker): 15% discount<br/>
    • Gaming Console + Controller + Headset: 12% discount
    <br/><br/>
    <b>Digital Wallet Exclusive:</b> Additional 3% discount applies to all Electronics 
    purchases when customer uses Digital Wallet payment method.
    """
    story.append(Paragraph(pricing_guidelines, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Product Catalog 2024 | Electronics | Internal Use Only", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 2: Inventory Management Policy
# ========================================

def generate_inventory_policy():
    """Inventory management procedures and targets"""
    filename = f"{OUTPUT_DIR}/Inventory_Management_Policy.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Inventory Management Policy", title_style))
    story.append(Paragraph("Operations Manual - Section 4.2", styles['Heading3']))
    story.append(Paragraph("Effective Date: January 1, 2024 | Version 3.1", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. Policy Objectives", heading_style))
    objectives = """
    This policy establishes standardized inventory management procedures across all 
    NexusIQ retail locations to:
    <br/><br/>
    • Maintain optimal stock levels (minimize stockouts and overstock)<br/>
    • Achieve target inventory turnover rates by category<br/>
    • Reduce carrying costs and shrinkage<br/>
    • Enable accurate demand forecasting<br/>
    • Support customer satisfaction goals (product availability)
    """
    story.append(Paragraph(objectives, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2. Inventory Turnover Targets", heading_style))
    
    turnover_data = [
        ['Category', 'Target Days', 'Min Stock', 'Max Stock', 'Reorder Point'],
        ['Electronics', '22 days', '15 days', '35 days', 'When <20 days'],
        ['Home Goods', '28 days', '20 days', '45 days', 'When <25 days'],
        ['Clothing', '35 days', '25 days', '60 days', 'When <30 days'],
        ['Food/Grocery', '8 days', '5 days', '12 days', 'When <7 days'],
        ['Sports Equipment', '40 days', '30 days', '70 days', 'When <35 days'],
    ]
    
    t = Table(turnover_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.5*inch])
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
    
    story.append(Paragraph("3. Receiving Procedures", heading_style))
    receiving = """
    <b>3.1 Delivery Acceptance:</b><br/>
    • Verify shipment matches purchase order (quantity, SKUs)<br/>
    • Inspect for visible damage (reject if >5% of shipment damaged)<br/>
    • Sign delivery receipt only after inspection complete
    <br/><br/>
    <b>3.2 Inventory Logging:</b><br/>
    • Scan all items into inventory management system within 2 hours of receipt<br/>
    • Update stock levels in real-time (critical for online inventory visibility)<br/>
    • Tag high-value items (>$500) with security markers
    <br/><br/>
    <b>3.3 Quality Control Sampling:</b><br/>
    • Electronics: Test 10% of units (power on, basic functionality)<br/>
    • Clothing: Visual inspection for defects (stitching, sizing labels)<br/>
    • Food: Check expiration dates, temperature requirements met
    """
    story.append(Paragraph(receiving, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("4. Stock Replenishment Process", heading_style))
    replenishment = """
    <b>4.1 Automated Reordering (Preferred Method):</b><br/>
    Inventory management system generates purchase orders automatically when stock 
    reaches reorder point. Store managers review and approve daily.
    <br/><br/>
    <b>4.2 Manual Override Scenarios:</b><br/>
    • Upcoming promotions (increase stock 2 weeks prior)<br/>
    • Seasonal demand shifts (e.g., back-to-school, holidays)<br/>
    • Supplier delays (emergency orders from alternate suppliers)<br/>
    • New product launches (initial conservative order, monitor demand)
    <br/><br/>
    <b>4.3 Regional Distribution Centers:</b><br/>
    Stores can request emergency stock transfers from regional hubs:
    <br/>
    • West Region Hub (Seattle): Serves West coast stores<br/>
    • Central Region Hub (Chicago): Serves Central, North, and overflow<br/>
    • East Region Hub (Newark): Serves East coast stores
    <br/><br/>
    Lead time for inter-store transfers: 2-3 business days (standard), 
    next-day available for critical stockouts.
    """
    story.append(Paragraph(replenishment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("5. Inventory Cycle Counts", heading_style))
    cycle_counts = """
    <b>5.1 Frequency by Category:</b><br/>
    • High-value Electronics (>$1,000): Weekly cycle counts<br/>
    • Standard Electronics: Bi-weekly cycle counts<br/>
    • All other categories: Monthly cycle counts
    <br/><br/>
    <b>5.2 Variance Tolerance:</b><br/>
    • <2% variance: Acceptable, update system to match physical count<br/>
    • 2-5% variance: Investigate cause, manager approval required to adjust<br/>
    • >5% variance: Trigger full audit, notify Loss Prevention team
    <br/><br/>
    <b>5.3 Annual Physical Inventory:</b><br/>
    Complete wall-to-wall inventory count conducted in January (post-holiday season). 
    Stores close for 1 day. Results reconciled within 3 business days.
    """
    story.append(Paragraph(cycle_counts, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("6. Shrinkage Prevention", heading_style))
    shrinkage = """
    <b>Target Shrinkage Rate:</b> <1.5% of total inventory value annually
    <br/><br/>
    <b>6.1 Security Measures:</b><br/>
    • EAS tags on all items >$100<br/>
    • Locked display cases for premium Electronics (>$500)<br/>
    • CCTV coverage of high-theft zones (entrance, Electronics section)<br/>
    • Employee bag checks upon shift end (random, respectful)
    <br/><br/>
    <b>6.2 Common Shrinkage Causes:</b><br/>
    • Theft (external): 45% of shrinkage<br/>
    • Administrative errors (receiving, scanning): 30%<br/>
    • Supplier fraud (short shipments): 15%<br/>
    • Theft (internal): 10%
    <br/><br/>
    <b>6.3 Reporting:</b><br/>
    Store managers submit monthly shrinkage reports. Corporate Loss Prevention 
    analyzes trends and provides recommendations.
    """
    story.append(Paragraph(shrinkage, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("7. Seasonal Inventory Planning", heading_style))
    seasonal = """
    <b>Q1 (Jan-Mar):</b> Post-holiday clearance. Reduce inventory to baseline. 
    Prepare for spring refresh (Home category focus).
    <br/><br/>
    <b>Q2 (Apr-Jun):</b> Moderate inventory levels. Prepare for back-to-school 
    (Electronics, Clothing).
    <br/><br/>
    <b>Q3 (Jul-Sep):</b> Back-to-school peak. Electronics +40% stock, Clothing +30%. 
    Begin holiday season planning (October ordering).
    <br/><br/>
    <b>Q4 (Oct-Dec):</b> Holiday season. ALL categories +35% stock. Peak sales period 
    accounts for 38% of annual revenue. Daily inventory monitoring critical.
    """
    story.append(Paragraph(seasonal, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Inventory Management Policy v3.1 | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 3: Store Operations Manual
# ========================================

def generate_store_operations_manual():
    """Standard operating procedures for retail locations"""
    filename = f"{OUTPUT_DIR}/Store_Operations_Manual.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Store Operations Manual", title_style))
    story.append(Paragraph("Standard Operating Procedures - All Locations", styles['Heading3']))
    story.append(Paragraph("Version 2.4 | Effective January 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Section 1: Daily Opening Procedures", heading_style))
    opening = """
    <b>Start Time:</b> 30 minutes before store opening (typically 9:00am for 9:30am opening)
    <br/><br/>
    <b>1.1 Opening Checklist:</b><br/>
    ☐ Unlock front entrance (Manager on duty only)<br/>
    ☐ Disable alarm system (Manager enters security code)<br/>
    ☐ Turn on all lights (overhead, display cases, signage)<br/>
    ☐ Boot up POS (Point of Sale) systems (all registers)<br/>
    ☐ Verify cash drawers balanced from prior night close<br/>
    ☐ Check voicemail and email for corporate communications
    <br/><br/>
    <b>1.2 Store Walkthrough:</b><br/>
    ☐ Visual inspection for cleanliness (overnight cleaning crew should have completed work)<br/>
    ☐ Check restroom supplies (soap, paper towels, toilet paper)<br/>
    ☐ Verify Electronics demo units powered on and functional<br/>
    ☐ Ensure promotional signage current (check weekly promo calendar)<br/>
    ☐ Confirm emergency exits clear and accessible
    <br/><br/>
    <b>1.3 Staff Briefing (10 minutes before opening):</b><br/>
    • Review daily sales targets and promotions<br/>
    • Assign section responsibilities<br/>
    • Highlight any new product arrivals or special orders ready for pickup<br/>
    • Safety reminder of the day
    """
    story.append(Paragraph(opening, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Section 2: Customer Service Standards", heading_style))
    customer_service = """
    <b>2.1 Greeting Protocol:</b><br/>
    • Acknowledge all customers within 30 seconds of entry (eye contact, smile, "Welcome to NexusIQ!")<br/>
    • Offer assistance within 2 minutes if customer appears to be browsing<br/>
    • Use open-ended questions: "What brings you in today?" vs "Can I help you?"
    <br/><br/>
    <b>2.2 Product Knowledge Requirements:</b><br/>
    All sales associates must complete quarterly training on:
    <br/>
    • Top 20 SKUs in assigned department (features, benefits, pricing)<br/>
    • Digital Wallet payment process and benefits (3% discount promotion)<br/>
    • Current promotions and bundle offers<br/>
    • Competitor comparison points (NexusIQ advantages)
    <br/><br/>
    <b>2.3 Handling Difficult Customers:</b><br/>
    • Listen actively, don't interrupt<br/>
    • Empathize: "I understand your frustration, let me help resolve this."<br/>
    • Offer solutions (return, exchange, discount on future purchase)<br/>
    • Escalate to manager if customer requests or issue unresolved after 10 minutes<br/>
    • NEVER argue or become defensive
    <br/><br/>
    <b>2.4 Upselling Best Practices:</b><br/>
    • Suggest complementary products (laptop → mouse, case, software)<br/>
    • Mention bundle discounts when applicable<br/>
    • Highlight Digital Wallet discount as incentive for immediate purchase<br/>
    • Focus on value, not just price
    """
    story.append(Paragraph(customer_service, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Section 3: Point of Sale (POS) Procedures", heading_style))
    pos = """
    <b>3.1 Transaction Process:</b><br/>
    1. Greet customer at register<br/>
    2. Scan all items (verify prices match shelf labels)<br/>
    3. Ask: "Do you have a NexusIQ loyalty account?" (enter phone number if yes)<br/>
    4. Ask: "Would you like to use Digital Wallet today and save 3%?"<br/>
    5. Process payment (see Section 3.2 for payment methods)<br/>
    6. Provide receipt (ask: "Email or printed?")<br/>
    7. Thank customer and invite them back
    <br/><br/>
    <b>3.2 Accepted Payment Methods:</b><br/>
    • Digital Wallet (Apple Pay, Google Pay, Samsung Pay) - 3% discount applied automatically<br/>
    • Credit Card (Visa, Mastercard, Amex, Discover)<br/>
    • Debit Card (PIN or signature)<br/>
    • Cash (provide change, count back to customer)<br/>
    • NexusIQ Gift Cards<br/>
    • Check (with valid ID, manager approval for amounts >$500)
    <br/><br/>
    <b>3.3 Return/Exchange Processing:</b><br/>
    • Verify receipt (within 30 days for full refund, 31-60 days for store credit only)<br/>
    • Inspect item for damage or use (unopened Electronics preferred, some exceptions for defects)<br/>
    • Process refund to original payment method<br/>
    • No receipt? Offer store credit at lowest sale price in past 90 days (manager approval)
    """
    story.append(Paragraph(pos, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Section 4: Safety and Security", heading_style))
    safety = """
    <b>4.1 Emergency Procedures:</b><br/>
    • <b>Fire:</b> Evacuate immediately via nearest exit. Gather at designated outdoor assembly 
    point. Manager calls 911 and conducts headcount.<br/>
    • <b>Medical Emergency:</b> Call 911, render first aid if trained (AED location: break room). 
    Do not move injured person unless immediate danger.<br/>
    • <b>Active Threat:</b> Run-Hide-Fight protocol. Prioritize personal safety. Lock down 
    if safe to do so.
    <br/><br/>
    <b>4.2 Theft Prevention:</b><br/>
    • Greet all customers (deters shoplifters)<br/>
    • Monitor high-value Electronics section<br/>
    • If you witness theft in progress, DO NOT confront. Note description, notify manager and 
    Loss Prevention. Call police if theft in progress.<br/>
    • Review security camera footage post-incident
    <br/><br/>
    <b>4.3 Cash Handling Security:</b><br/>
    • Cash drawers limited to $500 max. Managers perform "drops" to safe when threshold exceeded.<br/>
    • Never leave register unattended with cash drawer open<br/>
    • Count drawer at shift change with witness present<br/>
    • Robbery protocol: Comply with demands, activate silent alarm (foot pedal under register), 
    observe details for police report
    """
    story.append(Paragraph(safety, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Section 5: Closing Procedures", heading_style))
    closing = """
    <b>Start Time:</b> 30 minutes before closing (typically 8:30pm for 9:00pm close)
    <br/><br/>
    <b>5.1 Pre-Close Activities:</b><br/>
    ☐ Announce closing time to customers ("We'll be closing in 15 minutes...")<br/>
    ☐ Begin straightening merchandise (face products, organize displays)<br/>
    ☐ Count cash drawers (preliminary count, finalize after last customer)
    <br/><br/>
    <b>5.2 Final Closing Checklist:</b><br/>
    ☐ Lock front entrance at closing time (no new customers admitted)<br/>
    ☐ Process remaining customers efficiently<br/>
    ☐ Finalize all cash drawers and prepare deposit<br/>
    ☐ Reconcile POS system (daily sales report)<br/>
    ☐ Verify all Electronics demo units powered down (except security systems)<br/>
    ☐ Turn off unnecessary lights (leave emergency/security lighting)<br/>
    ☐ Set alarm system (Manager enters code)<br/>
    ☐ Secure building (final door check, lock deadbolts)
    <br/><br/>
    <b>5.3 Deposit Procedures:</b><br/>
    Manager places cash/checks in tamper-proof deposit bag, transports to bank night drop 
    or armored car service. Never make deposit alone; always have second employee present 
    for security.
    """
    story.append(Paragraph(closing, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Store Operations Manual v2.4 | NexusIQ Corporation", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 4: Returns & Refunds Policy
# ========================================

def generate_returns_policy():
    """Customer-facing returns and refunds policy"""
    filename = f"{OUTPUT_DIR}/Returns_Refunds_Policy.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Returns & Refunds Policy", title_style))
    story.append(Paragraph("NexusIQ Customer Satisfaction Guarantee", styles['Heading3']))
    story.append(Paragraph("Effective: January 1, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Our Commitment", heading_style))
    commitment = """
    At NexusIQ, your satisfaction is our priority. We stand behind every product we sell 
    with our comprehensive 30-Day Satisfaction Guarantee. If you're not completely happy 
    with your purchase, we'll make it right.
    """
    story.append(Paragraph(commitment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Standard Return Policy", heading_style))
    standard_policy = """
    <b>Timeframe:</b> Returns accepted within 30 days of purchase date
    <br/><br/>
    <b>Condition Requirements:</b><br/>
    • Original packaging (box, manuals, accessories)<br/>
    • Product in new or like-new condition (minimal signs of use)<br/>
    • All accessories and components included<br/>
    • Valid proof of purchase (receipt or order confirmation)
    <br/><br/>
    <b>Refund Method:</b><br/>
    • Original payment method (credit card, debit card, Digital Wallet)<br/>
    • Cash purchases: Cash refund or store credit (customer choice)<br/>
    • Processing time: 3-5 business days for electronic refunds
    """
    story.append(Paragraph(standard_policy, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Category-Specific Policies", heading_style))
    
    category_policies_data = [
        ['Category', 'Return Window', 'Restocking Fee', 'Special Notes'],
        ['Electronics (unopened)', '30 days', 'None', 'Full refund'],
        ['Electronics (opened)', '14 days', '15%', 'Must be functional'],
        ['Computers/Laptops', '14 days', '20%', 'Data must be wiped'],
        ['Smart Home Devices', '30 days', 'None', 'Reset to factory settings'],
        ['Clothing', '60 days', 'None', 'Tags attached, unworn'],
        ['Food/Grocery', '7 days', 'None', 'Unopened only'],
        ['Home Goods', '30 days', 'None', 'Unassembled preferred'],
        ['Sports Equipment', '30 days', '10%', 'Minimal use acceptable'],
    ]
    
    t = Table(category_policies_data, colWidths=[1.5*inch, 1.2*inch, 1.3*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Exchanges", heading_style))
    exchanges = """
    <b>Same Product (Different Size/Color):</b><br/>
    • Free exchange within 60 days<br/>
    • No restocking fees apply<br/>
    • Price adjustments if sale occurred after original purchase
    <br/><br/>
    <b>Different Product:</b><br/>
    • Return original item (subject to return policy)<br/>
    • Purchase new item as separate transaction<br/>
    • Price difference applies
    """
    story.append(Paragraph(exchanges, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Non-Returnable Items", heading_style))
    non_returnable = """
    The following items cannot be returned or exchanged due to health, safety, or hygiene concerns:
    <br/><br/>
    • Opened software or digital content<br/>
    • Personal care items (earbuds, headphones if ear tips removed from packaging)<br/>
    • Perishable food items (after 7-day window)<br/>
    • Intimate apparel (underwear, swimwear if hygiene seal broken)<br/>
    • Custom or personalized products<br/>
    • Gift cards (unless required by law)<br/>
    • Clearance or final sale items (marked "AS IS")
    """
    story.append(Paragraph(non_returnable, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Defective Products", heading_style))
    defective = """
    <b>Manufacturer Defects:</b><br/>
    If a product is defective due to manufacturing error (not damage from use):
    <br/>
    • Return within warranty period (typically 12-24 months, see product documentation)<br/>
    • No restocking fee applies<br/>
    • Choice of: Full refund, replacement, or repair<br/>
    • NexusIQ may facilitate warranty claim with manufacturer on your behalf
    <br/><br/>
    <b>Damaged in Transit:</b><br/>
    If product arrives damaged (online orders or delivery):
    <br/>
    • Report within 48 hours of delivery<br/>
    • Provide photos of damage<br/>
    • Free replacement or full refund (including shipping costs)
    """
    story.append(Paragraph(defective, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("How to Return", heading_style))
    how_to_return = """
    <b>In-Store Returns:</b><br/>
    1. Bring item(s) and receipt to any NexusIQ location<br/>
    2. Visit Customer Service desk<br/>
    3. Associate will inspect item and process return<br/>
    4. Refund issued immediately (or within 3-5 days for card transactions)
    <br/><br/>
    <b>Online/Mail Returns (Future Capability):</b><br/>
    NexusIQ is launching e-commerce in Q2 2025. Online return process will include:
    <br/>
    • Initiate return request via nexusiq.com<br/>
    • Print prepaid return label<br/>
    • Ship item back to designated return center<br/>
    • Refund processed upon receipt and inspection (5-7 business days)
    """
    story.append(Paragraph(how_to_return, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("No Receipt Returns", heading_style))
    no_receipt = """
    We understand receipts can be lost. If you don't have proof of purchase:
    <br/><br/>
    <b>Option 1: Store Credit</b><br/>
    • Item must be in sellable condition<br/>
    • Store credit issued at lowest sale price in past 90 days<br/>
    • Valid ID required (driver's license or state ID)
    <br/><br/>
    <b>Option 2: Loyalty Account Lookup</b><br/>
    • If you provided phone number at purchase, we can locate transaction<br/>
    • Full refund to original payment method if found
    <br/><br/>
    <b>Limitations:</b><br/>
    • Maximum 3 no-receipt returns per customer per year<br/>
    • Electronics over $500 require receipt (no exceptions)
    """
    story.append(Paragraph(no_receipt, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Holiday Return Extension", heading_style))
    holiday_extension = """
    <b>November 1 - December 31 Purchases:</b><br/>
    Extended return period through January 31 of the following year
    <br/><br/>
    This gives gift recipients ample time to return or exchange items purchased during 
    the holiday season. All other return policy terms remain in effect (restocking fees, 
    condition requirements, etc.).
    """
    story.append(Paragraph(holiday_extension, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Returns & Refunds Policy | Questions? Visit any store or email support@nexusiq.com", 
                          styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 4 Products & Operations PDFs"""
    print("\n" + "="*70)
    print("📄 TIER 4: Products & Operations Documents")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 Generating 4 products/operations documents...\n")
    
    generate_product_catalog_electronics()
    generate_inventory_policy()
    generate_store_operations_manual()
    generate_returns_policy()
    
    print("\n" + "="*70)
    print("✅ SUCCESS: All 4 Products & Operations Documents Generated!")
    print("="*70)
    print(f"\n📁 Location: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  1. Product_Catalog_Electronics_2024.pdf")
    print("  2. Inventory_Management_Policy.pdf")
    print("  3. Store_Operations_Manual.pdf")
    print("  4. Returns_Refunds_Policy.pdf")
    
    print("\n📊 Progress Update:")
    print("├── ✅ Financial Documents (5/5)")
    print("├── ✅ Market Intelligence (5/5)")
    print("├── ✅ Contracts & Legal (4/4)")
    print("├── ✅ Products & Operations (4/4)")
    print("├── ⏳ Strategic Planning (0/3)")
    print("└── ⏳ HR & Compliance (0/2)")
    print("\n📈 Total Progress: 18/23 PDFs (78.3%)")
    print("\n💡 Next: Run database/generate_tier5_strategic.py\n")


if __name__ == "__main__":
    main()
