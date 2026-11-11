import os
import random
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import extract, func
from models import db, User, Contribution, Loan, Feedback, Announcement, Setting

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

# FIXED: Explicitly point to the 'instance' folder so sacco.db persists across git pulls and updates
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(instance_dir, 'sacco.db'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

db.init_app(app)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt', 'gif'}

LEADERSHIP_ROLES = [
    'Chairman and Finance', 
    'HR & Secretary Manager', 
    'ICT Director'
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_min_weekly_amount():
    setting = Setting.query.filter_by(key='min_weekly_contribution').first()
    if setting:
        try:
            return float(setting.value)
        except ValueError:
            return 100.0
    return 100.0

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
        admin_pass = os.environ.get('ADMIN_PASSWORD', '123')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@sacco.com')
        hashed_pw = generate_password_hash(admin_pass, method='scrypt')
        new_admin = User(username='admin', email=admin_email, phone_number='0700000000', password=hashed_pw, role='System Admin')
        db.session.add(new_admin)
        db.session.commit()
    
    # Initialize default setting if not present
    default_setting = Setting.query.filter_by(key='min_weekly_contribution').first()
    if not default_setting:
        db.session.add(Setting(key='min_weekly_contribution', value='100.0'))
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

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect.')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.')
            return redirect(url_for('change_password'))

        user.password = generate_password_hash(new_password, method='scrypt')
        db.session.commit()
        flash('Your password has been changed successfully!')

        if user.username == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))

    return render_template('change_password.html', user=user)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('username')
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user:
            code = str(random.randint(100000, 999999))
            user.reset_otp = code
            user.reset_otp_requested = True
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
            
            try:
                sender_email = os.environ.get('MAIL_USERNAME', 'welimodavid781@gmail.com')
                sender_password = os.environ.get('MAIL_PASSWORD', 'ghdtalvrietsjobb')
                
                msg = MIMEText(f"Hello {user.username},\n\nYour password reset OTP is: {code}\nIt is valid for 15 minutes.\n\nRegards,\nSACCO Administration")
                msg['Subject'] = 'Password Reset OTP - SACCO System'
                msg['From'] = sender_email
                msg['To'] = user.email
                
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, user.email, msg.as_string())
                    
                flash(f"An OTP has been automatically sent to your email ({user.email}).")
            except Exception as e:
                flash(f"Failed to email OTP: {str(e)}. (Debug OTP: {code})")
            
            return redirect(url_for('reset_password_otp'))
        else:
            flash('No account found with that username or email.')
    return render_template('forgot_password.html')

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        user = User.query.filter_by(username=username).first()
        if user and user.reset_otp_requested and user.reset_otp == otp:
            if user.otp_expiry and datetime.utcnow() > user.otp_expiry:
                flash('OTP has expired. Please request a new one.')
                return redirect(url_for('forgot_password'))
            user.password = generate_password_hash(new_password, method='scrypt')
            user.reset_otp = None
            user.reset_otp_requested = False
            user.otp_expiry = None
            db.session.commit()
            flash('Password reset successfully. Please login.')
            return redirect(url_for('login'))
        flash('Invalid username or OTP code.')
    return render_template('reset_password_otp.html')

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
    target_user.reset_otp = code
    target_user.reset_otp_requested = True
    target_user.otp_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    
    try:
        sender_email = os.environ.get('MAIL_USERNAME', 'welimodavid781@gmail.com')
        sender_password = os.environ.get('MAIL_PASSWORD', 'ghdtalvrietsjobb')
        
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

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
        flash('Unauthorized access.')
        return redirect(url_for('dashboard'))
    
    try:
        min_weekly = float(request.form.get('min_weekly_contribution'))
        if min_weekly < 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid minimum contribution amount.')
        return redirect(url_for('admin'))
        
    setting = Setting.query.filter_by(key='min_weekly_contribution').first()
    if not setting:
        setting = Setting(key='min_weekly_contribution', value=str(min_weekly))
        db.session.add(setting)
    else:
        setting.value = str(min_weekly)
    db.session.commit()
    flash('Minimum weekly contribution updated successfully.')
    return redirect(url_for('admin'))

