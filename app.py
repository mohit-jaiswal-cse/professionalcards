from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, BusinessCard
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ✅ Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///business_card_db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# ✅ Make sure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ✅ Initialize db
db.init_app(app)

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "⚠️ Email already registered"

        new_user = User(name=name, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        return "❌ Invalid credentials"

    return render_template('login.html')

# @app.route('/dashboard')
# def dashboard():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     user = User.query.get(session['user_id'])
#     cards = BusinessCard.query.filter_by(user_id=user.id).all()
#     can_create = True

#     if user.role == 'new' and len(cards) >= 1:
#         can_create = False

#     return render_template('dashboard.html', user=user, cards=cards, can_create=can_create)

@app.route('/new-card', methods=['GET', 'POST'])
def new_card():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    existing_cards = BusinessCard.query.filter_by(user_id=user.id).count()

    if user.role == 'new' and existing_cards >= 1:
        return "⚠️ You can only create one card as a new user."

    if request.method == 'POST':
        name = request.form['name']
        designation = request.form['designation']
        company = request.form['company']
        mobile = request.form['mobile']
        email = request.form['email']

        logo_file = request.files['logo']
        filename = secure_filename(logo_file.filename)
        filepath = os.path.join('static/uploads', filename)
        logo_file.save(filepath)
        logo_path = f"/static/uploads/{filename}"

        card = BusinessCard(
            user_id=user.id,
            name=name,
            designation=designation,
            company=company,
            mobile=mobile,
            email=email,
            logo=logo_path,
            pdf='placeholder.pdf',
            qr='placeholder.png'
        )
        db.session.add(card)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('form.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

from reportlab.pdfgen import canvas
import qrcode

# ✅ PDF Generator
def generate_pdf(data, pdf_path):
    c = canvas.Canvas(pdf_path)
    c.setFont("Helvetica", 14)
    c.drawString(100, 800, f"Name: {data['name']}")
    c.drawString(100, 780, f"Designation: {data['designation']}")
    c.drawString(100, 760, f"Company: {data['company']}")
    c.drawString(100, 740, f"Mobile: {data['mobile']}")
    c.drawString(100, 720, f"Email: {data['email']}")
    c.save()

# ✅ QR Generator
def generate_qr(data, qr_path):
    vcard = f"""BEGIN:VCARD
VERSION:3.0
FN:{data['name']}
N:{data['name']}
ORG:{data['company']}
TITLE:{data['designation']}
TEL;TYPE=cell:{data['mobile']}
EMAIL;TYPE=internet:{data['email']}
END:VCARD"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(vcard)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    img.save(qr_path)


# ✅ Preview page after form submission
@app.route('/preview', methods=['POST'])
def preview():
    name = request.form['name']
    designation = request.form['designation']
    company = request.form['company']
    mobile = request.form['mobile']
    email = request.form['email']

    # Logo Upload
    logo_file = request.files['logo']
    filename = secure_filename(logo_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    logo_file.save(filepath)
    logo_path = f"/static/uploads/{filename}"

    # PDF Generation
    pdf_filename = f"{name.replace(' ', '_')}.pdf"
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    generate_pdf({
        'name': name, 'designation': designation,
        'company': company, 'mobile': mobile, 'email': email
    }, pdf_path)
    pdf_url = f"/static/uploads/{pdf_filename}"

    # QR Generation
    qr_filename = f"{name.replace(' ', '_')}_qr.png"
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
    generate_qr({
        'name': name, 'designation': designation,
        'company': company, 'mobile': mobile, 'email': email
    }, qr_path)
    qr_url = f"/static/uploads/{qr_filename}"

    return render_template('preview.html',
        name=name, designation=designation, company=company,
        mobile=mobile, email=email, logo=logo_path,
        pdf=pdf_url, qr=qr_url, save=True
    )


# ✅ Save the data to MySQL
@app.route('/save', methods=['POST'])
def save():
    data = request.form
    new_card = BusinessCard(
        name=data['name'],
        designation=data['designation'],
        company=data['company'],
        mobile=data['mobile'],
        email=data['email'],
        logo=data['logo'],
        pdf=data['pdf'],
        qr=data['qr'],
        user_id=session['user_id'] 
    )
    db.session.add(new_card)
    db.session.commit()
    return "<h3>✅ Data saved to MySQL! <a href='/'>New Entry</a></h3>"

@app.route('/dashboard')
def dashboard():
    user = User.query.get(session['user_id'])
    cards = BusinessCard.query.filter_by(user_id=user.id).all()
    return render_template('dashboard.html', user=user, cards=cards)

@app.route('/card/<int:card_id>')
def view_card(card_id):
    card = BusinessCard.query.get_or_404(card_id)
    return render_template('card.html',
        name=card.name,
        designation=card.designation,
        company=card.company,
        mobile=card.mobile,
        email=card.email,
        logo=card.logo,
        pdf=card.pdf,
        qr=card.qr,
        save=False  # Don't show "Save to DB" button
    )


@app.route('/admin/cards')
def admin_cards():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if user.role != 'admin':
        return "Access denied"

    all_cards = BusinessCard.query.all()
    return render_template('admin_cards.html', cards=all_cards)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
