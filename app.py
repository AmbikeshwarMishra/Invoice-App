import os
import sqlite3
import datetime
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import qrcode
from PIL import Image
import pytesseract
import pdfplumber
#import docx

# ReportLab Engine for Exact PDF Layout Matching
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_NAME = "database.db"

# Premium Color Palette: Cyan Slate Neon Theme
COLOR_BG = colors.HexColor('#0B132B')  # Deep Dark Slate
COLOR_SURFACE = colors.HexColor('#1C2541')  # Navy Surface
COLOR_PRIMARY = colors.HexColor('#3A506B')  # Muted Blue-Grey Header
COLOR_NEON_ACCENT = colors.HexColor('#00F5D4')  # Neon Mint Accent
COLOR_CYAN = colors.HexColor('#00BBF9')  # Electric Cyan Text
COLOR_TEXT = colors.HexColor('#E0E1DD')  # Soft Ice White Text
COLOR_MUTED = colors.HexColor('#90E0EF')  # Cyan Muted Text

# Flask Login Manager Initialization
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    conn.close()
    if u:
        return User(u[0], u[1], u[2])
    return None


# Database Initialization
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            date TEXT,
            supplier_name TEXT,
            client_name TEXT,
            gross_amount REAL,
            tax_amount REAL,
            total_amount REAL,
            currency TEXT,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    # Default Admin User Setup (Username: admin, Password: admin123)
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', hashed_pw))
    conn.commit()
    conn.close()


init_db()


def generate_invoice_number():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM invoices")
    count = cursor.fetchone()[0]
    conn.close()
    year = datetime.datetime.now().year
    return f"2026-27/SM/DIC/{count + 1:02d}"


def generate_upi_qr(upi_id, amount, name):
    upi_url = f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR"
    qr = qrcode.make(upi_url)
    img_io = BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io


# 1. Public Landing Page Route
@app.route('/')
def landing():
    return render_template('landing.html')


# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data and check_password_hash(user_data[2], password):
            user = User(user_data[0], user_data[1], user_data[2])
            login_user(user)
            return redirect(url_for('index'))  # Fixed: Pointed to index route
        else:
            flash("Invalid Username or Password!", "danger")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))


# Protected Invoice Generator Console Route
@app.route('/app')
@login_required
def index():
    inv_no = generate_invoice_number()
    return render_template('index.html', invoice_no=inv_no, user=current_user.username)