@app.route('/admin/monthly_report')
def monthly_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
        flash('Unauthorized access.')
        return redirect(url_for('dashboard'))
        
    selected_month = request.args.get('month', datetime.utcnow().month, type=int)
    selected_year = request.args.get('year', datetime.utcnow().year, type=int)
    
    contributions = Contribution.query.options(db.joinedload(Contribution.user)).filter(
        extract('month', Contribution.date_made) == selected_month,
        extract('year', Contribution.date_made) == selected_year,
        Contribution.status == 'Approved'
    ).order_by(Contribution.date_made.desc()).all()
    
    totals = db.session.query(
        Contribution.account_type, 
        func.sum(Contribution.amount)
    ).filter(
        extract('month', Contribution.date_made) == selected_month,
        extract('year', Contribution.date_made) == selected_year,
        Contribution.status == 'Approved'
    ).group_by(Contribution.account_type).all()
    
    totals_dict = {item[0]: item[1] for item in totals}
    grand_total = sum(totals_dict.values())
    
    return render_template('monthly_report.html', 
                           user=admin_user,
                           contributions=contributions, 
                           totals_dict=totals_dict, 
                           grand_total=grand_total,
                           selected_month=selected_month,
                           selected_year=selected_year)
@app.route('/admin/email_monthly_report/<int:year>/<int:month>', methods=['POST'])
def email_monthly_report(year, month):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
        flash('Unauthorized access.')
        return redirect(url_for('dashboard'))
        
    # Get contributions and calculate totals for the specified month/year
    contributions = Contribution.query.options(db.joinedload(Contribution.user)).filter(
        extract('month', Contribution.date_made) == month,
        extract('year', Contribution.date_made) == year,
        Contribution.status == 'Approved'
    ).all()
    
    totals = db.session.query(
        Contribution.account_type, 
        func.sum(Contribution.amount)
    ).filter(
        extract('month', Contribution.date_made) == month,
        extract('year', Contribution.date_made) == year,
        Contribution.status == 'Approved'
    ).group_by(Contribution.account_type).all()
    
    totals_dict = {item[0]: item[1] for item in totals}
    grand_total = sum(totals_dict.values())
    
    # Build email body content
    report_summary = f"""
Monthly General Report - {month}/{year}
=====================================

CATEGORY TOTALS:
- Weekly Contribution: {totals_dict.get('Weekly Contribution', 0.0):.2f} KES
- Personal Savings: {totals_dict.get('Personal Savings', 0.0):.2f} KES
- Loan Repayment: {totals_dict.get('Loan Repayment', 0.0):.2f} KES
- Collateral Damage: {totals_dict.get('Collateral Damage', 0.0):.2f} KES
-------------------------------------
GRAND TOTAL: {grand_total:.2f} KES

TRANSACTION DETAILS:
"""
    for c in contributions:
        report_summary += f"- {c.date_made.strftime('%Y-%m-%d')} | {c.user.username} | {c.account_type} | {c.amount:.2f} KES\n"
        
    report_summary += "\nRegards,\nSACCO Administration"

    # Fetch all member emails
    members = User.query.all()
    
    try:
        sender_email = os.environ.get('MAIL_USERNAME', 'welimodavid781@gmail.com')
        sender_password = os.environ.get('MAIL_PASSWORD', 'ghdtalvrietsjobb')
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            for member in members:
                if member.email:
                    msg = MIMEText(f"Hello {member.username},\n\nPlease find below the monthly general report for {month}/{year}:\n{report_summary}")
                    msg['Subject'] = f'Monthly General Report ({month}/{year}) - SACCO System'
                    msg['From'] = sender_email
                    msg['To'] = member.email
                    server.sendmail(sender_email, member.email, msg.as_string())
                    
        flash(f'Monthly report for {month}/{year} successfully emailed to all members!')
    except Exception as e:
        flash(f'Failed to send report emails: {str(e)}')
        
    return redirect(url_for('monthly_report', month=month, year=year))

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
            # Ensure a valid role is assigned, defaulting to HR MANAGER if none selected
            assigned_role = role if role in ['HR MANAGER', 'ICT DIRECTOR', 'FINANCE CHAIRMAN'] else 'HR MANAGER'
            
            user = User(username=username, email=email, phone_number=phone_number, password=hashed_pw, role=assigned_role)
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

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    if user.username == 'admin':
        return redirect(url_for('admin'))

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            announcement = Announcement(content=content, publisher_id=user.id)
            db.session.add(announcement)
            db.session.commit()
            flash('Announcement broadcasted successfully.')
        return redirect(url_for('dashboard'))

    late_status = is_contribution_late()
    min_amount = get_min_weekly_amount()

    contributions = Contribution.query.filter_by(user_id=user.id).order_by(Contribution.date_made.desc()).all()
    loans = get_loans_for_user(user.id)
    feedbacks = Feedback.query.filter_by(user_id=user.id, deleted_by_member=False).order_by(Feedback.date_submitted.desc()).all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    
    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans, feedbacks=feedbacks, announcements=announcements, min_amount=min_amount, is_late_status=late_status)

