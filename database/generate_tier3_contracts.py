"""
TIER 3: Contracts & Legal Documents (4 documents)
Generates supplier agreements, service contracts, and payment terms
Location: data/pdfs/03_contracts_legal/
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
OUTPUT_DIR = "./data/pdfs/03_contracts_legal"


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
# DOCUMENT 1: TechVendor Supplier Contract
# ========================================

def generate_techvendor_contract():
    """Main Electronics supplier agreement"""
    filename = f"{OUTPUT_DIR}/Supplier_Contract_TechVendor.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("SUPPLY AGREEMENT", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Between NexusIQ Corporation and TechVendor Inc.", styles['Heading3']))
    story.append(Paragraph("Effective Date: January 1, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. PARTIES TO AGREEMENT", heading_style))
    parties = """
    This Supply Agreement ("Agreement") is entered into as of January 1, 2024, by and between:
    <br/><br/>
    <b>SUPPLIER:</b> TechVendor Inc.<br/>
    Address: 4521 Innovation Drive, San Jose, CA 95134<br/>
    Contact: Sarah Chen, VP of Sales | sarah.chen@techvendor.com
    <br/><br/>
    <b>BUYER:</b> NexusIQ Corporation<br/>
    Address: 1200 Commerce Blvd, Chicago, IL 60607<br/>
    Contact: Michael Rodriguez, Chief Procurement Officer | m.rodriguez@nexusiq.com
    """
    story.append(Paragraph(parties, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2. PRODUCTS AND PRICING", heading_style))
    story.append(Paragraph("2.1 Electronics Category - Premium Tier", styles['Heading3']))
    
    products_data = [
        ['Product Code', 'Description', 'Unit Price', 'Min Order Qty'],
        ['EL-SMART-001', 'Smartphone Pro 15', '$749', '100 units'],
        ['EL-LAPTOP-042', 'UltraBook X5', '$1,299', '50 units'],
        ['EL-TABLET-018', 'Tablet Pro 12"', '$599', '75 units'],
        ['EL-WATCH-009', 'SmartWatch Series 6', '$399', '150 units'],
        ['EL-AUDIO-033', 'Wireless Earbuds Pro', '$249', '200 units'],
    ]
    
    t = Table(products_data, colWidths=[1.3*inch, 2.2*inch, 1.2*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2.2 Volume Discount Structure", styles['Heading3']))
    discount = """
    • Orders 500-999 units/month: 5% discount<br/>
    • Orders 1,000-2,499 units/month: 8% discount<br/>
    • Orders 2,500+ units/month: 12% discount<br/>
    <br/>
    <b>Annual Commitment Bonus:</b> Additional 3% rebate if NexusIQ purchases exceed $5M 
    in calendar year 2024.
    """
    story.append(Paragraph(discount, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("3. DELIVERY AND LOGISTICS", heading_style))
    delivery = """
    <b>3.1 Delivery Schedule:</b> TechVendor commits to bi-weekly deliveries to NexusIQ 
    regional distribution centers:
    <br/>
    • West Region (Seattle, WA): Every other Monday<br/>
    • East Region (Newark, NJ): Every other Tuesday<br/>
    • Central Region (Chicago, IL): Every other Wednesday
    <br/><br/>
    <b>3.2 Lead Time:</b> Standard orders processed within 5 business days. Rush orders 
    (20% surcharge) available with 48-hour delivery.
    <br/><br/>
    <b>3.3 Shipping Terms:</b> FOB Destination. TechVendor bears all shipping costs and 
    risk of loss until products delivered to NexusIQ warehouses.
    """
    story.append(Paragraph(delivery, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("4. PAYMENT TERMS", heading_style))
    payment = """
    <b>4.1 Payment Schedule:</b> Net 45 days from invoice date.
    <br/><br/>
    <b>4.2 Early Payment Incentive:</b> 2% discount if payment received within 10 days.
    <br/><br/>
    <b>4.3 Payment Methods:</b> Wire transfer or ACH to TechVendor designated account. 
    Credit card payments accepted with 2.5% processing fee.
    <br/><br/>
    <b>4.4 Late Payment:</b> Interest charged at 1.5% per month on overdue balances.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("5. QUALITY ASSURANCE AND RETURNS", heading_style))
    quality = """
    <b>5.1 Quality Standards:</b> All products must meet ISO 9001 certification requirements. 
    Defect rate not to exceed 2% per shipment.
    <br/><br/>
    <b>5.2 Warranty:</b> TechVendor provides 12-month manufacturer warranty on all electronics. 
    Extends to 24 months for Laptop and Tablet categories.
    <br/><br/>
    <b>5.3 Return Policy:</b><br/>
    • Defective products: Full refund/replacement within 30 days<br/>
    • Overstock returns: Accepted with 15% restocking fee (max 10% of order value)<br/>
    • Damaged in transit: TechVendor replaces at no charge within 5 business days
    """
    story.append(Paragraph(quality, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("6. TERM AND TERMINATION", heading_style))
    term = """
    <b>6.1 Contract Duration:</b> This Agreement effective January 1, 2024, continuing through 
    December 31, 2025 (24 months).
    <br/><br/>
    <b>6.2 Renewal:</b> Auto-renews for successive 12-month periods unless either party provides 
    90-day written notice of non-renewal.
    <br/><br/>
    <b>6.3 Termination for Cause:</b> Either party may terminate with 30-day notice if other 
    party breaches material terms and fails to cure within 15 days.
    <br/><br/>
    <b>6.4 Termination Obligations:</b> Upon termination, NexusIQ must pay for all delivered 
    goods. TechVendor must accept return of unopened inventory purchased within 60 days of 
    termination.
    """
    story.append(Paragraph(term, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("7. AUTHORIZED SIGNATURES", heading_style))
    story.append(Spacer(1, 0.3*inch))
    
    signatures_data = [
        ['TECHVENDOR INC.', 'NEXUSIQ CORPORATION'],
        ['', ''],
        ['_________________________', '_________________________'],
        ['Sarah Chen', 'Michael Rodriguez'],
        ['VP of Sales', 'Chief Procurement Officer'],
        ['Date: January 1, 2024', 'Date: January 1, 2024'],
    ]
    
    t = Table(signatures_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 3), (-1, 4), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Confidential Business Agreement | Page 1-2", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 2: HomeGoods Supplier Contract
# ========================================

def generate_homegoods_contract():
    """Home category supplier agreement"""
    filename = f"{OUTPUT_DIR}/Supplier_Contract_HomeGoods_Inc.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("SUPPLY AGREEMENT", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Between NexusIQ Corporation and HomeGoods Inc.", styles['Heading3']))
    story.append(Paragraph("Effective Date: March 15, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. PARTIES TO AGREEMENT", heading_style))
    parties = """
    This Supply Agreement ("Agreement") is entered into as of March 15, 2024, by and between:
    <br/><br/>
    <b>SUPPLIER:</b> HomeGoods Inc.<br/>
    Address: 8900 Warehouse Pkwy, Atlanta, GA 30308<br/>
    Contact: Jennifer Martinez, Director of B2B Sales | j.martinez@homegoods-inc.com
    <br/><br/>
    <b>BUYER:</b> NexusIQ Corporation<br/>
    Address: 1200 Commerce Blvd, Chicago, IL 60607<br/>
    Contact: Michael Rodriguez, Chief Procurement Officer | m.rodriguez@nexusiq.com
    """
    story.append(Paragraph(parties, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2. PRODUCTS AND PRICING", heading_style))
    story.append(Paragraph("2.1 Home Category - Smart Home & Essentials", styles['Heading3']))
    
    products_data = [
        ['Product Code', 'Description', 'Unit Price', 'Min Order'],
        ['HM-SMART-101', 'Smart Thermostat Pro', '$189', '50 units'],
        ['HM-SMART-102', 'Smart Lighting Kit (4-pack)', '$129', '100 units'],
        ['HM-SMART-103', 'Security Camera System', '$299', '40 units'],
        ['HM-APPL-204', 'Robot Vacuum Deluxe', '$349', '30 units'],
        ['HM-FURN-305', 'Ergonomic Desk Chair', '$249', '25 units'],
        ['HM-DECOR-401', 'Home Decor Bundle', '$89', '75 units'],
    ]
    
    t = Table(products_data, colWidths=[1.3*inch, 2.2*inch, 1.2*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2.2 Pricing Structure", styles['Heading3']))
    pricing = """
    <b>Base Pricing:</b> As listed in Section 2.1
    <br/><br/>
    <b>Volume Discounts:</b><br/>
    • Monthly orders $20K-$50K: 6% discount<br/>
    • Monthly orders $50K-$100K: 10% discount<br/>
    • Monthly orders >$100K: 14% discount
    <br/><br/>
    <b>Seasonal Promotions:</b> HomeGoods offers exclusive promotional pricing during:<br/>
    • Spring Home Refresh (March-May): Additional 5% off select items<br/>
    • Holiday Season (Nov-Dec): Additional 8% off smart home products
    """
    story.append(Paragraph(pricing, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("3. DELIVERY AND LOGISTICS", heading_style))
    delivery = """
    <b>3.1 Delivery Schedule:</b> Weekly deliveries to NexusIQ regional warehouses:
    <br/>
    • North Region (Minneapolis, MN): Every Thursday<br/>
    • Central Region (Chicago, IL): Every Friday<br/>
    • South Region (Atlanta, GA): Every Monday<br/>
    • East/West Regions: Coordinated through Central hub
    <br/><br/>
    <b>3.2 Lead Time:</b> Standard orders: 7 business days. Expedited service available 
    (15% surcharge) for 3-day delivery.
    <br/><br/>
    <b>3.3 Shipping:</b> Free shipping on orders >$10K. Orders <$10K subject to $150 
    flat-rate shipping fee.
    """
    story.append(Paragraph(delivery, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("4. PAYMENT TERMS", heading_style))
    payment = """
    <b>4.1 Payment Schedule:</b> Net 30 days from invoice date.
    <br/><br/>
    <b>4.2 Early Payment Discount:</b> 1.5% discount if payment received within 7 days.
    <br/><br/>
    <b>4.3 Payment Methods:</b> ACH transfer preferred. Wire transfer and check accepted. 
    No credit card payments (high processing fees).
    <br/><br/>
    <b>4.4 Late Payment Penalty:</b> 2% monthly interest on balances overdue >15 days.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("5. INSTALLATION SERVICES", heading_style))
    installation = """
    <b>5.1 Optional Service:</b> HomeGoods offers professional installation services for 
    smart home products at additional cost:
    <br/>
    • Smart Thermostat installation: $75 per unit<br/>
    • Security Camera System setup: $150 per system<br/>
    • Smart Lighting configuration: $50 per kit
    <br/><br/>
    <b>5.2 NexusIQ Resale:</b> NexusIQ authorized to resell installation services to end 
    customers. Pricing recommendation: Cost + 40% margin.
    <br/><br/>
    <b>5.3 Technician Training:</b> HomeGoods provides free training to NexusIQ staff 
    (quarterly sessions) to enable in-house installation capabilities.
    """
    story.append(Paragraph(installation, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("6. QUALITY AND WARRANTY", heading_style))
    quality = """
    <b>6.1 Product Standards:</b> All products UL certified and meet FCC requirements for 
    smart devices.
    <br/><br/>
    <b>6.2 Warranty Coverage:</b><br/>
    • Smart home devices: 18-month manufacturer warranty<br/>
    • Furniture and decor: 12-month warranty<br/>
    • Appliances: 24-month warranty with extended service plans available
    <br/><br/>
    <b>6.3 Defect Rate Guarantee:</b> HomeGoods guarantees <1.5% defect rate. If exceeded, 
    NexusIQ receives 5% credit on next order.
    """
    story.append(Paragraph(quality, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("7. TERM AND RENEWAL", heading_style))
    term = """
    <b>7.1 Initial Term:</b> March 15, 2024 through March 14, 2026 (24 months).
    <br/><br/>
    <b>7.2 Auto-Renewal:</b> Automatically renews for 12-month periods unless 60-day 
    written notice provided by either party.
    <br/><br/>
    <b>7.3 Price Adjustments:</b> Pricing subject to annual review. Any increases capped 
    at 5% or CPI (Consumer Price Index), whichever is lower.
    """
    story.append(Paragraph(term, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Supplier Agreement - HomeGoods Inc. | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 3: Logistics Service Agreement
# ========================================

def generate_logistics_msa():
    """Master Service Agreement with logistics provider"""
    filename = f"{OUTPUT_DIR}/Master_Service_Agreement_Logistics.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("MASTER SERVICE AGREEMENT", title_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Logistics and Fulfillment Services", styles['Heading3']))
    story.append(Paragraph("Effective Date: February 1, 2024", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("PARTIES", heading_style))
    parties = """
    This Master Service Agreement ("MSA") is entered into between:
    <br/><br/>
    <b>SERVICE PROVIDER:</b> SwiftShip Logistics LLC<br/>
    Address: 2400 Distribution Way, Memphis, TN 38118<br/>
    Contact: David Park, VP of Client Services | d.park@swiftship.com
    <br/><br/>
    <b>CLIENT:</b> NexusIQ Corporation<br/>
    Address: 1200 Commerce Blvd, Chicago, IL 60607<br/>
    Contact: Lisa Thompson, VP of Operations | l.thompson@nexusiq.com
    """
    story.append(Paragraph(parties, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("1. SCOPE OF SERVICES", heading_style))
    scope = """
    SwiftShip Logistics will provide the following services to NexusIQ:
    <br/><br/>
    <b>1.1 Warehousing Services:</b><br/>
    • Receive inbound shipments from NexusIQ suppliers<br/>
    • Quality inspection and inventory logging<br/>
    • Climate-controlled storage for electronics and smart home devices<br/>
    • Real-time inventory management system integration
    <br/><br/>
    <b>1.2 Distribution Services:</b><br/>
    • Pick, pack, and ship orders to NexusIQ retail locations<br/>
    • Regional distribution hub operations (5 hubs covering all NexusIQ regions)<br/>
    • Express delivery options (same-day, next-day, 2-day)
    <br/><br/>
    <b>1.3 Reverse Logistics:</b><br/>
    • Handle product returns from retail stores<br/>
    • Inspect, restock, or dispose per NexusIQ instructions<br/>
    • Coordinate warranty claims with suppliers
    """
    story.append(Paragraph(scope, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("2. SERVICE LEVEL AGREEMENTS (SLAs)", heading_style))
    
    sla_data = [
        ['Service Type', 'Delivery Timeframe', 'On-Time %', 'Penalty if Missed'],
        ['Standard Delivery', '3-5 business days', '98%', '5% credit'],
        ['Express (2-day)', '2 business days', '99%', '10% credit'],
        ['Rush (next-day)', '1 business day', '97%', '20% credit'],
        ['Same-Day (metro)', 'Same business day', '95%', '25% credit'],
    ]
    
    t = Table(sla_data, colWidths=[1.8*inch, 1.7*inch, 1.3*inch, 1.5*inch])
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
    story.append(Paragraph("3. PRICING STRUCTURE", heading_style))
    pricing = """
    <b>3.1 Warehousing Fees:</b><br/>
    • Storage: $0.50 per cubic foot per month<br/>
    • Inbound receiving: $25 per pallet<br/>
    • Quality inspection: $2 per unit (optional)
    <br/><br/>
    <b>3.2 Distribution Fees (per shipment):</b><br/>
    • Standard delivery: $8.50 base + $0.75 per mile<br/>
    • Express (2-day): $15.00 base + $1.25 per mile<br/>
    • Rush (next-day): $25.00 base + $2.00 per mile<br/>
    • Same-day (metro only): $45.00 flat rate within 25-mile radius
    <br/><br/>
    <b>3.3 Additional Services:</b><br/>
    • White-glove delivery (furniture): $75 per shipment<br/>
    • Special handling (fragile electronics): $10 per unit<br/>
    • Weekend/holiday delivery: 50% surcharge on base rate
    <br/><br/>
    <b>3.4 Volume Discounts:</b><br/>
    • 5,000+ shipments/month: 8% discount on distribution fees<br/>
    • 10,000+ shipments/month: 12% discount on distribution fees
    """
    story.append(Paragraph(pricing, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("4. PAYMENT TERMS", heading_style))
    payment = """
    <b>4.1 Invoicing:</b> SwiftShip invoices NexusIQ monthly, by the 5th of each month 
    for prior month services.
    <br/><br/>
    <b>4.2 Payment Due:</b> Net 30 days from invoice date.
    <br/><br/>
    <b>4.3 Disputes:</b> NexusIQ must notify SwiftShip of any billing disputes within 
    10 days of invoice receipt. Undisputed amounts remain due per original terms.
    <br/><br/>
    <b>4.4 Late Payments:</b> 1.5% monthly interest on overdue balances.
    """
    story.append(Paragraph(payment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("5. LIABILITY AND INSURANCE", heading_style))
    liability = """
    <b>5.1 Cargo Insurance:</b> SwiftShip maintains $5M cargo insurance covering loss, 
    theft, or damage during transit and storage.
    <br/><br/>
    <b>5.2 Liability Limit:</b> SwiftShip liability capped at actual replacement cost 
    of goods (based on NexusIQ's documented supplier invoices) or $500K per incident, 
    whichever is lower.
    <br/><br/>
    <b>5.3 Exclusions:</b> SwiftShip not liable for:<br/>
    • Acts of God (natural disasters, severe weather)<br/>
    • Customer-caused delays (incorrect shipping addresses)<br/>
    • Inherent product defects (manufacturing issues)
    <br/><br/>
    <b>5.4 Claims Process:</b> NexusIQ must file claims within 15 days of delivery or 
    discovery of loss/damage.
    """
    story.append(Paragraph(liability, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("6. TECHNOLOGY INTEGRATION", heading_style))
    technology = """
    <b>6.1 Inventory Management System:</b> SwiftShip provides API integration with 
    NexusIQ's inventory management system for real-time stock visibility.
    <br/><br/>
    <b>6.2 Tracking:</b> All shipments tracked via GPS. NexusIQ receives automated 
    notifications at key milestones (picked up, in transit, delivered).
    <br/><br/>
    <b>6.3 Reporting:</b> Monthly performance reports including on-time %, damage rates, 
    cost analysis, and trend insights.
    """
    story.append(Paragraph(technology, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("7. TERM AND TERMINATION", heading_style))
    term = """
    <b>7.1 Initial Term:</b> February 1, 2024 through January 31, 2026 (24 months).
    <br/><br/>
    <b>7.2 Renewal:</b> Auto-renews for 12-month periods unless 90-day notice provided.
    <br/><br/>
    <b>7.3 Termination for Convenience:</b> Either party may terminate with 180-day 
    written notice (to allow transition planning).
    <br/><br/>
    <b>7.4 Termination for Cause:</b> Immediate termination allowed if SLAs missed for 
    3 consecutive months or material breach occurs.
    """
    story.append(Paragraph(term, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Master Service Agreement - SwiftShip Logistics | Confidential", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 4: Payment Terms Summary
# ========================================

def generate_payment_terms_summary():
    """Cross-contract payment terms reference document"""
    filename = f"{OUTPUT_DIR}/Payment_Terms_Summary_All_Vendors.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("Payment Terms Summary", title_style))
    story.append(Paragraph("All Vendor Contracts - Quick Reference Guide", styles['Heading3']))
    story.append(Paragraph("Document Date: January 2025 | For Internal Use Only", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Purpose", heading_style))
    purpose = """
    This document consolidates payment terms from all active supplier and service provider 
    contracts to ensure consistent cash flow management and prevent payment errors.
    <br/><br/>
    <b>Total Active Contracts:</b> 12<br/>
    <b>Monthly Payment Obligations:</b> Approximately $2.8M<br/>
    <b>Accounts Payable Contact:</b> finance@nexusiq.com
    """
    story.append(Paragraph(purpose, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Supplier Contracts - Payment Terms", heading_style))
    
    supplier_data = [
        ['Vendor', 'Category', 'Payment Terms', 'Early Pay Discount', 'Late Penalty'],
        ['TechVendor Inc.', 'Electronics', 'Net 45', '2% if paid in 10 days', '1.5%/month'],
        ['HomeGoods Inc.', 'Home/Smart Home', 'Net 30', '1.5% if paid in 7 days', '2%/month'],
        ['ApparelPro LLC', 'Clothing', 'Net 60', 'None', '1%/month'],
        ['FreshFoods Co.', 'Food/Grocery', 'Net 15', '3% if paid in 5 days', '3%/month'],
        ['SportGear Inc.', 'Sports Equipment', 'Net 30', '2% if paid in 10 days', '2%/month'],
    ]
    
    t = Table(supplier_data, colWidths=[1.5*inch, 1.3*inch, 1.2*inch, 1.5*inch, 1.2*inch])
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
    
    story.append(Paragraph("Service Provider Contracts", heading_style))
    
    service_data = [
        ['Provider', 'Service', 'Payment Terms', 'Billing Cycle', 'Late Fee'],
        ['SwiftShip Logistics', 'Warehousing/Distribution', 'Net 30', 'Monthly (5th)', '1.5%/month'],
        ['SecureGuard Inc.', 'Store Security', 'Net 15', 'Monthly (1st)', '2%/month'],
        ['CleanPro Services', 'Janitorial', 'Net 20', 'Bi-weekly', '1%/month'],
        ['TechSupport 24/7', 'IT Support', 'Net 30', 'Monthly (10th)', 'None'],
        ['MarketReach Agency', 'Marketing/Advertising', 'Net 45', 'Quarterly', '2%/month'],
    ]
    
    t = Table(service_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
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
    story.append(Paragraph("Early Payment Discount Analysis", heading_style))
    discount_analysis = """
    <b>Opportunity Cost Calculation:</b><br/>
    If NexusIQ takes advantage of ALL early payment discounts available, estimated 
    annual savings: <b>$187,000</b>
    <br/><br/>
    <b>Breakdown by Vendor:</b><br/>
    • TechVendor (Net 45 → Pay in 10): 2% on ~$5M annual = $100K savings<br/>
    • HomeGoods (Net 30 → Pay in 7): 1.5% on ~$2.5M annual = $37.5K savings<br/>
    • FreshFoods (Net 15 → Pay in 5): 3% on ~$1M annual = $30K savings<br/>
    • SportGear (Net 30 → Pay in 10): 2% on ~$1M annual = $20K savings
    <br/><br/>
    <b>Recommendation:</b> Finance team should prioritize early payments to TechVendor 
    and FreshFoods for maximum discount capture. Consider establishing revolving credit 
    line to enable early payments without impacting working capital.
    """
    story.append(Paragraph(discount_analysis, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Payment Method Preferences", heading_style))
    payment_methods = """
    <b>Preferred Methods by Vendor:</b><br/>
    • <b>ACH Transfer (8 vendors):</b> TechVendor, HomeGoods, SwiftShip, SecureGuard, 
    CleanPro, TechSupport, ApparelPro, SportGear<br/>
    • <b>Wire Transfer (2 vendors):</b> FreshFoods (perishability urgency), MarketReach (international)<br/>
    • <b>Check (2 vendors):</b> Local service providers (CleanPro accepts both ACH and check)
    <br/><br/>
    <b>Processing Times:</b><br/>
    • ACH: 2-3 business days<br/>
    • Wire: Same-day (if initiated before 2pm EST)<br/>
    • Check: 5-7 business days (mailing + clearing)
    <br/><br/>
    <b>Cost Comparison:</b><br/>
    • ACH: $0.50 per transaction<br/>
    • Wire: $25 per transaction<br/>
    • Check: $2.50 per check (printing + postage)
    """
    story.append(Paragraph(payment_methods, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Critical Payment Dates (Monthly Calendar)", heading_style))
    calendar = """
    <b>1st of Month:</b> SecureGuard invoice due<br/>
    <b>5th of Month:</b> SwiftShip Logistics invoice issued (due 35 days later)<br/>
    <b>10th of Month:</b> TechSupport 24/7 invoice issued (due 40 days later)<br/>
    <b>15th of Month:</b> TechVendor invoices typically due (Net 45 from prior month shipments)<br/>
    <b>20th of Month:</b> CleanPro bi-weekly payment due<br/>
    <b>30th of Month:</b> HomeGoods and SportGear invoices typically due (Net 30)
    <br/><br/>
    <b>Quarterly Payments:</b><br/>
    • MarketReach Agency: Jan 15, Apr 15, Jul 15, Oct 15
    """
    story.append(Paragraph(calendar, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Disputed Invoice Protocol", heading_style))
    disputes = """
    <b>Step 1:</b> Document dispute within vendor-specified timeframe (ranges from 10-15 days)
    <br/><br/>
    <b>Step 2:</b> Email vendor contact with:<br/>
    • Invoice number<br/>
    • Specific line items disputed<br/>
    • Supporting documentation (POs, delivery receipts, contracts)
    <br/><br/>
    <b>Step 3:</b> Pay undisputed portion to maintain good standing
    <br/><br/>
    <b>Step 4:</b> Escalate to vendor's AP manager if not resolved within 15 days
    <br/><br/>
    <b>Common Dispute Reasons:</b><br/>
    • Pricing discrepancy (volume discount not applied): 42% of disputes<br/>
    • Damaged goods not credited: 28%<br/>
    • Delivery quantity mismatch: 18%<br/>
    • Duplicate invoicing: 12%
    """
    story.append(Paragraph(disputes, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Internal Reference Document | Finance Department Use Only", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 3 Contracts & Legal PDFs"""
    print("\n" + "="*70)
    print("📄 TIER 3: Contracts & Legal Documents")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 Generating 4 contract documents...\n")
    
    generate_techvendor_contract()
    generate_homegoods_contract()
    generate_logistics_msa()
    generate_payment_terms_summary()
    
    print("\n" + "="*70)
    print("✅ SUCCESS: All 4 Contract Documents Generated!")
    print("="*70)
    print(f"\n📁 Location: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  1. Supplier_Contract_TechVendor.pdf")
    print("  2. Supplier_Contract_HomeGoods_Inc.pdf")
    print("  3. Master_Service_Agreement_Logistics.pdf")
    print("  4. Payment_Terms_Summary_All_Vendors.pdf")
    
    print("\n📊 Progress Update:")
    print("├── ✅ Financial Documents (5/5)")
    print("├── ✅ Market Intelligence (5/5)")
    print("├── ✅ Contracts & Legal (4/4)")
    print("├── ⏳ Products & Operations (0/4)")
    print("├── ⏳ Strategic Planning (0/3)")
    print("└── ⏳ HR & Compliance (0/2)")
    print("\n📈 Total Progress: 14/23 PDFs (60.9%)")
    print("\n💡 Next: Run database/generate_tier4_products_ops.py\n")


if __name__ == "__main__":
    main()
