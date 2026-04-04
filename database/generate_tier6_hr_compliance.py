"""
TIER 6: HR & Compliance Documents (2 documents)
Generates employee handbook and compliance training materials
Location: data/pdfs/06_hr_compliance/
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
OUTPUT_DIR = "./data/pdfs/06_hr_compliance"


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
# DOCUMENT 1: Employee Handbook
# ========================================

def generate_employee_handbook():
    """Comprehensive employee handbook with policies and procedures"""
    filename = f"{OUTPUT_DIR}/Employee_Handbook_2024.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("NexusIQ Corporation", title_style))
    story.append(Paragraph("Employee Handbook 2024", styles['Heading2']))
    story.append(Paragraph("Your Guide to Success at NexusIQ", styles['Heading3']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Welcome to NexusIQ!", heading_style))
    welcome = """
    Dear NexusIQ Team Member,
    <br/><br/>
    Welcome to the NexusIQ family! We're thrilled to have you join our team of dedicated 
    professionals committed to delivering exceptional customer experiences.
    <br/><br/>
    At NexusIQ, we believe that our employees are our greatest asset. This handbook outlines 
    the policies, benefits, and expectations that will guide your journey with us. Please 
    read it carefully and keep it for future reference.
    <br/><br/>
    Together, we're transforming retail through innovation, integrity, and outstanding service.
    <br/><br/>
    <i>Michael J. Patterson</i><br/>
    <i>Chief Executive Officer</i>
    """
    story.append(Paragraph(welcome, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Our Mission & Values", heading_style))
    mission = """
    <b>Mission:</b> To provide customers with exceptional products and personalized service, 
    powered by innovative technology and delivered by passionate team members.
    <br/><br/>
    <b>Core Values:</b>
    <br/><br/>
    <b>1. Customer First:</b> Every decision starts with "How does this benefit our customer?"
    <br/><br/>
    <b>2. Innovation:</b> We embrace change and continuously seek better ways to serve. Our 
    Digital Wallet leadership and omnichannel strategy exemplify this commitment.
    <br/><br/>
    <b>3. Integrity:</b> We do the right thing, even when no one is watching. Honesty and 
    transparency guide all our interactions.
    <br/><br/>
    <b>4. Teamwork:</b> We succeed together. Every department, every role contributes to 
    our collective success.
    <br/><br/>
    <b>5. Excellence:</b> Good enough never is. We strive for 4.6/5 customer satisfaction 
    and beyond.
    """
    story.append(Paragraph(mission, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Employment Policies", heading_style))
    employment = """
    <b>Employment Classification:</b><br/>
    • <b>Full-Time:</b> 32+ hours per week, eligible for full benefits<br/>
    • <b>Part-Time:</b> Less than 32 hours per week, eligible for limited benefits<br/>
    • <b>Seasonal:</b> Temporary employment (typically Oct-Jan), limited benefits
    <br/><br/>
    <b>Equal Opportunity Employment:</b><br/>
    NexusIQ is an equal opportunity employer. We prohibit discrimination based on race, 
    color, religion, sex, national origin, age, disability, veteran status, sexual 
    orientation, gender identity, or any other protected characteristic.
    <br/><br/>
    <b>At-Will Employment:</b><br/>
    Employment with NexusIQ is at-will. Either the employee or NexusIQ may terminate 
    the employment relationship at any time, with or without cause or notice.
    <br/><br/>
    <b>Background Checks:</b><br/>
    All employment offers are contingent upon successful completion of a background check. 
    Positions handling cash or sensitive data may require additional screening.
    <br/><br/>
    <b>Introductory Period:</b><br/>
    New employees complete a 90-day introductory period. During this time, performance 
    is closely monitored, and feedback is provided regularly. Benefits eligibility 
    begins after successful completion of this period.
    """
    story.append(Paragraph(employment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Compensation & Benefits", heading_style))
    compensation = """
    <b>Pay Schedule:</b><br/>
    • Hourly employees: Paid bi-weekly (every other Friday)<br/>
    • Salaried employees: Paid semi-monthly (15th and last day of month)<br/>
    • Direct deposit available and encouraged
    <br/><br/>
    <b>Overtime:</b><br/>
    Non-exempt employees receive 1.5x regular rate for hours worked beyond 40 per week. 
    Overtime must be pre-approved by your manager.
    <br/><br/>
    <b>Performance Bonuses:</b><br/>
    • Store employees: Quarterly bonus based on store performance (up to 5% of base pay)<br/>
    • Managers: Annual bonus based on regional/company performance (up to 15% of salary)<br/>
    • Digital adoption bonus: $50 for each customer you help sign up for Digital Wallet
    """
    story.append(Paragraph(compensation, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Benefits Summary (Full-Time Employees):</b>", styles['Normal']))
    
    benefits_data = [
        ['Benefit', 'Coverage', 'NexusIQ Contribution'],
        ['Health Insurance', 'Medical, Dental, Vision', '75% of premium'],
        ['401(k) Retirement', '6% match', '100% match up to 6%'],
        ['Paid Time Off (PTO)', '15 days Year 1, +1/year', 'N/A'],
        ['Sick Leave', '5 days annually', 'N/A'],
        ['Life Insurance', '1x annual salary', '100% paid'],
        ['Employee Discount', '25% off all products', 'N/A'],
        ['Digital Wallet Bonus', '5% (vs customer 3%)', 'N/A'],
    ]
    
    t = Table(benefits_data, colWidths=[2*inch, 2.2*inch, 2*inch])
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
    
    story.append(PageBreak())
    story.append(Paragraph("Work Schedule & Attendance", heading_style))
    schedule = """
    <b>Standard Store Hours:</b><br/>
    Monday - Saturday: 9:30 AM - 9:00 PM<br/>
    Sunday: 10:00 AM - 7:00 PM<br/>
    <i>(Hours may vary by location and season)</i>
    <br/><br/>
    <b>Scheduling:</b><br/>
    • Schedules posted 2 weeks in advance<br/>
    • Shift swap requests must be submitted via scheduling system, approved by manager<br/>
    • Availability changes require 2-week notice
    <br/><br/>
    <b>Attendance Expectations:</b><br/>
    • Arrive 10 minutes before scheduled shift start (prepared to work)<br/>
    • Notify manager at least 2 hours before shift if unable to work<br/>
    • 3 unexcused absences within 90 days may result in disciplinary action<br/>
    • No-call/no-show is grounds for immediate termination
    <br/><br/>
    <b>Time Off Requests:</b><br/>
    • Submit PTO requests at least 2 weeks in advance<br/>
    • Holiday blackout periods: Black Friday through New Year's Day (limited approvals)<br/>
    • Requests approved based on seniority and business needs
    """
    story.append(Paragraph(schedule, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Workplace Conduct", heading_style))
    conduct = """
    <b>Professional Appearance:</b><br/>
    • NexusIQ-branded polo shirt or dress code-compliant attire<br/>
    • Name badge visible at all times<br/>
    • Closed-toe shoes required (safety)<br/>
    • Neat, professional grooming
    <br/><br/>
    <b>Customer Interaction Standards:</b><br/>
    • Greet every customer with a smile and "Welcome to NexusIQ!"<br/>
    • Offer assistance within 2 minutes of customer entering your area<br/>
    • Never argue with customers; escalate to manager if needed<br/>
    • Thank every customer for their visit, regardless of purchase
    <br/><br/>
    <b>Prohibited Conduct:</b><br/>
    • Harassment or discrimination of any kind<br/>
    • Theft or dishonesty (zero tolerance)<br/>
    • Working under the influence of drugs or alcohol<br/>
    • Unauthorized disclosure of confidential information<br/>
    • Personal cell phone use on sales floor (emergency exceptions)<br/>
    • Negative comments about NexusIQ on social media
    <br/><br/>
    <b>Progressive Discipline:</b><br/>
    1. Verbal warning (documented)<br/>
    2. Written warning<br/>
    3. Final written warning / suspension<br/>
    4. Termination
    <br/><br/>
    <i>Serious violations may result in immediate termination without progressive steps.</i>
    """
    story.append(Paragraph(conduct, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Safety & Security", heading_style))
    safety = """
    <b>Workplace Safety:</b><br/>
    • Report all injuries immediately to your manager (even minor ones)<br/>
    • Know the location of first aid kit, fire extinguisher, and AED<br/>
    • Keep aisles and emergency exits clear at all times<br/>
    • Proper lifting technique: Bend knees, keep back straight, ask for help with heavy items
    <br/><br/>
    <b>Emergency Procedures:</b><br/>
    • <b>Fire:</b> RACE - Rescue, Alarm, Contain, Evacuate. Meet at designated assembly point.<br/>
    • <b>Medical:</b> Call 911, notify manager, render first aid if trained.<br/>
    • <b>Active Threat:</b> Run-Hide-Fight. Your safety is priority #1.
    <br/><br/>
    <b>Security Awareness:</b><br/>
    • Watch for suspicious behavior (shoplifting, fraud)<br/>
    • Never chase a shoplifter outside the store<br/>
    • Report all security concerns to Loss Prevention<br/>
    • Protect your employee discount code (abuse is theft)
    <br/><br/>
    <b>Cash Handling:</b><br/>
    • Count your drawer at shift start and end<br/>
    • Never leave register unattended with drawer open<br/>
    • Shortages over $10 require incident report<br/>
    • If robbed: Comply, stay calm, observe details, call police after threat leaves
    """
    story.append(Paragraph(safety, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Technology & Privacy", heading_style))
    technology = """
    <b>Company Systems:</b><br/>
    • POS, scheduling, and communication systems are company property<br/>
    • No expectation of privacy when using NexusIQ systems<br/>
    • Passwords must not be shared; log off when leaving workstation
    <br/><br/>
    <b>Customer Data Protection:</b><br/>
    • Never share customer information (addresses, phone numbers, purchase history)<br/>
    • Credit card numbers must never be written down or stored<br/>
    • Digital Wallet transactions are secure; never ask for PINs or passwords<br/>
    • Report any data breach suspicions immediately to IT Security
    <br/><br/>
    <b>Social Media Policy:</b><br/>
    • Personal social media must clearly state views are your own<br/>
    • No posting confidential business information<br/>
    • No disparaging NexusIQ, coworkers, or customers<br/>
    • Positive posts about NexusIQ are encouraged (tag us @NexusIQ!)
    """
    story.append(Paragraph(technology, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Growth & Development", heading_style))
    growth = """
    <b>Training Programs:</b><br/>
    • New hire orientation: 8 hours (paid)<br/>
    • Product knowledge training: Quarterly (4 hours each)<br/>
    • Digital Wallet certification: Required for all customer-facing roles<br/>
    • Leadership development: Available for high-potential employees
    <br/><br/>
    <b>Career Advancement:</b><br/>
    • We promote from within whenever possible<br/>
    • 30% of management positions filled internally (our goal)<br/>
    • Discuss career goals with your manager during quarterly check-ins<br/>
    • Internal job postings available before external recruitment
    <br/><br/>
    <b>Performance Reviews:</b><br/>
    • 90-day review (end of introductory period)<br/>
    • Annual performance review (anniversary month)<br/>
    • Quarterly check-ins (informal feedback)<br/>
    • Performance ratings tied to merit increases and promotion eligibility
    """
    story.append(Paragraph(growth, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Leaving NexusIQ", heading_style))
    leaving = """
    <b>Voluntary Resignation:</b><br/>
    • Please provide 2 weeks notice (4 weeks for management positions)<br/>
    • Written resignation preferred (email acceptable)<br/>
    • Exit interview conducted by HR
    <br/><br/>
    <b>Final Pay:</b><br/>
    • Final paycheck issued on next regular pay date (or as required by state law)<br/>
    • Accrued, unused PTO paid out per state requirements<br/>
    • Return all company property (badge, keys, uniform items)
    <br/><br/>
    <b>Rehire Eligibility:</b><br/>
    • Employees who leave in good standing are eligible for rehire<br/>
    • "Not eligible for rehire" status given for terminations for cause<br/>
    • Rehired employees may receive credit for prior service (case-by-case)
    """
    story.append(Paragraph(leaving, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Acknowledgment", heading_style))
    acknowledgment = """
    By signing below, I acknowledge that I have received, read, and understood the 
    NexusIQ Employee Handbook. I agree to abide by the policies and procedures outlined 
    herein. I understand that this handbook is not a contract of employment and that 
    my employment with NexusIQ is at-will.
    <br/><br/>
    <br/>
    Employee Signature: ______________________________ Date: ____________
    <br/><br/>
    <br/>
    Employee Name (Print): ______________________________
    <br/><br/>
    <br/>
    Manager Signature: ______________________________ Date: ____________
    """
    story.append(Paragraph(acknowledgment, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Employee Handbook 2024 | NexusIQ Corporation | Human Resources", styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# DOCUMENT 2: Compliance Training Materials
# ========================================

def generate_compliance_training():
    """Annual compliance training covering key regulatory requirements"""
    filename = f"{OUTPUT_DIR}/Compliance_Training_Materials.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles, title_style, heading_style = get_custom_styles()
    
    story.append(Paragraph("NexusIQ Compliance Training", title_style))
    story.append(Paragraph("Annual Training Module - 2024", styles['Heading2']))
    story.append(Paragraph("Required for All Employees | Completion Deadline: December 31, 2024", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Training Overview", heading_style))
    overview = """
    This training covers critical compliance topics required for all NexusIQ employees. 
    Completion is mandatory annually and tracked in your employee file.
    <br/><br/>
    <b>Training Modules:</b><br/>
    1. Anti-Harassment & Discrimination (30 minutes)<br/>
    2. Data Privacy & Security (20 minutes)<br/>
    3. Workplace Safety (15 minutes)<br/>
    4. Ethics & Integrity (15 minutes)<br/>
    5. Payment Card Industry (PCI) Compliance (20 minutes)
    <br/><br/>
    <b>Total Time:</b> Approximately 100 minutes<br/>
    <b>Assessment:</b> Quiz at end of each module (80% passing score required)
    """
    story.append(Paragraph(overview, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Module 1: Anti-Harassment & Discrimination", heading_style))
    harassment = """
    <b>What is Harassment?</b><br/>
    Harassment is unwelcome conduct based on a protected characteristic (race, sex, 
    religion, national origin, age, disability, etc.) that creates a hostile, intimidating, 
    or offensive work environment.
    <br/><br/>
    <b>Types of Harassment:</b><br/>
    • <b>Verbal:</b> Slurs, jokes, insults, comments about appearance or personal characteristics<br/>
    • <b>Physical:</b> Unwanted touching, blocking movement, assault<br/>
    • <b>Visual:</b> Displaying offensive posters, images, memes, or gestures<br/>
    • <b>Sexual:</b> Unwanted advances, requests for favors, inappropriate comments
    <br/><br/>
    <b>NexusIQ Policy:</b><br/>
    • Zero tolerance for harassment or discrimination<br/>
    • Applies to all employees, customers, vendors, and contractors<br/>
    • Violations may result in immediate termination
    <br/><br/>
    <b>Reporting Procedure:</b><br/>
    1. Report to your direct manager (unless they are the harasser)<br/>
    2. Report to Human Resources: hr@nexusiq.com or 1-800-555-NXIQ<br/>
    3. Anonymous hotline: 1-888-555-ANON (third-party managed)
    <br/><br/>
    <b>Retaliation Prohibited:</b><br/>
    NexusIQ prohibits retaliation against anyone who reports harassment in good faith 
    or participates in an investigation. Retaliation is a separate violation subject 
    to discipline.
    <br/><br/>
    <b>Bystander Intervention:</b><br/>
    If you witness harassment, you have a responsibility to act:<br/>
    • Direct: Speak up in the moment if safe to do so<br/>
    • Distract: Interrupt the situation ("Hey, can I ask you a question?")<br/>
    • Delegate: Report to a manager or HR<br/>
    • Document: Write down what you saw (dates, times, witnesses)
    """
    story.append(Paragraph(harassment, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Module 2: Data Privacy & Security", heading_style))
    data_privacy = """
    <b>Why Data Privacy Matters:</b><br/>
    NexusIQ collects sensitive customer data (payment info, addresses, purchase history). 
    Protecting this data is a legal requirement and essential to maintaining customer trust.
    <br/><br/>
    <b>Types of Protected Data:</b><br/>
    • <b>Payment Card Data:</b> Credit/debit card numbers, CVV, expiration dates<br/>
    • <b>Personal Identifiable Information (PII):</b> Names, addresses, phone numbers, email<br/>
    • <b>Transaction Data:</b> Purchase history, Digital Wallet records<br/>
    • <b>Employee Data:</b> Social Security numbers, payroll information
    <br/><br/>
    <b>Data Protection Rules:</b><br/>
    • NEVER write down credit card numbers<br/>
    • NEVER share customer data with unauthorized parties<br/>
    • NEVER leave screens displaying customer info unattended<br/>
    • ALWAYS verify identity before providing account information by phone<br/>
    • ALWAYS lock your workstation when stepping away (Ctrl+L on Windows)
    <br/><br/>
    <b>Common Data Breach Scenarios:</b><br/>
    • Phishing emails (don't click suspicious links!)<br/>
    • Tailgating (unauthorized person follows you through secure door)<br/>
    • Social engineering (caller claims to be IT, asks for password)<br/>
    • Lost devices (laptop, phone with company data)
    <br/><br/>
    <b>Reporting Data Incidents:</b><br/>
    Report ANY suspected data breach immediately to:<br/>
    • IT Security: security@nexusiq.com or ext. 5555<br/>
    • Your manager<br/>
    • Loss Prevention
    <br/><br/>
    <i>Early reporting minimizes damage. You will NOT be punished for reporting potential 
    incidents in good faith.</i>
    """
    story.append(Paragraph(data_privacy, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Module 3: Workplace Safety", heading_style))
    safety = """
    <b>Your Safety is Priority #1</b><br/>
    NexusIQ is committed to providing a safe workplace. Every employee has a responsibility 
    to identify and report hazards.
    <br/><br/>
    <b>Common Retail Hazards:</b><br/>
    • Slips, trips, and falls (wet floors, cluttered aisles, cables)<br/>
    • Lifting injuries (heavy boxes, improper technique)<br/>
    • Cuts (box cutters, broken glass)<br/>
    • Electrical hazards (frayed cords, overloaded outlets)
    <br/><br/>
    <b>Prevention Tips:</b><br/>
    • Clean up spills immediately; use "wet floor" signs<br/>
    • Keep aisles and emergency exits clear at all times<br/>
    • Lift with legs, not back; ask for help with items over 30 lbs<br/>
    • Report damaged equipment immediately; don't use it
    <br/><br/>
    <b>Injury Reporting:</b><br/>
    ALL work-related injuries must be reported to your manager immediately, even minor ones.<br/>
    • Complete incident report within 24 hours<br/>
    • Seek medical attention if needed (workers' comp covers work injuries)<br/>
    • Follow up with HR for return-to-work procedures
    <br/><br/>
    <b>Emergency Procedures Summary:</b>
    """
    story.append(Paragraph(safety, styles['Normal']))
    
    emergency_data = [
        ['Emergency', 'Action', 'Key Point'],
        ['Fire', 'RACE: Rescue, Alarm, Contain, Evacuate', 'Meet at assembly point'],
        ['Medical', 'Call 911, notify manager, render first aid', 'AED location: break room'],
        ['Active Threat', 'Run-Hide-Fight', 'Your safety first'],
        ['Robbery', 'Comply, stay calm, observe, report after', 'Never chase or confront'],
        ['Earthquake', 'Drop, Cover, Hold On', 'Stay away from windows'],
    ]
    
    t = Table(emergency_data, colWidths=[1.3*inch, 2.8*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Module 4: Ethics & Integrity", heading_style))
    ethics = """
    <b>NexusIQ Code of Ethics</b><br/>
    Our reputation is built on trust. Every employee is expected to act with honesty and 
    integrity in all business dealings.
    <br/><br/>
    <b>Key Principles:</b><br/>
    • <b>Honesty:</b> Be truthful in all communications (customers, coworkers, management)<br/>
    • <b>Fairness:</b> Treat everyone equitably; no favoritism or discrimination<br/>
    • <b>Accountability:</b> Take responsibility for your actions; admit mistakes<br/>
    • <b>Transparency:</b> No hidden agendas; share relevant information appropriately
    <br/><br/>
    <b>Conflicts of Interest:</b><br/>
    A conflict of interest exists when personal interests could improperly influence your 
    work decisions. Examples:<br/>
    • Working for a competitor (even part-time)<br/>
    • Accepting gifts from vendors (over $50 value requires disclosure)<br/>
    • Hiring/supervising relatives without disclosure<br/>
    • Using NexusIQ resources for personal business
    <br/><br/>
    <b>If in doubt, disclose!</b> Report potential conflicts to your manager or HR.
    <br/><br/>
    <b>Anti-Bribery & Corruption:</b><br/>
    NexusIQ prohibits bribes, kickbacks, or improper payments to anyone (government officials, 
    vendors, customers). This includes:<br/>
    • Cash payments<br/>
    • Lavish gifts or entertainment<br/>
    • Offering something of value in exchange for favorable treatment
    <br/><br/>
    <b>Fraud Prevention:</b><br/>
    Common fraud schemes to watch for:<br/>
    • Return fraud (returning stolen merchandise)<br/>
    • Employee discount abuse (using discount for non-family members)<br/>
    • Sweethearting (not scanning items for friends/family)<br/>
    • Vendor fraud (fictitious invoices, overbilling)
    <br/><br/>
    <b>Report suspected fraud to Loss Prevention immediately.</b>
    """
    story.append(Paragraph(ethics, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Module 5: PCI Compliance", heading_style))
    pci = """
    <b>What is PCI DSS?</b><br/>
    Payment Card Industry Data Security Standard (PCI DSS) is a set of security standards 
    designed to ensure all companies that process credit card information maintain a 
    secure environment.
    <br/><br/>
    <b>Why It Matters:</b><br/>
    • Protects customer financial data<br/>
    • Prevents data breaches that could cost millions<br/>
    • Non-compliance can result in fines up to $100,000/month<br/>
    • Loss of ability to process credit cards (business-ending)
    <br/><br/>
    <b>Your PCI Responsibilities:</b><br/>
    • <b>NEVER</b> write down full credit card numbers<br/>
    • <b>NEVER</b> ask for CVV over the phone (we don't need it for card-present transactions)<br/>
    • <b>NEVER</b> store payment data on personal devices or paper<br/>
    • <b>ALWAYS</b> verify the card matches the cardholder (check ID if suspicious)<br/>
    • <b>ALWAYS</b> protect POS terminals from tampering (report anything unusual)
    <br/><br/>
    <b>Recognizing Skimming Devices:</b><br/>
    Criminals may attach devices to card readers to steal data. Look for:<br/>
    • Loose or misaligned card readers<br/>
    • Unusual attachments or overlays on PIN pads<br/>
    • Wires or components that weren't there before
    <br/><br/>
    <b>If you suspect tampering, do NOT use the terminal. Report immediately to 
    Loss Prevention and IT.</b>
    <br/><br/>
    <b>Digital Wallet Security Advantage:</b><br/>
    Digital Wallet (Apple Pay, Google Pay) transactions are more secure than card swipes:<br/>
    • Tokenization: Actual card number never transmitted<br/>
    • Biometric authentication: Fingerprint or face required<br/>
    • Device-specific: Token only works on registered device
    <br/><br/>
    <i>This is why NexusIQ promotes Digital Wallet adoption—it protects both customers 
    and our business!</i>
    """
    story.append(Paragraph(pci, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    story.append(Paragraph("Training Completion Certification", heading_style))
    certification = """
    <b>Congratulations!</b>
    <br/><br/>
    You have completed all five modules of the NexusIQ Annual Compliance Training.
    <br/><br/>
    By signing below, I certify that I have:
    <br/>
    • Completed all training modules<br/>
    • Understood the material presented<br/>
    • Passed the assessment with a score of 80% or higher<br/>
    • Committed to applying these principles in my daily work
    <br/><br/>
    <br/>
    Employee Signature: ______________________________ Date: ____________
    <br/><br/>
    <br/>
    Employee Name (Print): ______________________________
    <br/><br/>
    <br/>
    Employee ID: ______________
    <br/><br/>
    <br/>
    Quiz Score: ______________ / 100
    <br/><br/>
    <br/>
    HR Representative: ______________________________ Date: ____________
    """
    story.append(Paragraph(certification, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("Resources & Contacts", heading_style))
    resources = """
    <b>Human Resources:</b> hr@nexusiq.com | 1-800-555-NXIQ ext. 2000
    <br/><br/>
    <b>Ethics Hotline (Anonymous):</b> 1-888-555-ANON | ethics@nexusiq.com
    <br/><br/>
    <b>IT Security:</b> security@nexusiq.com | ext. 5555
    <br/><br/>
    <b>Loss Prevention:</b> lp@nexusiq.com | ext. 4444
    <br/><br/>
    <b>Safety Officer:</b> safety@nexusiq.com | ext. 3333
    <br/><br/>
    <b>Employee Assistance Program (EAP):</b> 1-800-555-HELP (24/7, confidential)
    <br/><br/>
    <i>Remember: When in doubt, ask! Reporting concerns is always the right thing to do.</i>
    """
    story.append(Paragraph(resources, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("_" * 70, styles['Normal']))
    story.append(Paragraph("Compliance Training 2024 | NexusIQ Corporation | Required Annual Training", 
                          styles['Italic']))
    
    doc.build(story)
    print(f"✅ Generated: {filename}")


# ========================================
# MAIN EXECUTION
# ========================================

def main():
    """Generate all Tier 6 HR & Compliance PDFs"""
    print("\n" + "="*70)
    print("📄 TIER 6: HR & Compliance Documents (FINAL TIER)")
    print("="*70 + "\n")
    
    create_output_dir()
    
    print("🔄 Generating 2 HR & compliance documents...\n")
    
    generate_employee_handbook()
    generate_compliance_training()
    
    print("\n" + "="*70)
    print("✅ SUCCESS: All 2 HR & Compliance Documents Generated!")
    print("="*70)
    print(f"\n📁 Location: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  1. Employee_Handbook_2024.pdf")
    print("  2. Compliance_Training_Materials.pdf")
    
    print("\n" + "="*70)
    print("🎉 TIER 1 CORE PDFs COMPLETE! (23/23)")
    print("="*70)
    print("\n📊 Final Progress:")
    print("├── ✅ Financial Documents (5/5)")
    print("├── ✅ Market Intelligence (5/5)")
    print("├── ✅ Contracts & Legal (4/4)")
    print("├── ✅ Products & Operations (4/4)")
    print("├── ✅ Strategic Planning (3/3)")
    print("└── ✅ HR & Compliance (2/2)")
    print("\n📈 Total Progress: 23/23 PDFs (100%)")


if __name__ == "__main__":
    main()
