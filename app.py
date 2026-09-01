from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sacco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(200), default='default.png')
    weekly_balance = db.Column(db.Float, default=0.0)
    monthly_balance = db.Column(db.Float, default=0.0)
    meeting_balance = db.Column(db.Float, default=0.0)
    emergency_balance = db.Column(db.Float, default=0.0)
    contributions = db.relationship('Contribution', backref='user', lazy=True)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')

# Authentication Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

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

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/make_admin/<username>')
def make_admin(username):
    user = User.query.filter_by(username=username).first()
    if user:
        user.is_admin = True
        db.session.commit()
        flash(f'User {username} is now an admin!')
    else:
        flash('User not found.')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    contributions = Contribution.query.filter_by(user_id=user.id).all()
    members = User.query.all()
    return render_template('dashboard.html', user=user, contributions=contributions, members=members)

@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    user = User.query.get(session['user_id'])
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file.filename != '':
            filename = secure_filename(f"user_{user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
            db.session.commit()
            flash('Profile picture updated!')
    return redirect(url_for('dashboard'))

@app.route('/contribute', methods=['POST'])
@login_required
def contribute():
    user = User.query.get(session['user_id'])
    c_type = request.form.get('type')
    amount = request.form.get('amount')
    
    if c_type == 'meeting':
        amount = 100.0
    else:
        amount = float(amount) if amount else 0.0

    new_contrib = Contribution(user_id=user.id, type=c_type, amount=amount, status='Pending')
    db.session.add(new_contrib)
    db.session.commit()
    flash('Contribution submitted for admin approval.')
    return redirect(url_for('dashboard'))

@app.route('/request_loan', methods=['POST'])
@login_required
def request_loan():
    flash('Loan request submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/transfer_emergency', methods=['POST'])
@login_required
def transfer_emergency():
    flash('Transfer request submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return redirect(url_for('dashboard'))
    pending = Contribution.query.filter_by(status='Pending').all()
    members = User.query.all()
    return render_template('admin.html', pending=pending, members=members)

@app.route('/admin/approve/<int:contrib_id>')
@login_required
def approve_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_admin:
        return redirect(url_for('dashboard'))
        
    contrib = Contribution.query.get_or_404(contrib_id)
    if contrib.status == 'Pending':
        contrib.status = 'Approved'
        member = User.query.get(contrib.user_id)
        
        if contrib.type == 'weekly':
            limit = 50.0
            if contrib.amount > limit:
                excess = contrib.amount - limit
                member.weekly_balance += limit
                member.emergency_balance += excess
            else:
                member.weekly_balance += contrib.amount
        elif contrib.type == 'monthly':
            limit = 200.0
            if contrib.amount > limit:
                excess = contrib.amount - limit
                member.monthly_balance += limit
                member.emergency_balance += excess
            else:
                member.monthly_balance += contrib.amount
        elif contrib.type == 'meeting':
            member.meeting_balance += contrib.amount
            
        db.session.commit()
        flash('Contribution approved and balances updated successfully!')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/decline/<int:contrib_id>')
@login_required
def decline_contribution(contrib_id):
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_admin:
        return redirect(url_for('dashboard'))
        
    contrib = Contribution.query.get_or_404(contrib_id)
    if contrib.status == 'Pending':
        contrib.status = 'Declined'
        db.session.commit()
        flash('Contribution has been declined.')
        
    return redirect(url_for('admin_dashboard'))

# Automatically create database tables when app boots up (compatible with Gunicorn/Render)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)