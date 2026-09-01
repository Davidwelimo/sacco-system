import os
import random
import string
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Contribution, Loan, EmergencyTransfer

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sacco-secret-key-123')

# Handle database URI compatibility for Render PostgreSQL
db_url = os.environ.get('DATABASE_URL', 'sqlite:///sacco.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Database and Default Admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

# --- AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.is_admin else 'dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        
        user = User.query.filter_by(username=username, otp=otp).first()
        if user and otp:
            user.password_hash = generate_password_hash(new_password)
            user.otp = None  # Clear OTP after use
            db.session.commit()
            flash('Password reset successful. Please log in.')
            return redirect(url_for('login'))
        flash('Invalid username or OTP.')
    return render_template('reset_otp.html')

# --- MEMBER ROUTES ---

@app.route('/dashboard')
@login_required
def dashboard():
    members = User.query.filter_by(is_admin=False).all()
    return render_template('dashboard.html', user=current_user, members=members)

@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file selected.')
        return redirect(url_for('dashboard'))
    file = request.files['profile_pic']
    if file and allowed_file(file.filename):
        filename = secure_filename(f"user_{current_user.id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        current_user.profile_pic = filename
        db.session.commit()
        flash('Profile picture updated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/contribute', methods=['POST'])
@login_required
def contribute():
    c_type = request.form.get('type')  # 'weekly' or 'monthly'
    amount = float(request.form.get('amount', 0))
    required = 50.0 if c_type == 'weekly' else 200.0
    
    overpayment = 0.0
    if amount > required:
        overpayment = amount - required
        current_user.emergency_balance += overpayment
        
    contrib = Contribution(
        user_id=current_user.id,
        type=c_type,
        amount=amount,
        overpayment=overpayment
    )
    db.session.add(contrib)
    db.session.commit()
    flash(f'Contribution recorded! {overpayment} KES pushed to emergency fund.' if overpayment > 0 else 'Contribution recorded!')
    return redirect(url_for('dashboard'))

@app.route('/request_loan', methods=['POST'])
@login_required
def request_loan():
    amount = float(request.form.get('amount', 0))
    if amount > 0:
        loan = Loan(user_id=current_user.id, amount=amount)
        db.session.add(loan)
        db.session.commit()
        flash('Loan application submitted for admin approval.')
    return redirect(url_for('dashboard'))

@app.route('/transfer_emergency', methods=['POST'])
@login_required
def transfer_emergency():
    receiver_id = int(request.form.get('receiver_id'))
    amount = float(request.form.get('amount', 0))
    
    if current_user.emergency_balance >= amount and amount > 0:
        transfer = EmergencyTransfer(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            amount=amount
        )
        db.session.add(transfer)
        db.session.commit()
        flash('Emergency transfer submitted. Awaiting admin approval.')
    else:
        flash('Insufficient emergency balance.')
    return redirect(url_for('dashboard'))

# --- ADMIN ROUTES ---

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    pending_loans = Loan.query.filter_by(status='Pending').all()
    pending_transfers = EmergencyTransfer.query.filter_by(status='Pending').all()
    return render_template('admin.html', users=users, loans=pending_loans, transfers=pending_transfers)

@app.route('/admin/generate_otp/<int:user_id>', methods=['POST'])
@login_required
def generate_otp(user_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    otp = ''.join(random.choices(string.digits, k=6))
    user.otp = otp
    db.session.commit()
    flash(f'Generated OTP for {user.username}: {otp}')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Member removed successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/loan/<int:loan_id>/<action>', methods=['POST'])
@login_required
def handle_loan(loan_id, action):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    loan = Loan.query.get_or_404(loan_id)
    if action in ['Approve', 'Decline']:
        loan.status = action
        db.session.commit()
        flash(f'Loan {action.lower()}d.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/transfer/<int:transfer_id>/<action>', methods=['POST'])
@login_required
def handle_transfer(transfer_id, action):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    transfer = EmergencyTransfer.query.get_or_404(transfer_id)
    if action == 'Approve':
        sender = User.query.get(transfer.sender_id)
        if sender.emergency_balance >= transfer.amount:
            sender.emergency_balance -= transfer.amount
            transfer.status = 'Approved'
            db.session.commit()
            flash('Transfer approved and balance adjusted.')
        else:
            flash('Sender has insufficient balance.')
    elif action == 'Decline':
        transfer.status = 'Declined'
        db.session.commit()
        flash('Transfer declined.')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)