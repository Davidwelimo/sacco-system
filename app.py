import os
import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_zero_start_secret_key")

# Setup Profile Picture Upload Folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

MEMBERS = {} # format: { username: { name, email, phone, balance, password, role="Member", avatar } }
LOANS = [] # { id, username, member_name, amount, purpose, duration, status }
PAYMENTS = [] # { id, username, member_name, amount, ref_code, status, date }
RESET_REQUESTS = [] # { id, username, member_name, phone, status, date }


# ==========================================
# BASE STYLES & JS (LIGHT/DARK MODE)
# ==========================================

THEME_CSS = """
<style>
    :root {
        --bg: #f7fafc;
        --card-bg: #ffffff;
        --text: #2d3748;
        --subtext: #4a5568;
        --border: #e2e8f0;
        --nav-bg: #2b6cb0;
        --nav-admin: #1a365d;
        --input-bg: #ffffff;
    }
    [data-theme="dark"] {
        --bg: #1a202c;
        --card-bg: #2d3748;
        --text: #f7fafc;
        --subtext: #cbd5e0;
        --border: #4a5568;
        --nav-bg: #1a202c;
        --nav-admin: #0d1726;
        --input-bg: #4a5568;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; transition: background 0.2s, color 0.2s; }
    body { font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }
    .navbar { background: var(--nav-bg); color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
    .admin-nav { background: var(--nav-admin); }
    .container { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
    .card { background: var(--card-bg); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; border: 1px solid var(--border); }
    h2 { margin-bottom: 15px; font-size: 18px; color: var(--text); }
    .bal { font-size: 32px; font-weight: bold; color: #38a169; margin: 10px 0; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    label { font-size: 12px; font-weight: bold; color: var(--subtext); display: block; margin-bottom: 4px; }
    input { width: 100%; padding: 8px; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); border-radius: 6px; box-sizing: border-box; }
    .btn { padding: 8px 15px; background: #2b6cb0; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 12px; }
    .btn-theme { background: transparent; border: 1px solid white; color: white; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 11px; margin-left: 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text); }
    th { background: var(--border); }
    .badge { padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-Pending { background: #feebc8; color: #c05621; }
    .badge-Confirmed, .badge-Approved, .badge-Resolved { background: #c6f6d5; color: #22543d; }
    .badge-Rejected { background: #fed7d7; color: #9b2c2c; }
    .avatar-img { width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); vertical-align: middle; margin-right: 8px; }
    .avatar-placeholder { width: 45px; height: 45px; border-radius: 50%; background: #a0aec0; color: white; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; vertical-align: middle; margin-right: 8px; }
    .msg { color: #e53e3e; font-size: 13px; margin-bottom: 10px; }
    .success { color: #38a169; }
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
    }
</script>
"""

