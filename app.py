import os
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_zero_start_secret_key")

# Database Configuration (Uses Render PostgreSQL if available, otherwise local SQLite)
db_url = os.environ.get("DATABASE_URL", "sqlite:///sacco.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Uploads Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Global Theme CSS Processor
THEME_CSS_CONTENT = """
<style>
:root { --bg: #f7fafc; --card: #ffffff; --text: #2d3748; --subtext: #4a5568; --border: #e2e8f0; --nav-bg: #2d3748; --nav-admin: #1a365d; --input-bg: #ffffff; }
[data-theme="dark"] { --bg: #1a202c; --card: #2d3748; --text: #f7fafc; --subtext: #a0aec0; --border: #4a5568; --nav-bg: #0f172a; --nav-admin: #0f172a; --input-bg: #4a5568; }
* { box-sizing: border-box; margin: 0; padding: 0; transition: background 0.2s, color 0.2s; }
body { font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }
.navbar { background: var(--nav-bg); color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
.navbar-admin { background: var(--nav-admin); }
.container { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
.card { background: var(--card); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
.bold { font-size: 28px; font-weight: bold; color: #18a169; margin: 5px 0; }
label { font-size: 12px; font-weight: bold; color: var(--subtext); display: block; margin-bottom: 4px; }
input, select { width: 100%; padding: 8px; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); border-radius: 4px; }
.btn { padding: 8px 15px; background: #2b6cb0; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
.btn-theme { background: transparent; border: 1px solid white; color: white; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text); }
th { background: var(--border); }
.avatar-img { width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); }
.avatar-placeholder { width: 45px; height: 45px; border-radius: 50%; background: #4a5568; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; }
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

# Database Models
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

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="Admin").first():
        admin = User(
            username="admin",
            name="SACCO Admin",
            email="admin@sacco.com",
            phone="0000000000",
            password=generate_password_hash("admin123"),
            role="Admin"
        )
        db.session.add(admin)
        db.session.commit()

# HTML Templates
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SACCO Portal - Login & Register</title>
    {{ theme_css | safe }}
</head>
<body style="display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0;">
<div class="card" style="width: 360px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2>SACCO Portal</h2>
        <button class="btn-theme" onclick="toggleTheme()" style="color:var(--text);">Theme</button>
    </div>
    {% if error %}<div class="msg"><strong>{{ error }}</strong></div>{% endif %}
    {% if success %}<div class="msg success"><strong>{{ success }}</strong></div>{% endif %}

    <div id="login-form">
        <form method="POST" action="/login">
            <div style="margin-bottom: 10px;">
                <label>Username or Email</label>
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
</div>

<script>
function toggleView(targetId) {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'none';
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
    <div class="navbar navbar-admin">
        <h2>SACCO Admin Control Center</h2>
        <div>
            Logged in as: <strong>{{ admin.username }}</strong>
            <button class="btn-theme" onclick="toggleTheme()">Theme</button>
            <a href="/logout" style="color: #feb2b2; margin-left: 10px;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="card">
            <h2>Registered Members (Total: {{ members|length }})</h2>
            <table>
                <thead>
                    <tr><th>Photo</th><th>Name</th><th>Username</th><th>Email</th><th>Action</th></tr>
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
                        <td><strong>{{ m.name }}</strong></td>
                        <td>{{ m.username }}</td>
                        <td>{{ m.email }}</td>
                        <td>
                            <a href="/admin/remove_member/{{ m.username }}" class="btn" style="background: #e53e3e; text-decoration: none;">Remove</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" style="text-align:center;">No members registered yet.</td></tr>
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
        <div style="display: flex; align-items: center; gap: 10px;">
            {% if member.avatar %}
            <img src="/uploads/{{ member.avatar }}" class="avatar-img">
            {% else %}
            <div class="avatar-placeholder">{{ member.name[0].upper() }}</div>
            {% endif %}
            <h2>SACCO Member Portal</h2>
        </div>
        <div>
            Logged in as: <strong>{{ member.name }} ({{ member.username }})</strong>
            <button class="btn-theme" onclick="toggleTheme()">Theme</button>
            <a href="/logout" style="color: #feb2b2; margin-left: 10px;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="card">
            <h2>Welcome back, {{ member.name }}!</h2>
            <p>Your account is active and safe.</p>
        </div>
    </div>
</body>
</html>
"""

# App Routes
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.role == "Admin":
            return redirect(url_for('admin_dashboard'))
        elif user:
            return redirect(url_for('member_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity', '').lower().strip()
        password = request.form.get('password', '')

        user = User.query.filter((User.username == identity) | (User.email == identity)).first()
        
        # Checks hashed password, or falls back to plain-text for legacy database entries
        if user and (check_password_hash(user.password, password) or user.password == password):
            session['user_id'] = user.id
            if user.role == "Admin":
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

    hashed_password = generate_password_hash(password)

    new_user = User(
        username=username,
        name=name,
        email=email,
        phone=phone,
        password=hashed_password,
        role="Member",
        avatar=avatar_filename
    )
    db.session.add(new_user)
    db.session.commit()

    return render_template_string(LOGIN_HTML, success="Registration successful! Please login below.")

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    admin = User.query.get(session['user_id'])
    if not admin or admin.role != "Admin":
        return redirect(url_for('login'))

    members = User.query.filter_by(role="Member").all()
    return render_template_string(ADMIN_DASHBOARD, admin=admin, members=members)

@app.route('/member/dashboard')
def member_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    member = User.query.get(session['user_id'])
    if not member or member.role != "Member":
        session.pop('user_id', None)
        return redirect(url_for('login'))

    return render_template_string(MEMBER_DASHBOARD, member=member)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)