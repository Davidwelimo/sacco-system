import os
import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, render_template_string, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_zero_start_secret_key")

# Database Configuration
db_url = os.environ.get("DATABASE_URL", "sqlite:////tmp/sacco.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Setup Profile Picture Upload Folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==============================================================================
# BASE STYLES & JS (LIGHT/DARK MODE)
# ==============================================================================

THEME_CSS_CONTENT = """
<style>
  :root { --bg: #f7fafc; --card: #ffffff; --text: #2d3748; --subtext: #4a5568; --border: #e2e8f0; --nav-bg: #2d3748; --nav-admin: #1a365d; --input-bg: #ffffff; }
  [data-theme="dark"] { --bg: #1a202c; --card: #2d3748; --text: #f7fafc; --subtext: #a0aec0; --border: #4a5568; --nav-bg: #0f172a; --nav-admin: #0f172a; --input-bg: #4a5568; }
  * { box-sizing: border-box; margin: 0; padding: 0; transition: background 0.2s, color 0.2s; }
  body { font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }
  .navbar { background: var(--nav-bg); color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
  .admin-nav { background: var(--nav-admin); }
  .container { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
  .card { background: var(--card); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
  .bold { font-size: 28px; font-weight: bold; color: #18a169; margin: 5px 0; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
  label { font-size: 12px; font-weight: bold; color: var(--subtext); display: block; margin-bottom: 4px; }
  input, select { width: 100%; padding: 8px; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); border-radius: 4px; }
  .btn { padding: 8px 15px; background: #2b6cb0; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
  .btn-theme { background: transparent; border: 1px solid white; color: white; padding: 4px 10px; border-radius: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text); }
  th { background: var(--border); }
  .badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
  .badge-Pending, .badge-Unpaid { background: #feebc8; color: #c05621; }
  .badge-Approved, .badge-Resolved, .badge-Paid, .badge-Confirmed { background: #c6f6d5; color: #22543d; }
  .badge-Rejected { background: #fed7d7; color: #9b2c2c; }
  .badge-Partial { background: #e2e8f0; color: #4a5568; }
  .avatar-img { width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); }
  .avatar-placeholder { width: 45px; height: 45px; border-radius: 50%; background: #abacc0; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; }
  .msg { color: #e53e3e; font-size: 13px; margin-bottom: 10px; }
  .success { color: #38a169; }
  .tab-btn { background: none; border: none; color: #2b6cb0; text-decoration: underline; cursor: pointer; }
</style>
<script>
  function toggleTheme() {
    let theme = localStorage.getItem('theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }
  window.onload = function() {
    let savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
  };
</script>
"""

@app.context_processor
def inject_theme():
    return dict(theme_css=THEME_CSS_CONTENT)

# ==============================================================================
# DATABASE MODELS
# ==============================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="Member")
    avatar = db.Column(db.String(200), nullable=True)
    
    weekly_savings = db.Column(db.Float, default=0.0)
    monthly_savings = db.Column(db.Float, default=0.0)
    emergency_savings = db.Column(db.Float, default=0.0)

class WeeklyContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="Unpaid")

class MonthlyContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    month_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="Unpaid")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    member_name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    ref_code = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    date = db.Column(db.String(20), nullable=False)

class TransferRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_username = db.Column(db.String(80), nullable=False)
    recipient_username = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending")
    date = db.Column(db.String(20), nullable=False)

class ResetRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    member_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    date = db.Column(db.String(20), nullable=False)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="Admin").first():
        admin = User(
            username="admin",
            name="SACCO Admin",
            email="admin@sacco.com",
            phone="0000000000",
            password="admin123",
            role="Admin"
        )
        db.session.add(admin)
        db.session.commit()

def initialize_member_schedule(username, year):
    for week in range(1, 53):
        if not WeeklyContribution.query.filter_by(username=username, week_number=week, year=year).first():
            w = WeeklyContribution(username=username, week_number=week, year=year, amount_paid=0.0, status="Unpaid")
            db.session.add(w)
    for month in range(1, 13):
        if not MonthlyContribution.query.filter_by(username=username, month_number=month, year=year).first():
            m = MonthlyContribution(username=username, month_number=month, year=year, amount_paid=0.0, status="Unpaid")
            db.session.add(m)
    db.session.commit()

