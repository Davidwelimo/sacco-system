import os
import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_zero_start_secret_key")

# ==========================================
# IN-MEMORY DATA STORES (STARTS AT ZERO)
# ==========================================

# Pre-created Admin account
USERS = {
    "admin": {
        "password": "admin123",
        "email": "admin@sacco.com",
        "role": "Admin",
        "name": "SACCO Admin"
    }
}

# Member list (Empty at start)
MEMBERS = {} # format: { username: { name, email, phone, balance, password, role="Member" } }

# Loan Applications (Empty at start)
LOANS = [] # { id, username, member_name, amount, purpose, duration, status }

# Payment / Deposit Verification Requests (Empty at start)
PAYMENTS = [] # { id, username, member_name, amount, ref_code, status, date }


# ==========================================
# HTML TEMPLATES
# ==========================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SACCO System - Login & Register</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .box { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 360px; }
        h2 { color: #1a365d; text-align: center; margin-bottom: 20px; }
        .form-group { margin-bottom: 12px; }
        label { font-size: 13px; font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px; }
        input, select { width: 100%; padding: 9px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; }
        .btn { width: 100%; padding: 10px; background: #2b6cb0; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .btn-alt { background: #38a169; }
        .tab-btn { background: none; border: none; color: #2b6cb0; cursor: pointer; text-decoration: underline; font-size: 13px; margin-top: 15px; width: 100%; text-align: center; }
        .msg { color: #e53e3e; font-size: 13px; margin-bottom: 10px; text-align: center; }
        .success { color: #38a169; }
    </style>
</head>
<body>
    <div class="box">
        <h2>SACCO Portal</h2>
        {% if error %}<div class="msg">{{ error }}</div>{% endif %}
        {% if success %}<div class="msg success">{{ success }}</div>{% endif %}

        <div id="login-form">
            <form method="POST" action="/login">
                <div class="form-group">
                    <label>Username / Email</label>
                    <input type="text" name="identity" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn">Login</button>
            </form>
            <button class="tab-btn" onclick="toggleForm()">New Member? Register Here</button>
        </div>

        <div id="register-form" style="display:none;">
            <form method="POST" action="/register">
                <div class="form-group">
                    <label>Full Name</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required>
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" name="email" required>
                </div>
                <div class="form-group">
                    <label>Phone Number (M-Pesa)</label>
                    <input type="text" name="phone" placeholder="0712345678" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-alt">Create Account (Starts at KES 0)</button>
            </form>
            <button class="tab-btn" onclick="toggleForm()">Already registered? Login</button>
        </div>
    </div>

    <script>
        function toggleForm() {
            var l = document.getElementById('login-form');
            var r = document.getElementById('register-form');
            if (l.style.display === 'none') {
                l.style.display = 'block'; r.style.display = 'none';
            } else {
                l.style.display = 'none'; r.style.display = 'block';
            }
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
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f7fafc; color: #2d3748; }
        .navbar { background: #1a365d; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 25px; }
        h2 { color: #1a365d; margin-bottom: 15px; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
        th { background: #edf2f7; font-weight: bold; }
        .btn { padding: 5px 10px; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; text-decoration: none; font-size: 11px; }
        .btn-green { background: #38a169; }
        .btn-red { background: #e53e3e; }
        .badge { padding: 3px 7px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-Pending { background: #feebc8; color: #c05621; }
        .badge-Approved, .badge-Confirmed { background: #c6f6d5; color: #22543d; }
        .badge-Rejected { background: #fed7d7; color: #9b2c2c; }
    </style>
</head>
<body>
    <div class="navbar">
        <h2>SACCO Admin Control Center</h2>
        <div>Logged in as: <strong>Admin</strong> | <a href="/logout" style="color: #feb2b2;">Logout</a></div>
    </div>
    <div class="container">
        
        <!-- SECTION 1: MEMBERS DIRECTORY & BALANCES -->
        <div class="card">
            <h2>1. Registered SACCO Members (Total: {{ members|length }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Full Name</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>Savings Balance (KES)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for uname, m in members.items() %}
                    <tr>
                        <td><strong>{{ uname }}</strong></td>
                        <td>{{ m.name }}</td>
                        <td>{{ m.email }}</td>
                        <td>{{ m.phone }}</td>
                        <td style="color: #2b6cb0; font-weight: bold;">KES {{ "{:,}".format(m.balance) }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" style="text-align:center; color:#718096;">No members registered yet. System starting from zero.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- SECTION 2: PAYMENT / DEPOSIT CONFIRMATION QUEUE -->
        <div class="card">
            <h2>2. Payment & Deposit Verification Requests</h2>
            <p style="font-size: 12px; color: #718096; margin-bottom: 10px;">Verify M-Pesa / Bank Reference code before confirming funds into member balance.</p>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Member</th>
                        <th>Amount (KES)</th>
                        <th>Ref Code / Receipt</th>
                        <th>Date</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in payments %}
                    <tr>
                        <td>#{{ p.id }}</td>
                        <td>{{ p.member_name }} ({{ p.username }})</td>
                        <td><strong>KES {{ "{:,}".format(p.amount) }}</strong></td>
                        <td><code>{{ p.ref_code }}</code></td>
                        <td>{{ p.date }}</td>
                        <td><span class="badge badge-{{ p.status }}">{{ p.status }}</span></td>
                        <td>
                            {% if p.status == 'Pending' %}
                                <a href="/admin/confirm_payment/{{ p.id }}" class="btn btn-green">Confirm & Add Funds</a>
                                <a href="/admin/reject_payment/{{ p.id }}" class="btn btn-red">Reject</a>
                            {% else %}
                                <span style="color:#a0aec0; font-size:11px;">Processed</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" style="text-align:center; color:#718096;">No payment verification claims submitted yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- SECTION 3: LOAN REQUESTS -->
        <div class="card">
            <h2>3. Member Loan Applications</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Member</th>
                        <th>Amount (KES)</th>
                        <th>Purpose</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for l in loans %}
                    <tr>
                        <td>#{{ l.id }}</td>
                        <td>{{ l.member_name }}</td>
                        <td>KES {{ "{:,}".format(l.amount) }}</td>
                        <td>{{ l.purpose }}</td>
                        <td>{{ l.duration }} Months</td>
                        <td><span class="badge badge-{{ l.status }}">{{ l.status }}</span></td>
                        <td>
                            {% if l.status == 'Pending' %}
                                <a href="/admin/approve_loan/{{ l.id }}" class="btn btn-green">Approve</a>
                                <a href="/admin/reject_loan/{{ l.id }}" class="btn btn-red">Reject</a>
                            {% else %}
                                <span style="color:#a0aec0; font-size:11px;">Completed</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" style="text-align:center; color:#718096;">No loan requests yet.</td></tr>
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
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f7fafc; color: #2d3748; }
        .navbar { background: #2b6cb0; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .container { max-width: 900px; margin: 30px auto; padding: 0 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 20px; }
        h2 { color: #2b6cb0; margin-bottom: 15px; font-size: 18px; }
        .bal { font-size: 32px; font-weight: bold; color: #276749; margin: 10px 0; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        label { font-size: 12px; font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px; }
        input { width: 100%; padding: 8px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; }
        .btn { padding: 10px 15px; background: #2b6cb0; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
        th { background: #edf2f7; }
        .badge { padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-Pending { background: #feebc8; color: #c05621; }
        .badge-Confirmed, .badge-Approved { background: #c6f6d5; color: #22543d; }
        .badge-Rejected { background: #fed7d7; color: #9b2c2c; }
    </style>
</head>
<body>
    <div class="navbar">
        <h2>SACCO Member Portal</h2>
        <div>Logged in as: <strong>{{ member.name }}</strong> | <a href="/logout" style="color: #e2e8f0;">Logout</a></div>
    </div>
    <div class="container">
        
        <!-- SAVINGS BALANCE -->
        <div class="card">
            <h2>Your SACCO Savings Balance</h2>
            <div class="bal">KES {{ "{:,}".format(member.balance) }}</div>
            <p style="font-size: 12px; color: #718096;">Deposits will reflect here once confirmed by Admin.</p>
        </div>

        <!-- REPORT MONEY SENT -->
        <div class="card">
            <h2>Report Payment / Send Money to Admin</h2>
            <form method="POST" action="/member/notify_payment">
                <div class="form-grid">
                    <div>
                        <label>Amount Sent (KES)</label>
                        <input type="number" name="amount" placeholder="e.g. 5000" required>
                    </div>
                    <div>
                        <label>M-Pesa Ref / Transaction Code</label>
                        <input type="text" name="ref_code" placeholder="e.g. QKH892JKS" required>
                    </div>
                </div>
                <button type="submit" class="btn">Submit for Admin Confirmation</button>
            </form>
        </div>

        <!-- REQUEST LOAN -->
        <div class="card">
            <h2>Request a Loan</h2>
            <form method="POST" action="/member/apply_loan">
                <div class="form-grid">
                    <div>
                        <label>Loan Amount (KES)</label>
                        <input type="number" name="amount" placeholder="e.g. 20000" required>
                    </div>
                    <div>
                        <label>Purpose</label>
                        <input type="text" name="purpose" placeholder="e.g. Emergency, Stock" required>
                    </div>
                    <div>
                        <label>Repayment Duration (Months)</label>
                        <input type="number" name="duration" placeholder="6" required>
                    </div>
                </div>
                <button type="submit" class="btn" style="background:#38a169;">Submit Loan Application</button>
            </form>
        </div>

        <!-- YOUR PAYMENT CLAIMS HISTORY -->
        <div class="card">
            <h2>Your Payment/Deposit Submissions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ref Code</th>
                        <th>Amount</th>
                        <th>Date</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in user_payments %}
                    <tr>
                        <td><code>{{ p.ref_code }}</code></td>
                        <td>KES {{ "{:,}".format(p.amount) }}</td>
                        <td>{{ p.date }}</td>
                        <td><span class="badge badge-{{ p.status }}">{{ p.status }}</span></td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" style="text-align:center; color:#718096;">No payments reported yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

    </div>
</body>
</html>
"""

# ==========================================
# ROUTES & LOGIC
# ==========================================

@app.route('/')
def home():
    if 'user' in session:
        if session['user']['role'] == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity')
        password = request.form.get('password')

        # Check Admin
        for uname, details in USERS.items():
            if identity in (uname, details['email']) and details['password'] == password:
                session['user'] = details
                return redirect(url_for('admin_dashboard'))

        # Check Members
        for uname, details in MEMBERS.items():
            if identity in (uname, details['email']) and details['password'] == password:
                session['user'] = details
                return redirect(url_for('member_dashboard'))

        return render_template_string(LOGIN_HTML, error="Invalid credentials.")

    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    username = request.form.get('username').lower().strip()
    email = request.form.get('email').lower().strip()
    phone = request.form.get('phone')
    password = request.form.get('password')

    if username in MEMBERS or username in USERS:
        return render_template_string(LOGIN_HTML, error="Username already exists!")

    MEMBERS[username] = {
        "username": username,
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "balance": 0,  # STARTS AT ZERO
        "role": "Member"
    }

    return render_template_string(LOGIN_HTML, success="Registration successful! Please login below.")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))
    return render_template_string(ADMIN_DASHBOARD, members=MEMBERS, payments=PAYMENTS, loans=LOANS)

@app.route('/admin/confirm_payment/<int:pay_id>')
def confirm_payment(pay_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    for p in PAYMENTS:
        if p['id'] == pay_id and p['status'] == 'Pending':
            p['status'] = 'Confirmed'
            # Credit member's balance!
            uname = p['username']
            if uname in MEMBERS:
                MEMBERS[uname]['balance'] += p['amount']
            break

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_payment/<int:pay_id>')
def reject_payment(pay_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    for p in PAYMENTS:
        if p['id'] == pay_id and p['status'] == 'Pending':
            p['status'] = 'Rejected'
            break

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve_loan/<int:loan_id>')
def approve_loan(loan_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    for l in LOANS:
        if l['id'] == loan_id:
            l['status'] = 'Approved'
            break

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_loan/<int:loan_id>')
def reject_loan(loan_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    for l in LOANS:
        if l['id'] == loan_id:
            l['status'] = 'Rejected'
            break

    return redirect(url_for('admin_dashboard'))

@app.route('/member/dashboard')
def member_dashboard():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    uname = session['user']['username']
    current_member = MEMBERS.get(uname, session['user'])
    user_payments = [p for p in PAYMENTS if p['username'] == uname]

    return render_template_string(MEMBER_DASHBOARD, member=current_member, user_payments=user_payments)

@app.route('/member/notify_payment', methods=['POST'])
def notify_payment():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    uname = session['user']['username']
    amount = int(request.form.get('amount', 0))
    ref_code = request.form.get('ref_code')
    today = datetime.date.today().strftime('%Y-%m-%d')

    PAYMENTS.append({
        "id": len(PAYMENTS) + 1,
        "username": uname,
        "member_name": session['user']['name'],
        "amount": amount,
        "ref_code": ref_code,
        "status": "Pending",
        "date": today
    })

    return redirect(url_for('member_dashboard'))

@app.route('/member/apply_loan', methods=['POST'])
def apply_loan():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    uname = session['user']['username']
    amount = int(request.form.get('amount', 0))
    purpose = request.form.get('purpose')
    duration = int(request.form.get('duration', 6))

    LOANS.append({
        "id": len(LOANS) + 101,
        "username": uname,
        "member_name": session['user']['name'],
        "amount": amount,
        "purpose": purpose,
        "duration": duration,
        "status": "Pending"
    })

    return redirect(url_for('member_dashboard'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)