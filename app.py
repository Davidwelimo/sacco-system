import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import random
from models import db, User, Contribution, Loan, Feedback, Announcement

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

db_url = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(basedir, 'sacco.db')}")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url and db_url.startswith("postgresql://") and "psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

if db_url and "sslmode" not in db_url and "sqlite" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url = db_url + f"{separator}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

db.init_app(app)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'}
LEADERSHIP_ROLES = ['System Admin', 'Chairman', 'Finance', 'HR & Secretary Manager', 'ICT Director']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_contribution_late():
    now = datetime.now()
    if now.weekday() < 5:
        return False
    if now.hour > 23 or (now.hour == 23 and now.minute > 59):
        return True
    return False

def update_user_balances(user_id):
    user = User.query.get(user_id)
    if user:
        approved = Contribution.query.filter_by(user_id=user_id, status='Approved').all()
        user.weekly_balance = sum(c.amount for c in approved if c.account_type == 'Weekly Contribution')
        user.savings_balance = sum(c.amount for c in approved if c.account_type == 'Personal Savings')
        user.loan_repayment_balance = sum(c.amount for c in approved if c.account_type == 'Loan Repayment')
        user.collateral_balance = sum(c.amount for c in approved if c.account_type == 'Collateral Damage')
        db.session.commit()

def get_loans_for_user(user_id):
    user_loans = Loan.query.filter_by(user_id=user_id).order_by(Loan.date_submitted.asc()).all()
    total_repaid = sum(c.amount for c in Contribution.query.filter_by(user_id=user_id, account_type='Loan Repayment', status='Approved').all())
    rem_rep = total_repaid
    processed = []
    for loan in user_loans:
        if loan.status == 'Approved':
            paid = min(loan.amount, rem_rep)
            rem_rep -= paid
            rem_bal = loan.amount - paid
        else:
            paid = 0.0
            rem_bal = loan.amount
        processed.append({
            'id': loan.id,
            'date_submitted': loan.date_submitted,
            'amount': loan.amount,
            'paid_so_far': paid,
            'remaining_balance': rem_bal,
            'status': loan.status
        })
    return list(reversed(processed))

def get_all_admin_loans():
    loans_list = []
    users = User.query.all()
    for user in users:
        user_loans = Loan.query.filter_by(user_id=user.id).order_by(Loan.date_submitted.asc()).all()
        total_repaid = sum(c.amount for c in Contribution.query.filter_by(user_id=user.id, account_type='Loan Repayment', status='Approved').all())
        rem_rep = total_repaid
        for loan in user_loans:
            if loan.status == 'Approved':
                paid = min(loan.amount, rem_rep)
                rem_rep -= paid
                rem_bal = loan.amount - paid
            else:
                paid = 0.0
                rem_bal = loan.amount
            loans_list.append({
                'id': loan.id,
                'user': user,
                'date_submitted': loan.date_submitted,
                'amount': loan.amount,
                'paid_so_far': paid,
                'remaining_balance': rem_bal,
                'status': loan.status
            })
    loans_list.sort(key=lambda x: x['date_submitted'], reverse=True)
    return loans_list

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/select_role', methods=['GET', 'POST'])
def select_role():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        return redirect(url_for('dashboard'))
    return render_template('select_role.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('select_role'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        role = request.form.get('role', 'Member')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists.')
            return redirect(url_for('register'))

        try:
            hashed_pw = generate_password_hash(password, method='scrypt')
            user = User(username=username, email=email, phone_number=phone_number, password=hashed_pw, role=role)
            db.session.add(user)
            db.session.commit()
            session['user_id'] = user.id
            flash('Registration successful.')
            return redirect(url_for('select_role'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during registration.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        user = User.query.filter_by(username=username).first()
        if user and user.reset_otp and user.reset_otp == otp:
            user.password = generate_password_hash(new_password, method='scrypt')
            user.reset_otp = None
            user.reset_otp_requested = False
            db.session.commit()
            flash('Password successfully reset!')
            return redirect(url_for('login'))
        flash('Invalid username or OTP.')
    return render_template('reset_otp.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    late_status = is_contribution_late()
    min_amount = 120.0 if late_status else 100.0

    contributions = Contribution.query.filter_by(user_id=user.id).order_by(Contribution.date_made.desc()).all()
    loans = get_loans_for_user(user.id)
    feedbacks = Feedback.query.filter_by(user_id=user.id, deleted_by_member=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans, feedbacks=feedbacks, members=members, announcements=announcements, min_amount=min_amount, is_late_status=late_status)

@app.route('/contribute', methods=['POST'])
def contribute():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    payment_method = request.form.get('payment_method', 'Mpesa')
    account_type = request.form.get('account_type', 'Weekly Contribution')
    try:
        amount = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('Invalid contribution amount.')
        return redirect(url_for('dashboard'))

    late_status = is_contribution_late()
    limit = 120.0 if late_status else 100.0

    if account_type == 'Weekly Contribution':
        if amount < limit:
            flash(f'Weekly contribution must be at least {limit} KES.')
            return redirect(url_for('dashboard'))
        excess = amount - limit
        db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type='Weekly Contribution', amount=limit, status='Pending'))
        if excess > 0:
            db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type='Collateral Damage', amount=excess, status='Pending'))
        db.session.commit()
        flash('Contribution submitted successfully.')
    else:
        db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type=account_type, amount=amount, status='Pending'))
        db.session.commit()
        flash('Contribution submitted.')
    return redirect(url_for('dashboard'))