def process_member_deposit(user, deposit_amount):
    remaining = deposit_amount
    current_year = datetime.date.today().year

    initialize_member_schedule(user.username, current_year)

    unpaid_weeks = WeeklyContribution.query.filter_by(username=user.username, status="Unpaid")\
                                           .order_by(WeeklyContribution.week_number.asc()).all()
    for w in unpaid_weeks:
        needed = 50.0 - w.amount_paid
        if remaining >= needed:
            remaining -= needed
            w.amount_paid = 50.0
            w.status = "Paid"
            user.weekly_savings += needed
        elif remaining > 0:
            w.amount_paid += remaining
            w.status = "Partial"
            user.weekly_savings += remaining
            remaining = 0
            break

    if remaining > 0:
        unpaid_months = MonthlyContribution.query.filter_by(username=user.username, status="Unpaid")\
                                                 .order_by(MonthlyContribution.month_number.asc()).all()
        for m in unpaid_months:
            needed = 200.0 - m.amount_paid
            if remaining >= needed:
                remaining -= needed
                m.amount_paid = 200.0
                m.status = "Paid"
                user.monthly_savings += needed
            elif remaining > 0:
                m.amount_paid += remaining
                m.status = "Partial"
                user.monthly_savings += remaining
                remaining = 0
                break

    if remaining > 0:
        user.emergency_savings += remaining

# ==============================================================================
# HTML TEMPLATES
# ==============================================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SACCO Portal - Login & Register</title>
  {{ theme_css | safe }}
</head>
<body style="display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0;">
  <div class="box card" style="width: 360px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h2>SACCO Portal</h2>
      <button class="btn-theme" onclick="toggleTheme()" style="color:var(--text); border-color:var(--border);">Theme</button>
    </div>
    {% if error %}<div class="msg">{{ error }}</div>{% endif %}
    {% if success %}<div class="msg success">{{ success }}</div>{% endif %}

    <div id="login-form">
      <form method="POST" action="/login">
        <div style="margin-bottom: 10px;">
          <label>Username / Email</label>
          <input type="text" name="identity" required>
        </div>
        <div style="margin-bottom: 10px;">
          <label>Password</label>
          <input type="password" name="password" required>
        </div>
        <button type="submit" class="btn" style="width:100%; margin-top: 10px;">Login</button>
      </form>
      <div style="margin-top: 15px; text-align: center; font-size: 12px;">
        <button class="tab-btn" onclick="toggleView('register-form')">New Member? Register Here</button>
        <button class="tab-btn" onclick="toggleView('forgot-form')" style="color: #e53e3e;">Forgot Password?</button>
      </div>
    </div>

    <div id="register-form" style="display:none;">
      <form method="POST" action="/register" enctype="multipart/form-data">
        <div style="margin-bottom: 10px;">
          <label>Full Name</label>
          <input type="text" name="name" required>
        </div>
        <div style="margin-bottom: 10px;">
          <label>Username</label>
          <input type="text" name="username" required>
        </div>
        <div style="margin-bottom: 10px;">
          <label>Email</label>
          <input type="email" name="email" required>
        </div>
        <div style="margin-bottom: 10px;">
          <label>Phone Number</label>
          <input type="text" name="phone" placeholder="0712345678" required>
        </div>
        <div style="margin-bottom: 10px;">
          <label>Profile Picture (Optional)</label>
          <input type="file" name="avatar" accept="image/*">
        </div>
        <div style="margin-bottom: 10px;">
          <label>Password</label>
          <input type="password" name="password" required>
        </div>
        <button type="submit" class="btn" style="width:100%; background: #38a169;">Create Account</button>
      </form>
      <div style="margin-top: 15px; text-align: center; font-size: 12px;">
        <button class="tab-btn" onclick="toggleView('login-form')">Already registered? Login</button>
      </div>
    </div>

    <div id="forgot-form" style="display:none;">
      <p style="font-size: 12px; color:var(--subtext); margin-bottom: 10px;">Enter your username or phone. The admin will reset your password.</p>
      <form method="POST" action="/request_reset">
        <div style="margin-bottom: 10px;">
          <label>Username or Phone Number</label>
          <input type="text" name="identity" required>
        </div>
        <button type="submit" class="btn" style="width:100%; background: #dd6b20;">Request Reset</button>
      </form>
      <div style="margin-top: 15px; text-align: center; font-size: 12px;">
        <button class="tab-btn" onclick="toggleView('login-form')">Back to Login</button>
      </div>
    </div>
  </div>

  <script>
    function toggleView(targetId) {
      document.getElementById('login-form').style.display = 'none';
      document.getElementById('register-form').style.display = 'none';
      document.getElementById('forgot-form').style.display = 'none';
      document.getElementById(targetId).style.display = 'block';
    }
  </script>
