import os
import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_zero_start_secret_key")

# ==========================================
# IN-MEMORY DATA STORES
# ==========================================

ADMIN_PROFILE = {
    "username": "admin",
    "password": "admin123",
    "email": "admin@sacco.com",
    "role": "Admin",
    "name": "SACCO Admin"
}

MEMBERS = {} # format: { username: { name, email, phone, balance, password, role="Member" } }
LOANS = [] # { id, username, member_name, amount, purpose, duration, status }
PAYMENTS = [] # { id, username, member_name, amount, ref_code, status, date }
RESET_REQUESTS = [] # { id, username, member_name, phone, status, date }


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
        input { width: 100%; padding: 9px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; }
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
            <button class="tab-btn" onclick="toggleView('register-form')">New Member? Register Here</button>
            <button class="tab-btn" onclick="toggleView('forgot-form')" style="color:#e53e3e;">Forgot Password?</button>
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
                <button type="submit" class="btn btn-alt">Create Account</button>
            </form>
            <button class="tab-btn" onclick="toggleView('login-form')">Already registered? Login</button>
        </div>

        <div id="forgot-form" style="display:none;">
            <p style="font-size:12px; color:#4a5568; margin-bottom:10px;">Submit your username or phone. The Admin will verify and set a new password for you.</p>
            <form method="POST" action="/request_reset">
                <div class="form-group">
                    <label>Your Username or Phone Number</label>
                    <input type="text" name="identity" required>
                </div>
                <button type="submit" class="btn" style="background:#dd6b20;">Request Admin Reset</button>
            </form>
            <button class="tab-btn" onclick="toggleView('login-form')">Back to Login</button>
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
        .btn-blue { background: #2b6cb0; }
        .btn-orange { background: #dd6b20; }
        .badge { padding: 3px 7px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .badge-Pending { background: #feebc8; color: #c05621; }
        .badge-Approved, .badge-Confirmed, .badge-Resolved { background: #c6f6d5; color: #22543d; }
        .badge-Rejected { background: #fed7d7; color: #9b2c2c; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 10px; }
        label { font-size: 12px; font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px; }
        input { width: 100%; padding: 8px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; }
        .msg { color: #e53e3e; font-size: 13px; margin-bottom: 10px; }
        .success { color: #38a169; }
        .reset-form { display: flex; gap: 5px; }
    </style>
</head>
<body>
    <div class="navbar">
        <h2>SACCO Admin Control Center</h2>
        <div>Logged in as: <strong>{{ admin.username }}</strong> | <a href="/logout" style="color: #feb2b2;">Logout</a></div>
    </div>
    <div class="container">

        {% if msg %}<div class="card msg success"><strong>{{ msg }}</strong></div>{% endif %}
        {% if err %}<div class="card msg"><strong>{{ err }}</strong></div>{% endif %}

        <!-- SECTION 1: ADMIN CREDENTIALS -->
        <div class="card">
            <h2>1. Admin Security Settings (Update Credentials)</h2>
            <form method="POST" action="/admin/update_credentials">
                <div class="form-grid">
                    <div>
                        <label>New Admin Username</label>
                        <input type="text" name="new_username" value="{{ admin.username }}" required>
                    </div>
                    <div>
                        <label>New Password</label>
                        <input type="password" name="new_password" placeholder="Leave blank to keep current password">
                    </div>
                </div>
                <button type="submit" class="btn btn-blue" style="margin-top:12px; padding: 8px 15px;">Update Credentials</button>
            </form>
        </div>

        <!-- SECTION 2: FORGOT PASSWORD REQUESTS -->
        <div class="card">
            <h2>2. Password Reset Requests (Approvals)</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Member</th>
                        <th>Phone</th>
                        <th>Date</th>
                        <th>Status</th>
                        <th>Action / Reset Password</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in reset_requests %}
                    <tr>
                        <td>#{{ r.id }}</td>
                        <td>{{ r.member_name }} (<strong>{{ r.username }}</strong>)</td>
                        <td>{{ r.phone }}</td>
                        <td>{{ r.date }}</td>
                        <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
                        <td>
                            {% if r.status == 'Pending' %}
                            <form method="POST" action="/admin/resolve_reset/{{ r.id }}" class="reset-form">
                                <input type="text" name="new_password" placeholder="Set new pass" required style="padding:4px; font-size:11px; width:130px;">
                                <button type="submit" class="btn btn-orange">Set New Password</button>
                            </form>
                            {% else %}
                            <span style="color:#a0aec0; font-size:11px;">Resolved</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="6" style="text-align:center; color:#718096;">No password reset requests pending.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- SECTION 3: MEMBERS DIRECTORY, REMOVAL & MANUAL PASSWORD OVERRIDE -->
        <div class="card">
            <h2>3. Registered SACCO Members (Total: {{ members|length }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Full Name</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>Savings Balance</th>
                        <th>Manual Password Override</th>
                        <th>Action</th>
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
                        <td>
                            <form method="POST" action="/admin/direct_reset/{{ uname }}" class="reset-form">
                                <input type="text" name="new_password" placeholder="New password" required style="padding:4px; font-size:11px; width:110px;">
                                <button type="submit" class="btn btn-blue">Change</button>
                            </form>
                        </td>
                        <td>
                            <a href="/admin/remove_member/{{ uname }}" class="btn btn-red" onclick="return confirm('Are you sure you want to remove member {{ uname }}?');">Remove</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" style="text-align:center; color:#718096;">No members registered yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- SECTION 4: PAYMENTS QUEUE -->
        <div class="card">
            <h2>4. Deposit Verification Requests</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Member</th>
                        <th>Amount</th>
                        <th>Ref Code</th>
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
                                <a href="/admin/confirm_payment/{{ p.id }}" class="btn btn-green">Confirm</a>
                                <a href="/admin/reject_payment/{{ p.id }}" class="btn btn-red">Reject</a>
                            {% else %}
                                <span style="color:#a0aec0; font-size:11px;">Processed</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" style="text-align:center; color:#718096;">No deposit requests.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- SECTION 5: LOANS -->
        <div class="card">
            <h2>5. Member Loan Applications</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Member</th>
                        <th>Amount</th>
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
        .msg { color: #e53e3e; font-size: 13px; margin-bottom: 10px; }
        .success { color: #38a169; }
    </style>
</head>
<body>
    <div class="navbar">
        <h2>SACCO Member Portal</h2>
        <div>Logged in as: <strong>{{ member.name }}</strong> ({{ member.username }}) | <a href="/logout" style="color: #e2e8f0;">Logout</a></div>
    </div>
    <div class="container">
        
        {% if msg %}<div class="card msg success"><strong>{{ msg }}</strong></div>{% endif %}
        {% if err %}<div class="card msg"><strong>{{ err }}</strong></div>{% endif %}

        <div class="card">
            <h2>Your SACCO Savings Balance</h2>
            <div class="bal">KES {{ "{:,}".format(member.balance) }}</div>
        </div>

        <!-- PROFILE UPDATE SECTION -->
        <div class="card">
            <h2>Account Settings (Update Username / Password)</h2>
            <form method="POST" action="/member/update_profile">
                <div class="form-grid">
                    <div>
                        <label>Your Username</label>
                        <input type="text" name="new_username" value="{{ member.username }}" required>
                    </div>
                    <div>
                        <label>New Password</label>
                        <input type="password" name="new_password" placeholder="Leave blank to keep current password">
                    </div>
                </div>
                <button type="submit" class="btn" style="background:#4a5568;">Save Changes</button>
            </form>
        </div>

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
                        <input type="text" name="purpose" placeholder="e.g. Emergency" required>
                    </div>
                    <div>
                        <label>Repayment Duration (Months)</label>
                        <input type="number" name="duration" placeholder="6" required>
                    </div>
                </div>
                <button type="submit" class="btn" style="background:#38a169;">Submit Loan Application</button>
            </form>
        </div>

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
        identity = request.form.get('identity').lower().strip()
        password = request.form.get('password')

        # Check Admin
        if identity in (ADMIN_PROFILE['username'].lower(), ADMIN_PROFILE['email'].lower()) and ADMIN_PROFILE['password'] == password:
            session['user'] = ADMIN_PROFILE
            return redirect(url_for('admin_dashboard'))

        # Check Members
        for uname, details in MEMBERS.items():
            if identity in (uname.lower(), details['email'].lower()) and details['password'] == password:
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

    if username in MEMBERS or username == ADMIN_PROFILE['username'].lower():
        return render_template_string(LOGIN_HTML, error="Username already exists!")

    MEMBERS[username] = {
        "username": username,
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "balance": 0,
        "role": "Member"
    }

    return render_template_string(LOGIN_HTML, success="Registration successful! Please login below.")

@app.route('/request_reset', methods=['POST'])
def request_reset():
    identity = request.form.get('identity').lower().strip()
    target_member = None

    for uname, m in MEMBERS.items():
        if identity in (uname.lower(), m['phone'].lower()):
            target_member = m
            break

    if target_member:
        today = datetime.date.today().strftime('%Y-%m-%d')
        RESET_REQUESTS.append({
            "id": len(RESET_REQUESTS) + 1,
            "username": target_member['username'],
            "member_name": target_member['name'],
            "phone": target_member['phone'],
            "status": "Pending",
            "date": today
        })
        return render_template_string(LOGIN_HTML, success="Reset request sent to Admin. Contact the Admin to approve and get your new password.")
    
    return render_template_string(LOGIN_HTML, error="No account found matching that username or phone number.")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))
    msg = request.args.get('msg')
    err = request.args.get('err')
    return render_template_string(ADMIN_DASHBOARD, admin=ADMIN_PROFILE, members=MEMBERS, payments=PAYMENTS, loans=LOANS, reset_requests=RESET_REQUESTS, msg=msg, err=err)

@app.route('/admin/update_credentials', methods=['POST'])
def update_credentials():
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    new_username = request.form.get('new_username').lower().strip()
    new_password = request.form.get('new_password')

    if new_username in MEMBERS:
        return redirect(url_for('admin_dashboard', err="Username is already taken by a member!"))

    ADMIN_PROFILE['username'] = new_username
    if new_password:
        ADMIN_PROFILE['password'] = new_password

    session['user'] = ADMIN_PROFILE
    return redirect(url_for('admin_dashboard', msg="Admin credentials updated successfully!"))

@app.route('/admin/resolve_reset/<int:req_id>', methods=['POST'])
def resolve_reset(req_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    new_password = request.form.get('new_password')

    for r in RESET_REQUESTS:
        if r['id'] == req_id and r['status'] == 'Pending':
            r['status'] = 'Resolved'
            uname = r['username']
            if uname in MEMBERS:
                MEMBERS[uname]['password'] = new_password
            return redirect(url_for('admin_dashboard', msg=f"Password for member '{uname}' updated to '{new_password}'."))

    return redirect(url_for('admin_dashboard', err="Request not found."))

@app.route('/admin/direct_reset/<username>', methods=['POST'])
def direct_reset(username):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    new_password = request.form.get('new_password')

    if username in MEMBERS:
        MEMBERS[username]['password'] = new_password
        return redirect(url_for('admin_dashboard', msg=f"Password for '{username}' changed to '{new_password}'."))

    return redirect(url_for('admin_dashboard', err="Member not found."))

@app.route('/admin/remove_member/<username>')
def remove_member(username):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    if username in MEMBERS:
        del MEMBERS[username]
        return redirect(url_for('admin_dashboard', msg=f"Member '{username}' removed successfully."))

    return redirect(url_for('admin_dashboard', err="Member not found."))

@app.route('/admin/confirm_payment/<int:pay_id>')
def confirm_payment(pay_id):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    for p in PAYMENTS:
        if p['id'] == pay_id and p['status'] == 'Pending':
            p['status'] = 'Confirmed'
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
    if uname not in MEMBERS:
        session.pop('user', None)
        return redirect(url_for('login'))

    current_member = MEMBERS[uname]
    user_payments = [p for p in PAYMENTS if p['username'] == uname]
    msg = request.args.get('msg')
    err = request.args.get('err')

    return render_template_string(MEMBER_DASHBOARD, member=current_member, user_payments=user_payments, msg=msg, err=err)

@app.route('/member/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    old_uname = session['user']['username']
    new_uname = request.form.get('new_username').lower().strip()
    new_password = request.form.get('new_password')

    if old_uname not in MEMBERS:
        return redirect(url_for('login'))

    # If changing username, make sure it's not taken by someone else
    if new_uname != old_uname and (new_uname in MEMBERS or new_uname == ADMIN_PROFILE['username'].lower()):
        return redirect(url_for('member_dashboard', err="That username is already taken!"))

    # Copy and update details
    member_data = MEMBERS.pop(old_uname)
    member_data['username'] = new_uname
    if new_password:
        member_data['password'] = new_password

    MEMBERS[new_uname] = member_data
    session['user'] = member_data

    # Update references in PAYMENTS & LOANS
    for p in PAYMENTS:
        if p['username'] == old_uname:
            p['username'] = new_uname
    for l in LOANS:
        if l['username'] == old_uname:
            l['username'] = new_uname

    return redirect(url_for('member_dashboard', msg="Account details updated successfully!"))

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