@app.route('/request_loan', methods=['POST'])
def request_loan():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    try:
        amount = float(request.form.get('amount'))
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid loan amount.')
        return redirect(url_for('dashboard'))

    db.session.add(Loan(user_id=user.id, amount=amount, status='Pending'))
    db.session.commit()
    flash('Loan request submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    message = request.form.get('message')
    if message:
        db.session.add(Feedback(user_id=user.id, message=message))
        db.session.commit()
        flash('Feedback submitted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/delete_feedback/<int:feedback_id>', methods=['POST'])
def delete_feedback(feedback_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    feedback = Feedback.query.get_or_404(feedback_id)
    user = User.query.get(session['user_id'])
    if feedback.user_id == user.id:
        feedback.deleted_by_member = True
    elif user.role in LEADERSHIP_ROLES:
        feedback.deleted_by_admin = True
    db.session.commit()
    return redirect(url_for('admin') if user.role in LEADERSHIP_ROLES else url_for('dashboard'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    file = request.files.get('profile_pic')
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user.profile_pic = f"uploads/{filename}"
    db.session.commit()
    flash('Profile updated!')
    return redirect(url_for('dashboard'))

@app.route('/publish_announcement', methods=['POST'])
def publish_announcement():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    title = request.form.get('title')
    content = request.form.get('content')
    file = request.files.get('file')
    file_url = None
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join('static/uploads', filename))
        file_url = f"uploads/{filename}"
    db.session.add(Announcement(title=title, content=content, file_path=file_url, publisher_id=admin_user.id))
    db.session.commit()
    flash('Announcement published!')
    return redirect(url_for('admin'))

@app.route('/approve_contrib/<int:contrib_id>', methods=['POST'])
def approve_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Approved'
    db.session.commit()
    update_user_balances(contrib.user_id)
    flash('Contribution approved.')
    return redirect(url_for('admin'))

@app.route('/reject_contrib/<int:contrib_id>', methods=['POST'])
def reject_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Declined'
    db.session.commit()
    update_user_balances(contrib.user_id)
    flash('Contribution declined.')
    return redirect(url_for('admin'))

@app.route('/delete_contrib/<int:contrib_id>', methods=['POST'])
def delete_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    uid = contrib.user_id
    db.session.delete(contrib)
    db.session.commit()
    update_user_balances(uid)
    flash('Contribution deleted.')
    return redirect(url_for('admin'))

@app.route('/approve_loan/<int:loan_id>', methods=['POST'])
def approve_loan(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'Approved'
    db.session.commit()
    flash('Loan approved.')
    return redirect(url_for('admin'))

@app.route('/reject_loan/<int:loan_id>', methods=['POST'])
def reject_loan(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'Declined'
    db.session.commit()
    flash('Loan declined.')
    return redirect(url_for('admin'))

@app.route('/delete_loan/<int:loan_id>', methods=['POST'])
def delete_loan(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    db.session.delete(loan)
    db.session.commit()
    flash('Loan deleted.')
    return redirect(url_for('admin'))

@app.route('/admin_reply_feedback/<int:feedback_id>', methods=['POST'])
def admin_reply_feedback(feedback_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    feedback = Feedback.query.get_or_404(feedback_id)
    feedback.admin_reply = request.form.get('admin_reply')
    db.session.commit()
    flash('Reply saved.')
    return redirect(url_for('admin'))

@app.route('/issue_otp/<int:user_id>', methods=['POST'])
def issue_otp(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    target_user = User.query.get_or_404(user_id)
    target_otp = str(random.randint(100000, 999999))
    target_user.reset_otp = target_otp
    target_user.reset_otp_requested = True
    db.session.commit()
    flash(f'OTP for {target_user.username}: {target_otp}')
    return redirect(url_for('admin'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    target_user = User.query.get_or_404(user_id)
    db.session.delete(target_user)
    db.session.commit()
    flash('User deleted.')
    return redirect(url_for('admin'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    
    all_contribs = Contribution.query.order_by(Contribution.date_made.desc()).all()
    all_loans = get_all_admin_loans()
    feedbacks = Feedback.query.filter_by(deleted_by_admin=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    
    return render_template('admin.html', all_contribs=all_contribs, all_loans=all_loans, feedbacks=feedbacks, members=members, announcements=announcements)

if __name__ == '__main__':
    app.run(debug=True)