</body>
</html>
"""

ADMIN_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SACCO Admin Control Center</title>
  {{ theme_css | safe }}
</head>
<body>
  <div class="navbar admin-nav">
    <h2>SACCO Admin Control Center</h2>
    <div>
      Logged in as: <strong>{{ admin.username }}</strong>
      <button class="btn-theme" onclick="toggleTheme()">Theme</button>
      <a href="/logout" style="color: #feb2b2;">Logout</a>
    </div>
  </div>

  <div class="container">
    {% if msg %}<div class="card msg success"><strong>{{ msg }}</strong></div>{% endif %}
    {% if err %}<div class="card msg"><strong>{{ err }}</strong></div>{% endif %}

    <div class="card">
      <h2>1. Admin Security Settings</h2>
      <form method="POST" action="/admin/update_credentials">
        <div class="form-grid">
          <div>
            <label>New Admin Username</label>
            <input type="text" name="new_username" value="{{ admin.username }}" required>
          </div>
          <div>
            <label>New Password</label>
            <input type="password" name="new_password" placeholder="Leave blank to keep current">
          </div>
        </div>
        <br>
        <button type="submit" class="btn">Update Credentials</button>
      </form>
    </div>

    <div class="card">
      <h2>2. Emergency Fund Transfer Requests (Friend Help)</h2>
      <table>
        <thead>
          <tr><th>#</th><th>Sender</th><th>Recipient</th><th>Amount</th><th>Status</th><th>Action</th></tr>
        </thead>
        <tbody>
          {% for t in transfers %}
          <tr>
            <td>{{ t.id }}</td>
            <td>{{ t.sender_username }}</td>
            <td>{{ t.recipient_username }}</td>
            <td><strong>KES {{ "{:,.2f}".format(t.amount) }}</strong></td>
            <td><span class="badge badge-{{ t.status }}">{{ t.status }}</span></td>
            <td>
              {% if t.status == 'Pending' %}
              <a href="/admin/approve_transfer/{{ t.id }}" class="btn" style="background: #38a169; text-decoration: none;">Approve</a>
              <a href="/admin/reject_transfer/{{ t.id }}" class="btn" style="background: #e53e3e; text-decoration: none;">Reject</a>
              {% else %}
              <span style="color:var(--subtext); font-size: 11px;">Processed</span>
              {% endif %}
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;">No emergency transfer requests pending.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>3. Registered Members & Breakdown</h2>
      <table>
        <thead>
          <tr><th>Photo</th><th>Name</th><th>Weekly (50/wk)</th><th>Monthly (200/mo)</th><th>Emergency Reserve</th><th>Action</th></tr>
        </thead>
        <tbody>
          {% for m in members %}
          <tr>
            <td>
              {% if m.avatar %}
              <img src="/uploads/{{ m.avatar }}" class="avatar-img">
              {% else %}
              <div class="avatar-placeholder">{{ m.name[0].upper() }}</div>
              {% endif %}
            </td>
            <td><strong>{{ m.name }}</strong><br><small>@{{ m.username }}</small></td>
            <td style="color: #38a169;">KES {{ "{:,.2f}".format(m.weekly_savings) }}</td>
            <td style="color: #2b6cb0;">KES {{ "{:,.2f}".format(m.monthly_savings) }}</td>
            <td style="color: #dd6b20; font-weight: bold;">KES {{ "{:,.2f}".format(m.emergency_savings) }}</td>
            <td>
              <a href="/admin/remove_member/{{ m.username }}" class="btn" style="background: #e53e3e; text-decoration: none;">Remove</a>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;">No members registered yet.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>4. Deposit Verification Requests</h2>
      <table>
        <thead>
          <tr><th>#</th><th>Member</th><th>Amount</th><th>Ref Code</th><th>Status</th><th>Action</th></tr>
        </thead>
        <tbody>
          {% for p in payments %}
          <tr>
            <td>{{ p.id }}</td>
            <td>{{ p.member_name }} ({{ p.username }})</td>
            <td><strong>KES {{ "{:,.2f}".format(p.amount) }}</strong></td>
            <td><code>{{ p.ref_code }}</code></td>
            <td><span class="badge badge-{{ p.status }}">{{ p.status }}</span></td>
            <td>
              {% if p.status == 'Pending' %}
              <a href="/admin/confirm_payment/{{ p.id }}" class="btn" style="background: #38a169; text-decoration: none;">Confirm & Allocate</a>
              <a href="/admin/reject_payment/{{ p.id }}" class="btn" style="background: #e53e3e; text-decoration: none;">Reject</a>
              {% else %}
              <span style="color:var(--subtext); font-size: 11px;">Processed</span>
              {% endif %}
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;">No deposit requests.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>5. Password Reset Requests</h2>
      <table>
        <thead>
          <tr><th>#</th><th>Member</th><th>Phone</th><th>Date</th><th>Status</th><th>Action</th></tr>
        </thead>
        <tbody>
          {% for r in reset_requests %}
          <tr>
            <td>{{ r.id }}</td>
            <td>{{ r.member_name }} ({{ r.username }})</td>
            <td>{{ r.phone }}</td>
            <td>{{ r.date }}</td>
            <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
            <td>
              {% if r.status == 'Pending' %}
              <form method="POST" action="/admin/resolve_reset/{{ r.id }}" style="display:flex; gap: 5px;">
                <input type="text" name="new_password" placeholder="Set new pass" required style="width: 120px;">
                <button type="submit" class="btn" style="background: #dd6b20; margin-top:0;">Reset</button>
              </form>
              {% else %}
              <span style="color:var(--subtext); font-size: 11px;">Resolved</span>
              {% endif %}
            </td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;">No reset requests pending.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""

MEMBER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Member Portal - SACCO</title>
  {{ theme_css | safe }}
</head>
<body>
  <div class="navbar">
    <div style="display:flex; align-items:center; gap: 10px;">
      {% if member.avatar %}
      <img src="/uploads/{{ member.avatar }}" class="avatar-img">
      {% else %}
      <div class="avatar-placeholder">{{ member.name[0].upper() }}</div>
      {% endif %}
      <h2>SACCO Member Portal</h2>
    </div>
    <div>
      Logged in as: <strong>{{ member.name }}</strong> ({{ member.username }})
      <button class="btn-theme" onclick="toggleTheme()">Theme</button>
      <a href="/logout" style="color: #feb2b2; margin-left: 10px;">Logout</a>
    </div>
  </div>

  <div class="container">
    {% if msg %}<div class="card msg success"><strong>{{ msg }}</strong></div>{% endif %}
    {% if err %}<div class="card msg"><strong>{{ err }}</strong></div>{% endif %}

    <div class="form-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-bottom: 20px;">
      <div class="card">
        <label>Weekly Savings (KES 50/wk)</label>
        <div class="bold">KES {{ "{:,.2f}".format(member.weekly_savings) }}</div>
      </div>
      <div class="card">
        <label>Monthly Savings (KES 200/mo)</label>
        <div class="bold" style="color: #2b6cb0;">KES {{ "{:,.2f}".format(member.monthly_savings) }}</div>
      </div>
      <div class="card">
        <label>Emergency Savings (Excess Pool)</label>
        <div class="bold" style="color: #dd6b20;">KES {{ "{:,.2f}".format(member.emergency_savings) }}</div>
      </div>
    </div>

    <div class="card">
      <h2>Report Deposit / Payment</h2>
      <p style="font-size: 12px; color: var(--subtext); margin-bottom: 10px;">
        Deposits automatically fill unpaid KES 50 weekly & KES 200 monthly goals. Any extra amount automatically goes into your <strong>Emergency Savings</strong>.
      </p>
      <form method="POST" action="/member/notify_payment">
        <div class="form-grid">
          <div>
            <label>Amount Sent (KES)</label>
            <input type="number" name="amount" placeholder="e.g. 500" required>
          </div>
          <div>
            <label>M-Pesa Ref / Receipt Code</label>
            <input type="text" name="ref_code" placeholder="e.g. QCH0892KS" required>
          </div>
        </div>
        <br>
        <button type="submit" class="btn">Submit for Admin Confirmation</button>
      </form>
    </div>

    <div class="card">
      <h2>Help a Friend (Emergency Savings Request)</h2>
      <p style="font-size: 12px; color: var(--subtext); margin-bottom: 10px;">
        Use your Emergency Savings to clear a friend's unpaid contributions. Subject to Admin approval.
      </p>
      <form method="POST" action="/member/request_transfer">
        <div class="form-grid">
          <div>
            <label>Friend's Username</label>
            <select name="recipient_username" required>
              <option value="">-- Select Member --</option>
              {% for other in other_members %}
              <option value="{{ other.username }}">{{ other.name }} (@{{ other.username }})</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label>Amount (Max KES {{ "{:,.2f}".format(member.emergency_savings) }})</label>
            <input type="number" name="amount" placeholder="e.g. 100" max="{{ member.emergency_savings }}" required>
          </div>
        </div>
        <br>
        <button type="submit" class="btn" style="background: #dd6b20;">Request Transfer to Friend</button>
      </form>
    </div>

    <div class="card">
      <h2>Weekly Dues Progress (KES 50 / Week)</h2>
      <div style="max-height: 200px; overflow-y: auto;">
        <table>
          <thead>
            <tr><th>Week</th><th>Paid Amount</th><th>Status</th></tr>
          </thead>
          <tbody>
            {% for w in weeks %}
            <tr>
              <td>Week {{ w.week_number }} ({{ w.year }})</td>
              <td>KES {{ "{:,.2f}".format(w.amount_paid) }} / KES 50.00</td>
              <td><span class="badge badge-{{ w.status }}">{{ w.status }}</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>Monthly Dues Progress (KES 200 / Month)</h2>
      <div style="max-height: 200px; overflow-y: auto;">
        <table>
          <thead>
            <tr><th>Month</th><th>Paid Amount</th><th>Status</th></tr>
          </thead>
          <tbody>
            {% for m in months %}
            <tr>
              <td>Month {{ m.month_number }} ({{ m.year }})</td>
              <td>KES {{ "{:,.2f}".format(m.amount_paid) }} / KES 200.00</td>
              <td><span class="badge badge-{{ m.status }}">{{ m.status }}</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body>
</html>
"""