@app.route('/update_profile_pic', methods=['POST'])
def update_profile_pic():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    file = request.files.get('profile_pic')
    if file and file.filename != '' and allowed_file(file.filename):
        upload_dir = os.path.join(app.root_path, 'static/uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = secure_filename(f"user_{user.id}_{file.filename}")
        file.save(os.path.join(upload_dir, filename))
        
        user.profile_pic = f"uploads/{filename}"
        db.session.commit()
        flash('Profile picture successfully updated!')
    else:
        flash('Please select a valid image file.')
        
    if user.username == 'admin':
        return redirect(url_for('admin'))
    return redirect(url_for('dashboard'))

@app.route('/top_up_wallet', methods=['POST'])
def top_up_wallet():
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
        flash('Invalid top-up amount.')
        return redirect(url_for('dashboard'))
    
    contrib = Contribution(
        user_id=user.id,
        payment_method='Mpesa',
        account_type='Wallet Top-up',
        amount=amount,
        status='Pending'
    )
    db.session.add(contrib)
    db.session.commit()
    flash(f'Wallet top-up request of {amount} KES submitted successfully. Waiting for admin approval.')
    return redirect(url_for('dashboard'))

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

    limit = get_min_weekly_amount()

    if account_type == 'Weekly Contribution' and amount < limit:
        flash(f'Weekly contribution must be at least {limit} KES.')
        return redirect(url_for('dashboard'))

    if payment_method == 'Wallet':
        if user.wallet_balance < amount:
            flash('Insufficient funds in your Wallet. Please top up first.')
            return redirect(url_for('dashboard'))
        
        user.wallet_balance -= amount

    contrib = Contribution(
        user_id=user.id, 
        payment_method=payment_method, 
        account_type=account_type, 
        amount=amount, 
        status='Pending'
    )
    db.session.add(contrib)
    db.session.commit()

    flash('Contribution submitted successfully and is pending admin approval.')
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
        reason = request.form.get('reason', '')
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid loan amount.')
        return redirect(url_for('dashboard'))

    # 1. Save loan request to database (without 'reason')
    new_loan = Loan(user_id=user.id, amount=amount, status='Pending')
    db.session.add(new_loan)
    db.session.commit()
    
    # 2. Email Chairman & Finance Officer
    try:
        sender_email = os.environ.get('MAIL_USERNAME', 'welimodavid781@gmail.com')
        sender_password = os.environ.get('MAIL_PASSWORD', 'ghdtalvrietsjobb')
        recipients = ['chairman@sacco.com', 'finance@sacco.com']
        
        msg = MIMEText(f"Hello,\n\nA new loan request of {amount:.2f} KES has been submitted by {user.username}.\nReason: {reason}\n\nPlease check the admin dashboard to review.")
        msg['Subject'] = f'New Loan Request - {user.username}'
        msg['From'] = sender_email
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            for recipient in recipients:
                msg['To'] = recipient
                server.sendmail(sender_email, recipient, msg.as_string())
    except Exception as e:
        print(f"Email failed: {e}")

    # 3. Send SMS notification to applicant via Onfon Mobile
    try:
        sms_url = "https://api.onfonmedia.co.ke/v1/sms/SendSMS"
        sms_payload = {
            "User_Name": os.environ.get('ONFON_USERNAME', ''),
            "PassWord": os.environ.get('ONFON_PASSWORD', ''),
            "SenderID": os.environ.get('ONFON_SENDER_ID', 'SACCO'),
            "PhoneNumber": getattr(user, 'phone_number', ''),
            "Text": f"Hello {user.username}, your loan request of {amount:.2f} KES has been received and is pending review."
        }
        if sms_payload["PhoneNumber"]:
            requests.post(sms_url, json=sms_payload, timeout=5)
    except Exception as e:
        print(f"SMS failed: {e}")

    flash('Loan request submitted successfully and notifications sent.')
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
    if not publisher_user:
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    content = request.form.get('content')
    file = request.files.get('file')
    file_url = None
    if file and file.filename != '' and allowed_file(file.filename):
        upload_dir = os.path.join(app.root_path, 'static/uploads')
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(file.filename)
        file.save(os.path.join(upload_dir, filename))
        file_url = f"uploads/{filename}"
    db.session.add(Announcement(title=title, content=content, file_path=file_url, publisher_id=publisher_user.id))
    db.session.commit()
    flash('Announcement broadcasted successfully across all accounts!')
    
    if publisher_user.username == 'admin':
        return redirect(url_for('admin'))
    return redirect(url_for('dashboard'))

@app.route('/approve_contrib/<int:contrib_id>', methods=['POST'])
def approve_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
        return redirect(url_for('dashboard'))
    
    contrib = Contribution.query.get_or_404(contrib_id)
    
    if contrib.status == 'Approved':
        flash('Contribution is already approved.')
        return redirect(url_for('admin'))

    if contrib.account_type == 'Wallet Top-up':
        contrib.status = 'Approved'
        user = User.query.get(contrib.user_id)
        if user:
            user.wallet_balance += contrib.amount
        db.session.commit()
        flash('Wallet top-up approved successfully and credited to user wallet.')
        return redirect(url_for('admin'))

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
                if contrib.payment_method == 'Wallet':
                    user = User.query.get(user_id)
                    if user:
                        user.wallet_balance += contrib.amount
                
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
    if not admin_user or admin_user.username != 'admin':
        return redirect(url_for('dashboard'))
    
    contrib = Contribution.query.get_or_404(contrib_id)
    if contrib.status != 'Declined':
        contrib.status = 'Declined'
        if contrib.payment_method == 'Wallet':
            user = User.query.get(contrib.user_id)
            if user:
                user.wallet_balance += contrib.amount
        db.session.commit()
        update_user_balances(contrib.user_id)
        
    flash('Contribution declined.')
    return redirect(url_for('admin'))

@app.route('/delete_contrib/<int:contrib_id>', methods=['POST'])
def delete_contrib(contrib_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
        return redirect(url_for('dashboard'))
    
    contrib = Contribution.query.get_or_404(contrib_id)
    uid = contrib.user_id
    was_approved = contrib.status == 'Approved'
    
    if was_approved and contrib.account_type == 'Wallet Top-up':
        user = User.query.get(uid)
        if user:
            user.wallet_balance -= contrib.amount

    db.session.delete(contrib)
    db.session.commit()
    if was_approved:
        update_user_balances(uid)
    flash('Contribution deleted.')
    return redirect(url_for('admin'))

@app.route('/approve_loan/<int:loan_id>', methods=['POST'])
def approve_loan(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.username != 'admin':
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
    if not admin_user or admin_user.username != 'admin':
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
    if not admin_user or admin_user.username != 'admin':
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
    if not admin_user or admin_user.username != 'admin':
        return redirect(url_for('dashboard'))
    
    new_role = request.form.get('role')
    target_user = User.query.get_or_404(user_id)
    
    if target_user.username == 'admin':
        flash('Cannot modify the primary admin account role.', 'danger')
        return redirect(url_for('admin'))
        
    valid_roles = ['HR MANAGER', 'ICT DIRECTOR', 'FINANCE CHAIRMAN', 'System Admin', 'Member']
    if new_role in valid_roles:
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

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session['user_id'])
    
    if not admin_user or admin_user.username != 'admin':
        flash('Unauthorized access. Please log in with the admin account.')
        return redirect(url_for('dashboard'))
    
    all_contribs = Contribution.query.options(db.joinedload(Contribution.user)).order_by(Contribution.date_made.desc()).all()
    all_loans = get_all_admin_loans()
    feedbacks = Feedback.query.filter_by(deleted_by_admin=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    
    approved_contribs = [c for c in all_contribs if c.status == 'Approved']
    
    total_weekly = sum(c.amount for c in approved_contribs if c.account_type == 'Weekly Contribution')
    total_savings = sum(c.amount for c in approved_contribs if c.account_type == 'Personal Savings')
    total_collateral = sum(c.amount for c in approved_contribs if c.account_type == 'Collateral Damage')
    total_repayment = sum(c.amount for c in approved_contribs if c.account_type == 'Loan Repayment')
    
    wallet_transfers = [c for c in all_contribs if c.account_type == 'Wallet Top-up']
    total_wallet_topups = sum(c.amount for c in approved_contribs if c.account_type == 'Wallet Top-up')
    
    grand_total = total_weekly + total_savings + total_collateral + total_repayment

    current_min_weekly = get_min_weekly_amount()

    member_summaries = []
    for m in members:
        m_contribs = [c for c in approved_contribs if c.user_id == m.id]
        w_bal = sum(c.amount for c in m_contribs if c.account_type == 'Weekly Contribution')
        s_bal = sum(c.amount for c in m_contribs if c.account_type == 'Personal Savings')
        c_bal = sum(c.amount for c in m_contribs if c.account_type == 'Collateral Damage')
        r_bal = sum(c.amount for c in m_contribs if c.account_type == 'Loan Repayment')
        tot_bal = w_bal + s_bal + c_bal + r_bal

        member_summaries.append({
            'user': m,
            'username': m.username,
            'email': m.email,
            'weekly_balance': w_bal,
            'weekly_total': w_bal,
            'savings_balance': s_bal,
            'savings_total': s_bal,
            'collateral_balance': c_bal,
            'collateral_total': c_bal,
            'loan_repayment_balance': r_bal,
            'loan_repayment_total': r_bal,
            'total_balance': tot_bal,
            'grand_total': tot_bal,
            'account_status': 'Active'
        })
    
    return render_template(
        'admin.html', 
        user=admin_user, 
        admin_user=admin_user, 
        all_contribs=all_contribs, 
        all_loans=all_loans, 
        feedbacks=feedbacks, 
        members=members, 
        announcements=announcements,
        total_weekly=total_weekly,
        total_savings=total_savings,
        total_collateral=total_collateral,
        total_repayment=total_repayment,
        wallet_transfers=wallet_transfers,
        total_wallet_topups=total_wallet_topups,
        grand_total=grand_total,
        current_min_weekly=current_min_weekly,
        member_summaries=member_summaries
    )

if __name__ == '__main__':
    app.run(debug=True)