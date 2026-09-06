import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

basebasedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basebasedir, 'sacco.db'))
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url and db_url.startswith("postgresql://") and "psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

if db_url and "sslmode" not in db_url and "sqlite" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url = db_url + f"{separator}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'}
LEADERSHIP_ROLES = ['System Admin', 'Chairman', 'Finance', 'HR & Secretary Manager', 'ICT Director']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
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

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    publisher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    publisher = db.relationship('User', backref=db.backref('announcements', lazy=True, cascade='all, delete-orphan'))

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
    if now.weekday() != 5:
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
    for user in User.query.all():
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
            return redirect(url_for('select_role'))
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
            session['user_id'] = new_user.id
            flash('Registration successful! Please select your role.')
            return redirect(url_for('select_role'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during registration. Username or email may already be taken.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/select_role', methods=['GET', 'POST'])
@login_required
def select_role():
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    if user.role == 'System Admin':
        return redirect(url_for('admin'))
    if request.method == 'POST':
        selected_role = request.form.get('role')
        valid_roles = ['Chairman and finance', 'HR and secretary manager', 'ICT director', 'Member']
        if selected_role in valid_roles:
            user.role = selected_role
            db.session.commit()
            flash('Role updated successfully!')
            return redirect(url_for('dashboard'))
    return render_template('select_role.html')

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
            user.user_reset = False
            db.session.commit()
            flash('Password has been successfully reset! Please log in.')
            return redirect(url_for('login'))
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
    loans = get_loans_for_user(user.id)
    feedbacks = Feedback.query.filter_by(user_id=user.id, deleted_by_member=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()

    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans, feedbacks=feedbacks, members=members, min_amount=min_amount, is_late=late_status, announcements=announcements)

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
            flash('Late contribution processed: 100 KES to Weekly, {excess} KES to Collateral Damage.')
            return redirect(url_for('dashboard'))

    db.session.add(Contribution(user_id=user.id, payment_method=payment_method, account_type=account_type, amount=amount, status='Pending'))
    db.session.commit()
    flash(f'{account_type} of {amount} KES towards [{account_type}] submitted.')
    return redirect(url_for('dashboard'))

@app.route('/request_loan', methods=['POST'])
@login_required
def request_loan():
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
    feedback = Feedback.query.get_or_404(feedback_id)
    if user.role == 'System Admin':
        feedback.deleted_by_admin = True
    elif feedback.user_id == user.id:
        feedback.deleted_by_member = True
    
    if feedback.deleted_by_member and feedback.deleted_by_admin:
        db.session.delete(feedback)
    db.session.commit()
    return redirect(url_for('admin') if user.role == 'System Admin' else url_for('dashboard'))

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    user = User.query.get(session['user_id'])
    file = request.files.get('profile_pic')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user.profile_pic = filename
        db.session.commit()
        flash('Profile picture updated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/publish_announcement', methods=['POST'])
@login_required
def publish_announcement():
    user = User.query.get(session['user_id'])
    if not user or user.role == 'Member':
        flash("Unauthorized action.")
        return redirect(url_for('dashboard'))

    title = request.form.get('title')
    content = request.form.get('content')
    file = request.files.get('file')
    
    file_url = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        os.makedirs(os.path.join(current_app.root_path, 'static/uploads'), exist_ok=True)
        file.save(os.path.join(current_app.root_path, 'static/uploads', filename))
        file_url = f"uploads/{filename}"

    new_post = Announcement(title=title, content=content, file_path=file_url, publisher_id=user.id)
    db.session.add(new_post)
    db.session.commit()
    
    flash("Announcement and document published successfully to all members!")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/approve_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def approve_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Approved'
    db.session.commit()
    update_user_balances(contrib.user_id)
    return redirect(url_for('admin'))

@app.route('/reject_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def reject_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Declined'
    db.session.commit()
    update_user_balances(contrib.user_id)
    return redirect(url_for('admin'))

@app.route('/delete_contribution/<int:contrib_id>', methods=['POST'])
@login_required
def delete_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
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
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'Approved'
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/reject_loan/<int:loan_id>', methods=['POST'])
@login_required
def reject_loan(loan_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'Declined'
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_loan/<int:loan_id>', methods=['POST'])
@login_required
def delete_loan(loan_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    db.session.delete(loan)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin_reply_feedback/<int:feedback_id>', methods=['POST'])
@login_required
def admin_reply_feedback(feedback_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    feedback = Feedback.query.get_or_404(feedback_id)
    feedback.admin_reply = request.form.get('admin_reply')
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/issue_otp/<int:user_id>', methods=['POST'])
@login_required
def issue_otp(user_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    import random
    target_user = User.query.get_or_404(user_id)
    target_otp = str(random.randint(100000, 999999))
    target_user.reset_otp = target_otp
    target_user.user_reset = True
    db.session.commit()
    flash(f'OTP for {target_user.username} is: {target_otp}')
    return redirect(url_for('admin'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    target_user = User.query.get_or_404(user_id)
    db.session.delete(target_user)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin')
@login_required
def admin():
    admin_user = User.query.get(session['user_id'])
    if not admin_user or admin_user.role != 'System Admin':
        return redirect(url_for('dashboard'))
    all_contribs = Contribution.query.order_by(Contribution.date_made.desc()).all()
    all_loans = get_all_admin_loans()
    feedbacks = Feedback.query.filter_by(deleted_by_admin=False).order_by(Feedback.date_submitted.desc()).all()
    members = User.query.all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    return render_template('admin.html', all_contribs=all_contribs, all_loans=all_loans, feedbacks=feedbacks, members=members, announcements=announcements)

if __name__ == '__main__':
    app.run(debug=True)