# ==============================================================================
# ROUTES
# ==============================================================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.role == 'Admin':
            return redirect(url_for('admin_dashboard'))
        elif user:
            return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity', '').lower().strip()
        password = request.form.get('password')

        user = User.query.filter((User.username == identity) | (User.email == identity)).first()
        if user and user.password == password:
            session['user_id'] = user.id
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('member_dashboard'))

        return render_template_string(LOGIN_HTML, error="Invalid credentials.")

    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    username = request.form.get('username', '').lower().strip()
    email = request.form.get('email', '').lower().strip()
    phone = request.form.get('phone')
    password = request.form.get('password')

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return render_template_string(LOGIN_HTML, error="Username or email already exists!")

    avatar_filename = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{username}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            avatar_filename = filename

    new_user = User(
        username=username,
        name=name,
        email=email,
        phone=phone,
        password=password,
        role="Member",
        avatar=avatar_filename
    )
    db.session.add(new_user)
    db.session.commit()

    initialize_member_schedule(username, datetime.date.today().year)

    return render_template_string(LOGIN_HTML, success="Registration successful! Please login below.")

@app.route('/request_reset', methods=['POST'])
def request_reset():
    identity = request.form.get('identity', '').lower().strip()
    user = User.query.filter((User.username == identity) | (User.phone == identity)).first()

    if user:
        today = datetime.date.today().strftime('%Y-%m-%d')
        req = ResetRequest(
            username=user.username,
            member_name=user.name,
            phone=user.phone,
            status="Pending",
            date=today
        )
        db.session.add(req)
        db.session.commit()
        return render_template_string(LOGIN_HTML, success="Reset request sent to Admin.")

    return render_template_string(LOGIN_HTML, error="No account found matching that username or phone.")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    admin = User.query.get(session['user_id'])
    if not admin or admin.role != 'Admin':
        return redirect(url_for('login'))

    members = User.query.filter_by(role="Member").all()
    payments = Payment.query.all()
    transfers = TransferRequest.query.all()
    reset_requests = ResetRequest.query.all()

    msg = request.args.get('msg')
    err = request.args.get('err')
    return render_template_string(ADMIN_DASHBOARD, admin=admin, members=members, payments=payments, transfers=transfers, reset_requests=reset_requests, msg=msg, err=err)