# Multi-Format OCR/Document Scanner (Images, PDF, DOCX)
@app.route('/scan_receipt', methods=['POST'])
@login_required
def scan_receipt():
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['receipt']
    filename = file.filename.lower()
    extracted_text = ""

    try:
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            img = Image.open(file.stream)
            extracted_text = pytesseract.image_to_string(img)
        elif filename.endswith('.pdf'):
            with pdfplumber.open(file.stream) as pdf:
                for page in pdf.pages:
                    extracted_text += (page.extract_text() or "") + "\n"
        elif filename.endswith('.docx'):
            doc = docx.Document(file.stream)
            extracted_text = "\n".join([p.text for p in doc.paragraphs])
        else:
            return jsonify({'error': 'Unsupported file format'}), 400

        return jsonify({'extracted_text': extracted_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Canvas Background Header/Footer Layout (Logo + Cyan Slate Shapes)
def draw_custom_letterhead(canvas_obj, doc):
    canvas_obj.saveState()

    # Dark Slate Background (#0B132B)
    canvas_obj.setFillColor(COLOR_BG)
    canvas_obj.rect(0, 0, letter[0], letter[1], fill=True, stroke=False)

    # Top Left Slate Curved Banner (#1C2541)
    canvas_obj.setFillColor(COLOR_SURFACE)
    path = canvas_obj.beginPath()
    path.moveTo(0, letter[1])
    path.lineTo(280, letter[1])
    path.curveTo(240, letter[1] - 70, 120, letter[1] - 120, 0, letter[1] - 110)
    path.close()
    canvas_obj.drawPath(path, fill=True, stroke=False)

    # SM SERVICES Logo Rendering
    logo_path = "static/images/logo.png"
    if os.path.exists(logo_path):
        canvas_obj.drawImage(logo_path, 30, letter[1] - 80, width=170, height=55, preserveAspectRatio=True, mask='auto')
    else:
        canvas_obj.setFont("Helvetica-Bold", 16)
        canvas_obj.setFillColor(COLOR_NEON_ACCENT)
        canvas_obj.drawString(30, letter[1] - 55, "SM SERVICES")

    # Top Right Header Info Text
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawRightString(letter[0] - 30, letter[1] - 40, "www.smservice.co.in")
    canvas_obj.drawRightString(letter[0] - 30, letter[1] - 53, "info@smservice.co.in")
    canvas_obj.drawRightString(letter[0] - 30, letter[1] - 66, "309 SaiRam Plaza, Indore, MP")

    # Bottom Geometric Accent Lines
    canvas_obj.setFillColor(COLOR_SURFACE)
    path_bot = canvas_obj.beginPath()
    path_bot.moveTo(letter[0] - 180, 0)
    path_bot.curveTo(letter[0] - 100, 50, letter[0] - 30, 90, letter[0], 110)
    path_bot.lineTo(letter[0], 0)
    path_bot.close()
    canvas_obj.drawPath(path_bot, fill=True, stroke=False)

    canvas_obj.restoreState()


# PDF Generator Matching Dark Theme & Dynamic Items
@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    data = request.form
    inv_no = data.get('invoice_no')
    date = data.get('date')
    duration = data.get('duration')
    supplier_name = data.get('supplier_name', 'SM SERVICES')
    supplier_address = data.get('supplier_address', '63 Mangal Nagar 309 Sai Ram Plaza Indore MP')
    supplier_gstin = data.get('supplier_gstin', '23BDJPM3829C1ZS')
    client_name = data.get('client_name')
    client_address = data.get('client_address')
    upi_id = data.get('upi_id', '9098273259@upi')
    currency = data.get('currency', '₹')

    products = data.getlist('product[]')
    quantities = data.getlist('qty[]')
    rates = data.getlist('rate[]')

    items = []
    gross_total = 0.0
    for i in range(len(products)):
        qty = float(quantities[i]) if quantities[i] else 1.0
        rate = float(rates[i]) if rates[i] else 0.0
        tot = qty * rate
        gross_total += tot
        items.append([
            Paragraph(f"<font color='#E0E1DD'>{i + 1}</font>", ParagraphStyle('C', alignment=1)),
            Paragraph(f"<font color='#E0E1DD'>{products[i]}</font>", ParagraphStyle('L')),
            Paragraph("<font color='#90E0EF'>Software</font>", ParagraphStyle('C', alignment=1)),
            Paragraph("<font color='#90E0EF'>-</font>", ParagraphStyle('C', alignment=1)),
            Paragraph(f"<font color='#E0E1DD'>{qty:.0f}</font>", ParagraphStyle('C', alignment=1)),
            Paragraph(f"<font color='#E0E1DD'>{rate:.1f}</font>", ParagraphStyle('R', alignment=2)),
            Paragraph(f"<font color='#E0E1DD'>{tot:.2f}</font>", ParagraphStyle('R', alignment=2))
        ])

    tax_rate = float(data.get('tax_rate', 18))
    tax_amount = (gross_total * tax_rate) / 100.0
    final_total = gross_total + tax_amount

    # Store into Database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO invoices (invoice_no, date, supplier_name, client_name, gross_amount, tax_amount, total_amount, currency, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (inv_no, date, supplier_name, client_name, gross_total, tax_amount, final_total, currency, 'Pending'))
    conn.commit()
    conn.close()

    # Build PDF Layout
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=110, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    text_white = ParagraphStyle('TW', parent=styles['Normal'], fontSize=8, leading=11, textColor=COLOR_TEXT)
    text_muted = ParagraphStyle('TM', parent=styles['Normal'], fontSize=8, leading=11, textColor=COLOR_MUTED)
    bold_cyan = ParagraphStyle('BC', parent=styles['Normal'], fontSize=8, leading=11, textColor=COLOR_CYAN,
                               fontName='Helvetica-Bold')
    bold_neon = ParagraphStyle('BN', parent=styles['Normal'], fontSize=8, leading=11, textColor=COLOR_NEON_ACCENT,
                               fontName='Helvetica-Bold')
    title_style = ParagraphStyle('TS', parent=styles['Heading2'], fontSize=12, alignment=1, spaceAfter=8,
                                 textColor=COLOR_NEON_ACCENT)

    elements.append(Paragraph("<b>TAX INVOICE</b>", title_style))

    # Supplier Info Table
    supplier_info = [
        [Paragraph("<b>Supplier's Detail</b>", bold_neon), "", "", ""],
        [Paragraph("Legal name of:", text_muted), Paragraph(supplier_name, bold_cyan),
         Paragraph("Duration:", text_muted), Paragraph(duration, text_white)],
        [Paragraph("Address:", text_muted), Paragraph(supplier_address, text_white), Paragraph("Date:", text_muted),
         Paragraph(date, text_white)],
        [Paragraph("Contact Person:", text_muted), Paragraph("Abhishek Mishra", text_white),
         Paragraph("Invoice No.:", text_muted), Paragraph(inv_no, bold_cyan)],
        [Paragraph("GSTIN:", text_muted), Paragraph(supplier_gstin, text_white), Paragraph("Contact No.:", text_muted),
         Paragraph("9098273259", text_white)]
    ]
    t_supplier = Table(supplier_info, colWidths=[90, 210, 100, 152])
    t_supplier.setStyle(TableStyle([
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('BACKGROUND', (0, 1), (-1, -1), COLOR_SURFACE),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_PRIMARY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_supplier)
    elements.append(Spacer(1, 8))

    # Receiver Info Table
    receiver_info = [
        [Paragraph("<b>Details of Receiver / Place of Supply</b>", bold_neon), ""],
        [Paragraph(f"<b>Name:</b> {client_name}<br/><b>Address:</b> {client_address}", text_white),
         Paragraph("<b>State:</b> Madhya Pradesh<br/><b>GSTIN/Unique ID:</b> N/A", text_white)]
    ]
    t_receiver = Table(receiver_info, colWidths=[300, 252])
    t_receiver.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('BACKGROUND', (0, 1), (-1, -1), COLOR_SURFACE),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_PRIMARY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(t_receiver)
    elements.append(Spacer(1, 8))

    # Items Grid
    grid_data = [[
        Paragraph("<b>S.No</b>", bold_cyan),
        Paragraph("<b>Product / Service</b>", bold_cyan),
        Paragraph("<b>Category</b>", bold_cyan),
        Paragraph("<b>DOJ</b>", bold_cyan),
        Paragraph("<b>Qty</b>", bold_cyan),
        Paragraph("<b>Rate</b>", bold_cyan),
        Paragraph("<b>Gross Amount</b>", bold_cyan)
    ]]
    grid_data.extend(items)
    grid_data.append(
        ["", "", "", "", "", Paragraph("<b>Gross:</b>", bold_cyan), Paragraph(f"<b>{gross_total:.2f}</b>", bold_cyan)])
    grid_data.append(["", "", "", "", "", Paragraph(f"<b>GST ({tax_rate:.0f}%):</b>", bold_cyan),
                      Paragraph(f"<b>{tax_amount:.2f}</b>", bold_cyan)])
    grid_data.append(["", "", "", "", "", Paragraph("<b>Total:</b>", bold_neon),
                      Paragraph(f"<b>{currency} {final_total:.2f}</b>", bold_neon)])

    t_items = Table(grid_data, colWidths=[30, 172, 60, 50, 40, 80, 120])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('BACKGROUND', (0, 1), (-1, -1), COLOR_SURFACE),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_PRIMARY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 8))

    # Payment Block with QR
    qr_io = generate_upi_qr(upi_id, final_total, supplier_name)
    qr_img = RLImage(qr_io, width=55, height=55)

    stamp_path = "static/images/stamp.png"
    if os.path.exists(stamp_path):
        sign_img = RLImage(stamp_path, width=100, height=40)
    else:
        sign_img = Paragraph(
            f"<font color='#E0E1DD'>For <b>M/s {supplier_name}</b><br/><br/>Authorized Signatory</font>", text_white)

    bank_info = [
        [Paragraph("<b>Remittance Address (RTGS/NEFT) & Payment QR</b>", bold_neon), "", ""],
        [Paragraph(
            "<b>Beneficiary Name:</b> Abhishek Mishra<br/><b>Bank Name:</b> Bank Of Maharashtra<br/><b>Account No:</b> 60376848875<br/><b>IFSC:</b> MAHB0001186",
            text_white),
            qr_img,
            sign_img]
    ]
    t_bank = Table(bank_info, colWidths=[270, 82, 200])
    t_bank.setStyle(TableStyle([
        ('SPAN', (0, 0), (2, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('BACKGROUND', (0, 1), (-1, 1), COLOR_SURFACE),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_CYAN),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 1), (1, 1), 'CENTER'),
        ('ALIGN', (2, 1), (2, 1), 'CENTER'),
    ]))
    elements.append(t_bank)

    doc.build(elements, onFirstPage=draw_custom_letterhead, onLaterPages=draw_custom_letterhead)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{inv_no.replace('/', '_')}.pdf",
                     mimetype='application/pdf')


@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices ORDER BY id DESC")
    invoices = cursor.fetchall()
    cursor.execute("SELECT SUM(total_amount) FROM invoices")
    total_rev = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE status='Pending'")
    pending_count = cursor.fetchone()[0] or 0
    conn.close()
    return render_template('dashboard.html', invoices=invoices, total_rev=total_rev, pending_count=pending_count)


if __name__ == '__main__':
    app.run(debug=True)