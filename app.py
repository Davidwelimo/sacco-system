import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_sacco_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sacco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Fixed contribution caps
CAPS = {
    'weekly': 50.0,
    'monthly': 200.0,
    'meeting': 100.0
}

# ----------------- MODELS -----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Balances
    weekly_balance = db.Column(db.Float, default=0.0)
    monthly_balance = db.Column(db.Float, default=0.0)
    meeting_balance = db.Column(db.Float, default=0.0)
    emergency_balance = db.Column(db.Float, default=0.0)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # weekly, monthly, meeting, emergency
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Declined
    
    user = db.relationship('User', backref=db.backref('contributions', lazy=True))

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    
    user = db.relationship('User', backref=db.backref('loans', lazy=True))

class EmergencyTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    purpose = db.Column(db.String(50), nullable=False) # weekly, monthly, meeting
    status = db.Column(db.String(20), default='Pending')
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class EmergencySelfPay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_type = db.Column(db.String(50), nullable=False) # weekly, monthly, meeting
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    
    user = db.relationship('User', backref=db.backref('self_pays', lazy=True))

# ----------------- ROUTES -----------------

@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('home'))
        
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Choose another.')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def member_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    transfers = EmergencyTransfer.query.filter_by(status='Pending').all()
    self_pays = EmergencySelfPay.query.filter_by(status='Pending').all()
    pending_contribs = Contribution.query.filter_by(status='Pending').all()
    loans = Loan.query.filter_by(status='Pending').all()
    users = User.query.all()
    
    return render_template(
        'admin.html',
        transfers=transfers,
        self_pays=self_pays,
        pending_contribs=pending_contribs,
        loans=loans,
        users=users
    )

# ----------------- CONTRIB APPROVAL LOGIC (WITH CAPPING & EXCESS DIVERT) -----------------

@app.route('/admin/contribution/<int:contrib_id>/<string:action>', methods=['POST'])
def handle_contribution(contrib_id, action):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    contribution = Contribution.query.get_or_404(contrib_id)
    user = User.query.get(contribution.user_id)

    if action == 'Approve':
        contrib_type = contribution.type.lower()
        total_amount = float(contribution.amount)

        if contrib_type in CAPS:
            cap = CAPS[contrib_type]

            if total_amount > cap:
                intended_amount = cap
                excess_amount = total_amount - cap
            else:
                intended_amount = total_amount
                excess_amount = 0.0

            # Update intended target balance
            if contrib_type == 'weekly':
                user.weekly_balance += intended_amount
            elif contrib_type == 'monthly':
                user.monthly_balance += intended_amount
            elif contrib_type == 'meeting':
                user.meeting_balance += intended_amount

            # Auto-divert excess to Emergency account
            if excess_amount > 0:
                user.emergency_balance += excess_amount
                flash(f"Approved {contrib_type.capitalize()}: KES {intended_amount:.2f} assigned. KES {excess_amount:.2f} excess moved to Emergency Account.")
            else:
                flash(f"Approved KES {intended_amount:.2f} for {contrib_type.capitalize()}.")

        elif contrib_type == 'emergency':
            user.emergency_balance += total_amount
            flash(f"Approved KES {total_amount:.2f} directly to Emergency Account.")

        contribution.status = 'Approved'
        db.session.commit()

    elif action == 'Decline':
        contribution.status = 'Declined'
        db.session.commit()
        flash("Contribution request declined.")

    return redirect(url_for('admin_dashboard'))

# ----------------- OTHER ADMIN ACTIONS -----------------

@app.route('/admin/transfer/<int:transfer_id>/<string:action>', methods=['POST'])
def handle_transfer(transfer_id, action):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    transfer = EmergencyTransfer.query.get_or_404(transfer_id)
    if action == 'Approve':
        sender = User.query.get(transfer.sender_id)
        receiver = User.query.get(transfer.receiver_id)
        
        if sender.emergency_balance >= transfer.amount:
            sender.emergency_balance -= transfer.amount
            if transfer.purpose == 'weekly':
                receiver.weekly_balance += transfer.amount
            elif transfer.purpose == 'monthly':
                receiver.monthly_balance += transfer.amount
            elif transfer.purpose == 'meeting':
                receiver.meeting_balance += transfer.amount
                
            transfer.status = 'Approved'
            flash("Emergency transfer approved.")
        else:
            flash("Sender has insufficient emergency funds.")
    else:
        transfer.status = 'Rejected'
        flash("Emergency transfer rejected.")
        
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/self_pay/<int:req_id>/<string:action>', methods=['POST'])
def handle_self_pay(req_id, action):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    req = EmergencySelfPay.query.get_or_404(req_id)
    if action == 'Approve':
        user = User.query.get(req.user_id)
        if user.emergency_balance >= req.amount:
            user.emergency_balance -= req.amount
            if req.target_type == 'weekly':
                user.weekly_balance += req.amount
            elif req.target_type == 'monthly':
                user.monthly_balance += req.amount
            elif req.target_type == 'meeting':
                user.meeting_balance += req.amount
            
            req.status = 'Approved'
            flash("Self-pay request approved.")
        else:
            flash("Insufficient emergency funds.")
    else:
        req.status = 'Rejected'
        flash("Self-pay request rejected.")
        
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/loan/<int:loan_id>/<string:action>', methods=['POST'])
def handle_loan(loan_id, action):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    loan = Loan.query.get_or_404(loan_id)
    loan.status = 'Approved' if action == 'Approve' else 'Declined'
    db.session.commit()
    flash(f"Loan application {loan.status.lower()}.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully.")
    return redirect(url_for('admin_dashboard'))

# Init DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)