@app.route('/admin/update_credentials', methods=['POST'])
def update_credentials():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin = User.query.get(session['user_id'])
    if not admin or admin.role != 'Admin':
        return redirect(url_for('login'))

    new_username = request.form.get('new_username', '').lower().strip()
    new_password = request.form.get('new_password')

    existing = User.query.filter_by(username=new_username).first()
    if existing and existing.id != admin.id:
        return redirect(url_for('admin_dashboard', err="Username is already taken!"))

    admin.username = new_username
    if new_password:
        admin.password = new_password

    db.session.commit()
    return redirect(url_for('admin_dashboard', msg="Admin credentials updated successfully!"))

@app.route('/admin/confirm_payment/<int:pay_id>')
def confirm_payment(pay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment = Payment.query.get(pay_id)
    if payment and payment.status == 'Pending':
        payment.status = 'Confirmed'
        user = User.query.filter_by(username=payment.username).first()
        if user:
            process_member_deposit(user, payment.amount)
        db.session.commit()
        return redirect(url_for('admin_dashboard', msg="Payment confirmed and allocated!"))

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_payment/<int:pay_id>')
def reject_payment(pay_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment = Payment.query.get(pay_id)
    if payment and payment.status == 'Pending':
        payment.status = 'Rejected'
        db.session.commit()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve_transfer/<int:req_id>')
def approve_transfer(req_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    t = TransferRequest.query.get(req_id)
    if t and t.status == 'Pending':
        sender = User.query.filter_by(username=t.sender_username).first()
        recipient = User.query.filter_by(username=t.recipient_username).first()

        if sender and recipient and sender.emergency_savings >= t.amount:
            sender.emergency_savings -= t.amount
            process_member_deposit(recipient, t.amount)
            t.status = 'Approved'
            db.session.commit()
            return redirect(url_for('admin_dashboard', msg="Transfer approved! Recipient's dues have been updated."))
        else:
            return redirect(url_for('admin_dashboard', err="Sender has insufficient Emergency Savings."))

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_transfer/<int:req_id>')
def reject_transfer(req_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    t = TransferRequest.query.get(req_id)
    if t and t.status == 'Pending':
        t.status = 'Rejected'
        db.session.commit()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resolve_reset/<int:req_id>', methods=['POST'])
def resolve_reset(req_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_password = request.form.get('new_password')
    req = ResetRequest.query.get(req_id)

    if req and req.status == 'Pending':
        req.status = 'Resolved'
        user = User.query.filter_by(username=req.username).first()
        if user:
            user.password = new_password
        db.session.commit()
        return redirect(url_for('admin_dashboard', msg=f"Password for '{req.username}' updated."))

    return redirect(url_for('admin_dashboard', err="Request not found."))

@app.route('/admin/remove_member/<username>')
def remove_member(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        return redirect(url_for('admin_dashboard', msg=f"Member '{username}' removed."))

    return redirect(url_for('admin_dashboard', err="Member not found."))

@app.route('/member/dashboard')
def member_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    member = User.query.get(session['user_id'])
    if not member or member.role != 'Member':
        session.pop('user_id', None)
        return redirect(url_for('login'))

    current_year = datetime.date.today().year
    initialize_member_schedule(member.username, current_year)

    weeks = WeeklyContribution.query.filter_by(username=member.username, year=current_year).order_by(WeeklyContribution.week_number.asc()).all()
    months = MonthlyContribution.query.filter_by(username=member.username, year=current_year).order_by(MonthlyContribution.month_number.asc()).all()
    other_members = User.query.filter(User.role == 'Member', User.username != member.username).all()

    msg = request.args.get('msg')
    err = request.args.get('err')

    return render_template_string(MEMBER_DASHBOARD, member=member, weeks=weeks, months=months, other_members=other_members, msg=msg, err=err)

@app.route('/member/notify_payment', methods=['POST'])
def notify_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    member = User.query.get(session['user_id'])
    amount = float(request.form.get('amount', 0))
    ref_code = request.form.get('ref_code')

    p = Payment(
        username=member.username,
        member_name=member.name,
        amount=amount,
        ref_code=ref_code,
        status="Pending",
        date=datetime.date.today().strftime('%Y-%m-%d')
    )
    db.session.add(p)
    db.session.commit()

    return redirect(url_for('member_dashboard', msg="Payment reported! Awaiting Admin confirmation."))

@app.route('/member/request_transfer', methods=['POST'])
def request_transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    member = User.query.get(session['user_id'])
    recipient_username = request.form.get('recipient_username')
    amount = float(request.form.get('amount', 0))

    if amount > member.emergency_savings:
        return redirect(url_for('member_dashboard', err="Requested amount exceeds your Emergency Savings."))

    t = TransferRequest(
        sender_username=member.username,
        recipient_username=recipient_username,
        amount=amount,
        status="Pending",
        date=datetime.date.today().strftime('%Y-%m-%d')
    )
    db.session.add(t)
    db.session.commit()

    return redirect(url_for('member_dashboard', msg="Transfer request submitted to Admin for approval."))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)