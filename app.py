import os
import random
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'sacco.db'))
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url and db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

if db_url and "sslmode" not in db_url and "sqlite" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url += f"{separator}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone_number = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='Member')
    profile_pic = db.Column(db.String(200), default='default.png')
    
    weekly_balance = db.Column(db.Float, default=0.0)
    savings_balance = db.Column(db.Float, default=0.0)
    loan_repayment_balance = db.Column(db.Float, default=0.0)
    collateral_balance = db.Column(db.Float, default=0.0)

    user_reset = db.Column(db.Boolean, default=False)
    reset_otp = db.Column(db.String(10), nullable=True)
    
    contributions = db.relationship('Contribution', backref='user', cascade='all, delete-orphan', lazy=True)
    loans = db.relationship('Loan', backref='user', cascade='all, delete-orphan', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user', cascade='all, delete-orphan', lazy=True)

class Contribution(db.Model):
    __tablename__ = 'contributions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    date_made = db.Column(db.DateTime, default=datetime.utcnow)

class Loan(db.Model):
    __tablename__ = 'loans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    admin_reply = db.Column(db.Text, nullable=True)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_by_member = db.Column(db.Boolean, default=False)
    deleted_by_admin = db.Column(db.Boolean, default=False)

with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin123', method='scrypt')
            default_admin = User(username='admin', email='admin@sacco.com', phone_number='0700000000', role='System Admin', password=hashed_pw)
            db.session.add(default_admin)
            db.session.commit()
    except Exception as e:
        print(f"Database initialization note: {e}")

def is_contribution_late():
    now = datetime.now()
    if now.weekday() != 6:
        return True
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
            if user.role == 'System Admin':
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
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
            new_user = User(username=username, email=email, phone_number=phone_number, password=hashed_pw, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Username or email may already be taken.')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.user_reset and user.reset_otp == otp:
            user.password = generate_password_hash(new_password, method='scrypt')
            user.reset_otp = None
            user.user_reset = False
            db.session.commit()
            flash('Password has been successfully reset! Please log in.')
            return redirect(url_for('login'))
        else:
            flash('Invalid username or OTP.')
            return redirect(url_for('reset_password_otp'))
            
    return render_template('reset_otp.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    if user.role == 'System Admin':
        return redirect(url_for('admin'))
    
    late_status = is_contribution_late()
    min_amount = 120.0 if late_status else 100.0

    contributions = Contribution.query.filter_by(user_id=user.id).order_by(Contribution.date_made.desc()).all()
    loans = Loan.query.filter_by(user_id=user.id).order_by(Loan.date_submitted.desc()).all()
    feedbacks = Feedback.query.filter_by(user_id=user.id, deleted_by_member=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.filter(User.id != user.id).all()
    
    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans, feedbacks=feedbacks, members=members, min_amount=min_amount, is_late=late_status)

@app.route('/contribute', methods=['POST'])
@login_required
def contribute():
    user = User.query.get(session['user_id'])
    payment_method = request.form.get('payment_method', 'Mpesa')
    account_type = request.form.get('account_type', 'Weekly Contribution')
    
    try:
        amount = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('Invalid contribution amount.')
        return redirect(url_for('dashboard'))

    late_status = is_contribution_late()

    if account_type == 'Weekly Contribution':
        minimum_required = 120.0 if late_status else 100.0
        if amount < minimum_required:
            if late_status:
                flash('Deadline passed. Late weekly contribution must be at least 120 KES.')
            else:
                flash('Weekly contribution must be at least 100 KES.')
            return redirect(url_for('dashboard'))

        if late_status and amount >= 120.0:
            excess = amount - 100.0
            db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type='Weekly Contribution', amount=100.0, status='Pending'))
            db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type='Collateral Damage', amount=excess, status='Pending'))
            db.session.commit()
            flash(f'Late contribution processed: 100 KES to Weekly, {excess} KES to Collateral Damage.')
            return redirect(url_for('dashboard'))

    db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type=account_type, amount=amount, status='Pending'))
    db.session.commit()
    flash(f'Payment of {amount} KES towards [{account_type}] submitted.')
    return redirect(url_for('dashboard'))

@app.route('/request_loan', methods=['POST'])
@login_required
def request_loan():
    user = User.query.get(session['user_id'])
    try:
        amount = float(request.form.get('amount'))
        if amount <= 0: raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid loan amount.')
        return redirect(url_for('dashboard'))

    db.session.add(Loan(user_id=user.id, amount=amount, status='Pending'))
    db.session.commit()
    flash('Loan request submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    user = User.query.get(session['user_id'])
    message = request.form.get('message')
    if message:
        db.session.add(Feedback(user_id=user.id, message=message))
        db.session.commit()
        flash('Feedback submitted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/delete_feedback/<int:feedback_id>', methods=['POST'])
@login_required
def delete_feedback(feedback_id):
    user = User.query.get(session['user_id'])
    fb = Feedback.query.get_or_404(feedback_id)
    if user.role == 'System Admin':
        fb.deleted_by_admin = True
    elif fb.user_id == user.id:
        fb.deleted_by_member = True
    if fb.deleted_by_member and fb.deleted_by_admin:
        db.session.delete(fb)
    db.session.commit()
    return redirect(url_for('admin') if user.role == 'System Admin' else url_for('dashboard'))

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    user = User.query.get(session['user_id'])
    file = request.files.get('profile_pic')
    if file and file.filename != '':
        filename = f"user_{user.id}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user.profile_pic = filename
        db.session.commit()
        flash('Profile picture updated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/approve_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def approve_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Approved'
    db.session.commit()
    update_user_balances(contrib.user_id)
    return redirect(url_for('admin'))

@app.route('/reject_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def reject_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Declined'
    db.session.commit()
    update_user_balances(contrib.user_id)
    return redirect(url_for('admin'))

@app.route('/delete_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def delete_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    uid = contrib.user_id
    db.session.delete(contrib)
    db.session.commit()
    update_user_balances(uid)
    return redirect(url_for('admin'))

@app.route('/approve_loan/<int:loan_id>', methods=['POST'])
@login_required
def approve_loan(loan_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    Loan.query.get_or_404(loan_id).status = 'Approved'
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/reject_loan/<int:loan_id>', methods=['POST'])
@login_required
def reject_loan(loan_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    Loan.query.get_or_404(loan_id).status = 'Declined'
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_loan/<int:loan_id>', methods=['POST'])
@login_required
def delete_loan(loan_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    db.session.delete(Loan.query.get_or_404(loan_id))
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin_reply_feedback/<int:feedback_id>', methods=['POST'])
@login_required
def admin_reply_feedback(feedback_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    Feedback.query.get_or_404(feedback_id).admin_reply = request.form.get('admin_reply')
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/issue_otp/<int:user_id>', methods=['POST'])
@login_required
def issue_otp(user_id):
    target = User.query.get_or_404(user_id)
    otp = str(random.randint(1000, 9999))
    target.reset_otp = otp
    target.user_reset = True
    db.session.commit()
    flash(f'OTP for {target.username}: {otp}')
    return redirect(url_for('admin'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    db.session.delete(User.query.get_or_404(user_id))
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin')
@login_required
def admin():
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin': return redirect(url_for('dashboard'))
    return render_template('admin.html', 
                           all_contribs=Contribution.query.order_by(Contribution.date_made.desc()).all(), 
                           all_loans=Loan.query.order_by(Loan.date_submitted.desc()).all(), 
                           feedbacks=Feedback.query.filter_by(deleted_by_admin=False).order_by(Feedback.date_submitted.desc()).all(), 
                           members=User.query.all())

if __name__ == '__main__':
    app.run(debug=True)