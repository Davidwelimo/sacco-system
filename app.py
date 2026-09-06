from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
from datetime import datetime, time
from functools import wraps
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'sacco.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    phone_number = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(50), default='Member') # System Admin, Finance chair, Secretary, Member
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(200), default='default.png')
    
    mandatory_balance = db.Column(db.Float, default=0.0)
    collateral_damage_balance = db.Column(db.Float, default=0.0)
    
    user_reset = db.Column(db.Boolean, default=False)
    reset_otp = db.Column(db.String(10), nullable=True)

    contributions = db.relationship('Contribution', backref='user', cascade='all, delete-orphan', lazy=True)
    loans = db.relationship('Loan', backref='user', cascade='all, delete-orphan', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user', cascade='all, delete-orphan', lazy=True)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False) # Cash or Mpesa
    amount = db.Column(db.Float, nullable=False)
    base_paid = db.Column(db.Float, default=0.0)
    penalty_paid = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='Pending')
    date_made = db.Column(db.DateTime, default=datetime.utcnow)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123', method='scrypt')
        default_admin = User(username='admin', email='admin@sacco.com', phone_number='0700000000', role='System Admin', password=hashed_pw, is_admin=True)
        db.session.add(default_admin)
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
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
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
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, phone_number=phone_number, role=role, password=hashed_pw, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return redirect(url_for('admin_dashboard'))
    contributions = Contribution.query.filter_by(user_id=user.id).order_by(Contribution.date_made.desc()).all()
    loans = Loan.query.filter_by(user_id=user.id).all()
    return render_template('dashboard.html', user=user, contributions=contributions, loans=loans)

@app.route('/contribute', methods=['POST'])
@login_required
def contribute():
    user = User.query.get(session['user_id'])
    payment_method = request.form.get('payment_method') # Cash or Mpesa
    amount_str = request.form.get('amount')
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid amount entered.')
        return redirect(url_for('dashboard'))
    
    # Weekly deadline logic: Monday 00:00 hrs
    now = datetime.utcnow()
    is_late = False
    if now.weekday() == 0 and now.time() >= time(0, 0):
        is_late = True
    elif now.weekday() > 0:
        is_late = True

    base_due = 100.0
    penalty_due = 20.0 if is_late else 0.0
    total_required = base_due + penalty_due

    if amount < base_due:
        flash(f'Minimum mandatory contribution is {base_due} bob.')
        return redirect(url_for('dashboard'))

    applied_base = base_due
    applied_penalty = 0.0

    if is_late and amount >= total_required:
        applied_penalty = penalty_due
    elif is_late and amount < total_required:
        applied_penalty = max(0.0, amount - base_due)

    new_contrib = Contribution(
        user_id=user.id,
        payment_method=payment_method,
        amount=amount,
        base_paid=applied_base,
        penalty_paid=applied_penalty,
        status='Pending'
    )
    db.session.add(new_contrib)
    db.session.commit()
    flash('Contribution submitted for admin approval.')
    return redirect(url_for('dashboard'))

@app.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    user = User.query.get(session['user_id'])
    message = request.form.get('message')
    if message:
        fb = Feedback(user_id=user.id, message=message)
        db.session.add(fb)
        db.session.commit()
        flash('Feedback submitted directly to admin successfully!')
    return redirect(url_for('dashboard'))

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    user = User.query.get(session['user_id'])
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    file = request.files.get('profile_pic')
    
    if new_username:
        user.username = new_username
    if new_password:
        user.password = generate_password_hash(new_password, method='scrypt')
    if file:
        filename = f"user_{user.id}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user.profile_pic = filename
        
    db.session.commit()
    flash('Settings updated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_admin:
        return redirect(url_for('dashboard'))
    
    pending_contribs = Contribution.query.filter_by(status='Pending').all()
    feedbacks = Feedback.query.all()
    members = User.query.filter_by(is_admin=False).all()
    
    total_mandatory = db.session.query(func.sum(User.mandatory_balance)).scalar() or 0.0
    total_collateral = db.session.query(func.sum(User.collateral_damage_balance)).scalar() or 0.0

    return render_template('admin.html', 
                           pending=pending_contribs, 
                           feedbacks=feedbacks,
                           members=members,
                           total_mandatory=total_mandatory,
                           total_collateral=total_collateral)

@app.route('/admin/approve/contrib/<int:contrib_id>')
@login_required
def approve_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_admin:
        return redirect(url_for('dashboard'))
        
    contrib = Contribution.query.get_or_404(contrib_id)
    if contrib.status != 'Approved':
        contrib.status = 'Approved'
        member = User.query.get(contrib.user_id)
        
        member.mandatory_balance += contrib.base_paid
        if contrib.penalty_paid > 0:
            member.collateral_damage_balance += contrib.penalty_paid
            
        db.session.commit()
        flash('Contribution approved, mandatory account updated, and penalty routed to collateral damage!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/decline/contrib/<int:contrib_id>')
@login_required
def decline_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_admin:
        return redirect(url_for('dashboard'))
    contrib = Contribution.query.get_or_404(contrib_id)
    contrib.status = 'Declined'
    db.session.commit()
    flash('Contribution declined.')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)