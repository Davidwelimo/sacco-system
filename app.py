from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os, random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sacco-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sacco.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    emergency_balance = db.Column(db.Float, default=0.0)
    weekly_balance = db.Column(db.Float, default=0.0)
    monthly_balance = db.Column(db.Float, default=0.0)
    meeting_balance = db.Column(db.Float, default=0.0)
    profile_pic = db.Column(db.String(200), default='default.png')
    otp = db.Column(db.String(6), nullable=True)

    # Cascade delete prevents 500 errors when removing users linked to records
    contributions = db.relationship('Contribution', backref='user', cascade='all, delete-orphan')
    loans = db.relationship('Loan', backref='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # weekly, monthly, meeting
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    
class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')

class EmergencyTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

# Initialize DB schema and admin user
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard'))
        session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))
        if User.query.filter(User.username.ilike(username)).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        new_user = User(username=username, is_admin=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(User.username.ilike(username)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or user.is_admin:
        session.clear()
        return redirect(url_for('login'))

    members = User.query.filter_by(is_admin=False).all()
    user_contribs = Contribution.query.filter_by(user_id=user.id).all()
    return render_template('dashboard.html', user=user, members=members, contributions=user_contribs)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        session.clear()
        return redirect(url_for('login'))

    users = User.query.filter_by(is_admin=False).all()
    pending_contribs = Contribution.query.filter_by(status='Pending').all()
    loans = Loan.query.filter_by(status='Pending').all()
    transfers = EmergencyTransfer.query.filter_by(status='Pending').all()
    return render_template('admin.html', users=users, pending_contribs=pending_contribs, loans=loans, transfers=transfers)

@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'user_id' not in session: return redirect(url_for('login'))
    file = request.files.get('profile_pic')
    if file and file.filename != '':
        filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        user = User.query.get(session['user_id'])
        if user:
            user.profile_pic = filename
            db.session.commit()
            flash('Profile picture updated!')
    return redirect(url_for('user_dashboard'))

@app.route('/contribute', methods=['POST'])
def contribute():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctype = request.form.get('type')
    amount_raw = request.form.get('amount', '0')
    try:
        amount = float(amount_raw) if ctype != 'meeting' else 100.0
    except ValueError:
        flash('Invalid amount entered.')
        return redirect(url_for('user_dashboard'))

    user = User.query.get(session['user_id'])
    if not user: return redirect(url_for('login'))

    # All payments set to 'Pending' — requires admin approval before balances update
    db.session.add(Contribution(user_id=user.id, type=ctype, amount=amount, status='Pending'))
    db.session.commit()
    flash(f'{ctype.capitalize()} payment submitted to Admin for approval.')
    return redirect(url_for('user_dashboard'))

@app.route('/admin/contribution/<int:contrib_id>/<action>', methods=['POST'])
def handle_contribution(contrib_id, action):
    if not session.get('is_admin'): return redirect(url_for('login'))
    contrib = Contribution.query.get(contrib_id)
    if contrib and contrib.status == 'Pending':
        if action == 'Approve':
            contrib.status = 'Approved'
            user = User.query.get(contrib.user_id)
            if user:
                if contrib.type == 'weekly':
                    user.weekly_balance += contrib.amount
                    if contrib.amount > 50.0:
                        user.emergency_balance += (contrib.amount - 50.0)
                elif contrib.type == 'monthly':
                    user.monthly_balance += contrib.amount
                    if contrib.amount > 200.0:
                        user.emergency_balance += (contrib.amount - 200.0)
                elif contrib.type == 'meeting':
                    user.meeting_balance += contrib.amount
            flash('Contribution approved and added to member balance!')
        else:
            contrib.status = 'Declined'
            flash('Contribution declined.')
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/request_loan', methods=['POST'])
def request_loan():
    if 'user_id' not in session: return redirect(url_for('login'))
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        flash('Invalid amount.')
        return redirect(url_for('user_dashboard'))
    
    if amount > 0:
        db.session.add(Loan(user_id=session['user_id'], amount=amount))
        db.session.commit()
        flash('Loan application submitted for admin approval.')
    return redirect(url_for('user_dashboard'))

@app.route('/transfer_emergency', methods=['POST'])
def transfer_emergency():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    receiver_id_raw = request.form.get('receiver_id')
    amount_raw = request.form.get('amount')

    if not receiver_id_raw or not amount_raw:
        flash('Please select a receiver and enter an amount.')
        return redirect(url_for('user_dashboard'))

    try:
        receiver_id = int(receiver_id_raw)
        amount = float(amount_raw)
    except ValueError:
        flash('Invalid transfer details.')
        return redirect(url_for('user_dashboard'))

    user = User.query.get(session['user_id'])
    if user and amount <= user.emergency_balance and amount > 0:
        db.session.add(EmergencyTransfer(sender_id=user.id, receiver_id=receiver_id, amount=amount))
        db.session.commit()
        flash('Transfer request sent to admin for approval.')
    else:
        flash('Insufficient emergency balance or invalid request.')
    return redirect(url_for('user_dashboard'))

@app.route('/admin/generate_otp/<int:user_id>', methods=['POST'])
def generate_otp(user_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        otp = str(random.randint(100000, 999999))
        user.otp = otp
        db.session.commit()
        flash(f'Generated OTP for {user.username}: {otp}')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        # Explicitly delete related emergency transfer records before deleting the user
        EmergencyTransfer.query.filter(
            (EmergencyTransfer.sender_id == user.id) | (EmergencyTransfer.receiver_id == user.id)
        ).delete()
        
        # Delete user (contributions & loans cascade-delete automatically)
        db.session.delete(user)
        db.session.commit()
        flash('User account deleted successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/loan/<int:loan_id>/<action>', methods=['POST'])
def handle_loan(loan_id, action):
    if not session.get('is_admin'): return redirect(url_for('login'))
    loan = Loan.query.get(loan_id)
    if loan:
        loan.status = 'Approved' if action == 'Approve' else 'Declined'
        db.session.commit()
        flash(f'Loan {action.lower()}d.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/transfer/<int:transfer_id>/<action>', methods=['POST'])
def handle_transfer(transfer_id, action):
    if not session.get('is_admin'): return redirect(url_for('login'))
    t = EmergencyTransfer.query.get(transfer_id)
    if t:
        if action == 'Approve':
            sender = User.query.get(t.sender_id)
            receiver = User.query.get(t.receiver_id)
            if sender and receiver and sender.emergency_balance >= t.amount:
                sender.emergency_balance -= t.amount
                receiver.emergency_balance += t.amount
                t.status = 'Approved'
                flash('Transfer approved.')
            else:
                t.status = 'Declined'
                flash('Failed: Sender has insufficient balance.')
        else:
            t.status = 'Declined'
            flash('Transfer declined.')
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/reset_password_otp', methods=['GET', 'POST'])
def reset_password_otp():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        otp = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password', '')
        user = User.query.filter(User.username.ilike(username)).first()
        if user and user.otp and user.otp == otp:
            user.set_password(new_password)
            user.otp = None
            db.session.commit()
            flash('Password reset successfully! Log in with your new password.')
            return redirect(url_for('login'))
        flash('Invalid username or OTP.')
    return render_template('reset_otp.html')

if __name__ == '__main__':
    app.run(debug=True)