# ==========================================
# HTML TEMPLATES
# ==========================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SACCO Portal - Login & Register</title>
    """ + THEME_CSS + """
    <style>
        body { display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .box { width: 360px; }
        .tab-btn { background: none; border: none; color: #2b6cb0; cursor: pointer; text-decoration: underline; font-size: 13px; margin-top: 12px; width: 100%; text-align: center; }
    </style>
</head>
<body>
    <div class="box card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2>SACCO Portal</h2>
            <button class="btn-theme" onclick="toggleTheme()" style="color:var(--text); border-color:var(--border);">🌓 Mode</button>
        </div>
        {% if error %}<div class="msg">{{ error }}</div>{% endif %}
        {% if success %}<div class="msg success">{{ success }}</div>{% endif %}

        <div id="login-form">
            <form method="POST" action="/login">
                <div style="margin-bottom:10px;">
                    <label>Username / Email</label>
                    <input type="text" name="identity" required>
                </div>
                <div style="margin-bottom:10px;">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn" style="width:100%;">Login</button>
            </form>
            <button class="tab-btn" onclick="toggleView('register-form')">New Member? Register Here</button>
            <button class="tab-btn" onclick="toggleView('forgot-form')" style="color:#e53e3e;">Forgot Password?</button>
        </div>

        <div id="register-form" style="display:none;">
            <form method="POST" action="/register" enctype="multipart/form-data">
                <div style="margin-bottom:10px;">
                    <label>Full Name</label>
                    <input type="text" name="name" required>
                </div>
                <div style="margin-bottom:10px;">
                    <label>Username</label>
                    <input type="text" name="username" required>
                </div>
                <div style="margin-bottom:10px;">
                    <label>Email</label>
                    <input type="email" name="email" required>
                </div>
                <div style="margin-bottom:10px;">
                    <label>Phone Number</label>
                    <input type="text" name="phone" placeholder="0712345678" required>
                </div>
                <div style="margin-bottom:10px;">
                    <label>Profile Picture (Optional)</label>
                    <input type="file" name="avatar" accept="image/*">
                </div>
                <div style="margin-bottom:10px;">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn" style="width:100%; background:#38a169;">Create Account</button>
            </form>
            <button class="tab-btn" onclick="toggleView('login-form')">Already registered? Login</button>
        </div>

        <div id="forgot-form" style="display:none;">
            <p style="font-size:12px; color:var(--subtext); margin-bottom:10px;">Enter your username or phone. The Admin will reset your password.</p>
            <form method="POST" action="/request_reset">
                <div style="margin-bottom:10px;">
                    <label>Username or Phone Number</label>
                    <input type="text" name="identity" required>
                </div>
                <button type="submit" class="btn" style="width:100%; background:#dd6b20;">Request Reset</button>
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
    """ + THEME_CSS + """
</head>
<body>
    <div class="navbar admin-nav">
        <h2>SACCO Admin Control Center</h2>
        <div>
            Logged in as: <strong>{{ admin.username }}</strong> 
            <button class="btn-theme" onclick="toggleTheme()">🌓 Theme</button>
            | <a href="/logout" style="color: #feb2b2;">Logout</a>
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
                <button type="submit" class="btn">Update Credentials</button>
            </form>
        </div>

        <div class="card">
            <h2>2. Password Reset Requests</h2>
            <table>
                <thead>
                    <tr><th>ID</th><th>Member</th><th>Phone</th><th>Date</th><th>Status</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {% for r in reset_requests %}
                    <tr>
                        <td>#{{ r.id }}</td>
                        <td>{{ r.member_name }} ({{ r.username }})</td>
                        <td>{{ r.phone }}</td>
                        <td>{{ r.date }}</td>
                        <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
                        <td>
                            {% if r.status == 'Pending' %}
                            <form method="POST" action="/admin/resolve_reset/{{ r.id }}" style="display:flex; gap:5px;">
                                <input type="text" name="new_password" placeholder="Set new pass" required style="padding:4px; font-size:11px; width:110px;">
                                <button type="submit" class="btn" style="background:#dd6b20; margin-top:0;">Reset</button>
                            </form>
                            {% else %}
                            <span style="color:var(--subtext); font-size:11px;">Resolved</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="6" style="text-align:center;">No reset requests pending.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>3. Registered Members (Total: {{ members|length }})</h2>
            <table>
                <thead>
                    <tr><th>Photo</th><th>Username</th><th>Name</th><th>Email</th><th>Savings</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {% for uname, m in members.items() %}
                    <tr>
                        <td>
                            {% if m.avatar %}
                            <img src="/uploads/{{ m.avatar }}" class="avatar-img">
                            {% else %}
                            <div class="avatar-placeholder">{{ m.name[0].upper() }}</div>
                            {% endif %}
                        </td>
                        <td><strong>{{ uname }}</strong></td>
                        <td>{{ m.name }}</td>
                        <td>{{ m.email }}</td>
                        <td style="color:#38a169; font-weight:bold;">KES {{ "{:,}".format(m.balance) }}</td>
                        <td>
                            <a href="/admin/remove_member/{{ uname }}" class="btn" style="background:#e53e3e; text-decoration:none;" onclick="return confirm('Remove member {{ uname }}?');">Remove</a>
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
                    <tr><th>ID</th><th>Member</th><th>Amount</th><th>Ref Code</th><th>Status</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {% for p in payments %}
                    <tr>
                        <td>#{{ p.id }}</td>
                        <td>{{ p.member_name }} ({{ p.username }})</td>
                        <td><strong>KES {{ "{:,}".format(p.amount) }}</strong></td>
                        <td><code>{{ p.ref_code }}</code></td>
                        <td><span class="badge badge-{{ p.status }}">{{ p.status }}</span></td>
                        <td>
                            {% if p.status == 'Pending' %}
                                <a href="/admin/confirm_payment/{{ p.id }}" class="btn" style="background:#38a169; text-decoration:none;">Confirm</a>
                                <a href="/admin/reject_payment/{{ p.id }}" class="btn" style="background:#e53e3e; text-decoration:none;">Reject</a>
                            {% else %}
                                <span style="color:var(--subtext); font-size:11px;">Processed</span>
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
            <h2>5. Member Loan Applications</h2>
            <table>
                <thead>
                    <tr><th>ID</th><th>Member</th><th>Amount</th><th>Purpose</th><th>Duration</th><th>Status</th><th>Action</th></tr>
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
                                <a href="/admin/approve_loan/{{ l.id }}" class="btn" style="background:#38a169; text-decoration:none;">Approve</a>
                                <a href="/admin/reject_loan/{{ l.id }}" class="btn" style="background:#e53e3e; text-decoration:none;">Reject</a>
                            {% else %}
                                <span style="color:var(--subtext); font-size:11px;">Completed</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="7" style="text-align:center;">No loan requests yet.</td></tr>
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
    """ + THEME_CSS + """
</head>
<body>
    <div class="navbar">
        <div style="display:flex; align-items:center;">
            {% if member.avatar %}
            <img src="/uploads/{{ member.avatar }}" class="avatar-img">
            {% else %}
            <div class="avatar-placeholder">{{ member.name[0].upper() }}</div>
            {% endif %}
            <h2>SACCO Member Portal</h2>
        </div>
        <div>
            Logged in as: <strong>{{ member.name }}</strong> ({{ member.username }})
            <button class="btn-theme" onclick="toggleTheme()">🌓 Theme</button>
            | <a href="/logout" style="color: #e2e8f0;">Logout</a>
        </div>
    </div>
    <div class="container">
        
        {% if msg %}<div class="card msg success"><strong>{{ msg }}</strong></div>{% endif %}
        {% if err %}<div class="card msg"><strong>{{ err }}</strong></div>{% endif %}

        <div class="card">
            <h2>Your SACCO Savings Balance</h2>
            <div class="bal">KES {{ "{:,}".format(member.balance) }}</div>
        </div>

        <!-- PROFILE & AVATAR UPDATE SECTION -->
        <div class="card">
            <h2>Profile & Settings</h2>
            <form method="POST" action="/member/update_profile" enctype="multipart/form-data">
                <div class="form-grid">
                    <div>
                        <label>Your Username</label>
                        <input type="text" name="new_username" value="{{ member.username }}" required>
                    </div>
                    <div>
                        <label>New Password (Optional)</label>
                        <input type="password" name="new_password" placeholder="Leave blank to keep current">
                    </div>
                    <div>
                        <label>Change Profile Picture</label>
                        <input type="file" name="avatar" accept="image/*">
                    </div>
                </div>
                <button type="submit" class="btn">Save Profile Changes</button>
            </form>
        </div>

        <div class="card">
            <h2>Report Payment / Deposit</h2>
            <form method="POST" action="/member/notify_payment">
                <div class="form-grid">
                    <div>
                        <label>Amount Sent (KES)</label>
                        <input type="number" name="amount" placeholder="e.g. 5000" required>
                    </div>
                    <div>
                        <label>M-Pesa Ref / Receipt Code</label>
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
                        <label>Duration (Months)</label>
                        <input type="number" name="duration" placeholder="6" required>
                    </div>
                </div>
                <button type="submit" class="btn" style="background:#38a169;">Submit Loan Application</button>
            </form>
        </div>

        <div class="card">
            <h2>Your Payment History</h2>
            <table>
                <thead>
                    <tr><th>Ref Code</th><th>Amount</th><th>Date</th><th>Status</th></tr>
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
                    <tr><td colspan="4" style="text-align:center;">No payments reported yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

    </div>
</body>
</html>
"""

# ==========================================
# ROUTES & FILE SERVING
# ==========================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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

        if identity in (ADMIN_PROFILE['username'].lower(), ADMIN_PROFILE['email'].lower()) and ADMIN_PROFILE['password'] == password:
            session['user'] = ADMIN_PROFILE
            return redirect(url_for('admin_dashboard'))

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

    avatar_filename = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{username}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            avatar_filename = filename

    MEMBERS[username] = {
        "username": username,
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "balance": 0,
        "role": "Member",
        "avatar": avatar_filename
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
        return render_template_string(LOGIN_HTML, success="Reset request sent to Admin. Contact Admin to approve.")
    
    return render_template_string(LOGIN_HTML, error="No account found matching that username or phone.")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))
    return render_template_string(ADMIN_DASHBOARD, admin=ADMIN_PROFILE, members=MEMBERS, payments=PAYMENTS, loans=LOANS, reset_requests=RESET_REQUESTS, msg=request.args.get('msg'), err=request.args.get('err'))

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
            return redirect(url_for('admin_dashboard', msg=f"Password for '{uname}' updated to '{new_password}'."))

    return redirect(url_for('admin_dashboard', err="Request not found."))

@app.route('/admin/remove_member/<username>')
def remove_member(username):
    if 'user' not in session or session['user']['role'] != 'Admin':
        return redirect(url_for('login'))

    if username in MEMBERS:
        del MEMBERS[username]
        return redirect(url_for('admin_dashboard', msg=f"Member '{username}' removed."))

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
    return render_template_string(MEMBER_DASHBOARD, member=current_member, user_payments=user_payments, msg=request.args.get('msg'), err=request.args.get('err'))

@app.route('/member/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    old_uname = session['user']['username']
    new_uname = request.form.get('new_username').lower().strip()
    new_password = request.form.get('new_password')

    if old_uname not in MEMBERS:
        return redirect(url_for('login'))

    if new_uname != old_uname and (new_uname in MEMBERS or new_uname == ADMIN_PROFILE['username'].lower()):
        return redirect(url_for('member_dashboard', err="That username is already taken!"))

    member_data = MEMBERS.pop(old_uname)
    member_data['username'] = new_uname
    if new_password:
        member_data['password'] = new_password

    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{new_uname}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            member_data['avatar'] = filename

    MEMBERS[new_uname] = member_data
    session['user'] = member_data

    for p in PAYMENTS:
        if p['username'] == old_uname:
            p['username'] = new_uname
    for l in LOANS:
        if l['username'] == old_uname:
            l['username'] = new_uname

    return redirect(url_for('member_dashboard', msg="Profile updated successfully!"))

@app.route('/member/notify_payment', methods=['POST'])
def notify_payment():
    if 'user' not in session or session['user']['role'] != 'Member':
        return redirect(url_for('login'))

    uname = session['user']['username']
    amount = int(request.form.get('amount', 0))
    ref_code = request.form.get('ref_code')

    PAYMENTS.append({
        "id": len(PAYMENTS) + 1,
        "username": uname,
        "member_name": session['user']['name'],
        "amount": amount,
        "ref_code": ref_code,
        "status": "Pending",
        "date": datetime.date.today().strftime('%Y-%m-%d')
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