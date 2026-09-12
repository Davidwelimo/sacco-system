from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='Member')
    
    weekly_balance = db.Column(db.Float, default=0.0)
    savings_balance = db.Column(db.Float, default=0.0)
    loan_repayment_balance = db.Column(db.Float, default=0.0)
    collateral_balance = db.Column(db.Float, default=0.0)
    
    reset_otp = db.Column(db.String(10), nullable=True)
    reset_otp_requested = db.Column(db.Boolean, default=False)
    
    # Profile Picture field added
    profile_pic = db.Column(db.String(255), nullable=True, default='uploads/default_avatar.png')

    contributions = db.relationship('Contribution', backref='user', lazy=True)
    loans = db.relationship('Loan', backref='user', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user', lazy=True)

class Contribution(db.Model):
    __tablename__ = 'contribution'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_method = db.Column(db.String(50), default='Mpesa')
    account_type = db.Column(db.String(50), nullable=False) # Weekly Contribution, Personal Savings, Loan Repayment, Collateral Damage
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Declined
    date_made = db.Column(db.DateTime, default=datetime.utcnow)

class Loan(db.Model):
    __tablename__ = 'loan'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Declined
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_by_member = db.Column(db.Boolean, default=False)
    deleted_by_admin = db.Column(db.Boolean, default=False)

class Announcement(db.Model):
    __tablename__ = 'announcement'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(200), nullable=True)
    publisher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)