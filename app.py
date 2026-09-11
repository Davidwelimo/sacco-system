import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, User, Contribution, Loan, Feedback, Announcement

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sacco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

db.init_app(app)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'}
LEADERSHIP_ROLES = ['System Admin', 'ICT manager', 'Chairman and Finance', 'HR /Secretary manager']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_contribution_late():
    now = datetime.now()
    if now.weekday() == 6: # Sunday
        if now.hour > 23 or (now.hour == 23 and now.minute > 59):
            return True
        return False
    return True # Monday to Saturday

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
    existing_admin = User.query.filter_by(username='admin').first()
    if not existing_admin:
        hashed_pw = generate_password_hash('123', method='scrypt')
        new_admin = User(username='admin', email='admin@sacco.com', phone_number='0700000000', password=hashed_pw, role='System Admin')
        db.session.add(new_admin)
        db.session.commit()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
            
        flash('Invalid username or password.')
 
    return render_template('login.html')

import random
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

@app.route('/admin/generate_otp/<int:user_id>', methods=['POST'])
def admin_generate_otp(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = User.query.get(session['user_id'])
    
    if not current_user or current_user.username != 'admin':
        flash('Only Admin can generate password reset OTPs.')
        return redirect(url_for('admin'))
        
    target_user = User.query.get_or_404(user_id)
    
    code = str(random.randint(100000, 999999))
    target_user.otp = code
    target_user.otp_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    
    try:
        sender_email = "welimodavid781@gmail.com"
        sender_password = "ghdtalvrietsjobb"
        
        msg = MIMEText(f"Hello {target_user.username},\n\nYour password reset OTP is: {code}\nIt is valid for 15 minutes.\n\nRegards,\nSACCO Administration")
        msg['Subject'] = 'Password Reset OTP - SACCO System'
        msg['From'] = sender_email
        msg['To'] = target_user.email
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, target_user.email, msg.as_string())
            
        flash(f"OTP successfully generated and emailed to {target_user.email}.")
    except Exception as e:
        flash(f"OTP generated for {target_user.username}: {code} (Email dispatch failed: {str(e)})")
        
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = User.query.get(session['user_id'])
    
    if not current_user or current_user.username != 'admin':
        flash('Only Admin can remove users from the system.')
        return redirect(url_for('admin'))
    
    target_user = User.query.get_or_404(user_id)
    
    if target_user.id == current_user.id:
        flash('You cannot remove your own active account.')
        return redirect(url_for('admin'))

    Contribution.query.filter_by(user_id=target_user.id).delete()
    Loan.query.filter_by(user_id=target_user.id).delete()
    Feedback.query.filter_by(user_id=target_user.id).delete()
    
    db.session.delete(target_user)
    db.session.commit()
    flash(f"User {target_user.username} has been removed from the system.")
    return redirect(url_for('admin'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        role = request.form.get('role')

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
            return redirect(url_for('dashboard'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during registration.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        user = User.query.filter_by(username=username).first()
        if user and user.reset_otp_requested and user.reset_otp == otp:
            user.password = generate_password_hash(new_password, method='scrypt')
            user.reset_otp = None
            user.reset_otp_requested = False
            db.session.commit()
            flash('Password reset successfully. Please login.')
            return redirect(url_for('login'))
        flash('Invalid username or OTP code.')
    return render_template('reset_password_otp.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    # ONLY send the primary admin account automatically to the admin panel
    if user.username == 'admin':
        return redirect(url_for('admin'))

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            if user.role in ['Admin', 'HR MANAGER', 'FINANCE CHAIRMAN', 'ICT DIRECTOR'] or user.username == 'admin':
                announcement = Announcement(content=content, user_id=user.id)
                db.session.add(announcement)
                db.session.commit()
                flash('Announcement broadcasted successfully.')
            else:
                flash('You do not have permission to post announcements.')
        return redirect(url_for('dashboard'))

    late_status = is_contribution_late()
    min_amount = 100.0 if late_status else 100.0

    contributions = Contribution.query.filter_by(user_id=user.id).order_by(Contribution.date_made.desc()).all()
    loans = get_loans_for_user(user.id)
    feedbacks = Feedback.query.filter_by(user_id=user.id, deleted_by_member=False).order_by(Feedback.date_submitted.desc()).all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    
    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans, feedbacks=feedbacks, announcements=announcements, min_amount=min_amount, is_late_status=late_status)

@app.route('/contribute', methods=['POST'])
def contribute():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user.username == 'admin':
        return redirect(url_for('admin'))
        
    payment_method = request.form.get('payment_method', 'Mpesa')
    account_type = request.form.get('account_type', 'Weekly Contribution')
    try:
        amount = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('Invalid contribution amount.')
        return redirect(url_for('dashboard'))

    late_status = is_contribution_late()
    limit = 100.0 if late_status else 100.0

    if account_type == 'Weekly Contribution':
        if amount < limit:
            flash(f'Weekly contribution must be at least {limit} KES.')
            return redirect(url_for('dashboard'))
        db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type='Weekly Contribution', amount=amount, status='Pending'))
        db.session.commit()
        flash('Weekly contribution submitted successfully.')
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
    if user.username == 'admin':
        return redirect(url_for('admin'))
        
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
    if user.username == 'admin':
        return redirect(url_for('admin'))
        
    message = request.form.get('message')
    if message:
        db.session.add(Feedback(user_id=user.id, message=message))
        db.session.commit()
        flash('Feedback submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/publish_announcement', methods=['POST'])
def publish_announcement():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    publisher_user = User.query.get(session['user_id'])
    if not publisher_user or publisher_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    content = request.form.get('content')
    file = request.files.get('file')
    file_url = None
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join('static/uploads', filename))
        file_url = f"uploads/{filename}"
    db.session.add(Announcement(title=title, content=content, file_path=file_url, publisher_id=publisher_user.id))
    db.session.commit()
    flash('Announcement broadcasted successfully across all accounts!')
    return redirect(url_for('admin'))

@app.route('/approve_contrib/<int:contrib_id>', methods=['POST'])
def approve_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    
    contrib = Contribution.query.get_or_404(contrib_id)
    
    if contrib.account_type == 'Loan Repayment':
        user_id = contrib.user_id
        approved_loans = Loan.query.filter_by(user_id=user_id, status='Approved').all()
        total_loans = sum(l.amount for l in approved_loans)
        
        other_repayments = Contribution.query.filter_by(user_id=user_id, account_type='Loan Repayment', status='Approved').filter(Contribution.id != contrib.id).all()
        total_repaid = sum(c.amount for c in other_repayments)
        
        remaining_balance = total_loans - total_repaid
        
        if contrib.amount > remaining_balance and remaining_balance >= 0:
            valid_repay = remaining_balance
            excess = contrib.amount - valid_repay
            
            if valid_repay > 0:
                contrib.amount = valid_repay
                contrib.status = 'Approved'
            else:
                contrib.status = 'Declined'
                
            if excess > 0:
                savings_amt = excess * 0.60
                collateral_amt = excess * 0.40
                if savings_amt > 0:
                    db.session.add(Contribution(user_id=user_id, payment_method=contrib.payment_method, account_type='Personal Savings', amount=savings_amt, status='Approved'))
                if collateral_amt > 0:
                    db.session.add(Contribution(user_id=user_id, payment_method=contrib.payment_method, account_type='Collateral Damage', amount=collateral_amt, status='Approved'))
        else:
            contrib.status = 'Approved'
    else:
        contrib.status = 'Approved'
        
    db.session.commit()
    update_user_balances(contrib.user_id)
    flash('Contribution approved successfully.')
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
    flash('Loan request deleted successfully.')
    return redirect(url_for('admin'))

@app.route('/update_role/<int:user_id>', methods=['POST'])
def update_role(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role not in LEADERSHIP_ROLES:
        return redirect(url_for('dashboard'))
    
    new_role = request.form.get('role')
    target_user = User.query.get_or_404(user_id)
    
    if target_user.username == 'admin':
        flash('Cannot modify the primary admin account role.', 'danger')
        return redirect(url_for('admin'))
        
    if new_role in LEADERSHIP_ROLES or new_role == 'Member':
        target_user.role = new_role
        db.session.commit()
        flash(f"Role updated successfully for {target_user.username}.")
    else:
        flash("Invalid role selected.")
        
    return redirect(url_for('admin'))

@app.route('/switch_role', methods=['POST'])
def switch_role():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
        
    selected_role = request.form.get('role')
    if selected_role in LEADERSHIP_ROLES:
        user.role = selected_role
        db.session.commit()
        flash(f"Successfully switched view to {selected_role}.")
        return redirect(url_for('admin'))
        
    flash("Invalid role selected.")
    return redirect(url_for('dashboard'))

@app.route('/admin/set_user_otp/<int:user_id>', methods=['POST'])
def admin_set_user_otp(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        flash('Only System Admin can perform this action.')
        return redirect(url_for('admin'))
    
    new_otp = request.form.get('otp')
    target_user = User.query.get_or_404(user_id)
    if new_otp:
        target_user.reset_otp = new_otp
        target_user.reset_otp_requested = True
        db.session.commit()
        flash(f'Password reset OTP set successfully for {target_user.username}.')
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
    
    return render_template('admin.html', admin_user=admin_user, all_contribs=all_contribs, all_loans=all_loans, feedbacks=feedbacks, members=members, announcements=announcements)

if __name__ == '__main__':
    app.run(debug=True)