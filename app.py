import os
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_secret_key_123")

USERS = {
    "admin": {
        "password": "admin123",
        "email": "admin@sacco.com",
        "role": "Admin",
        "name": "System Administrator"
    }
}

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SACCO Management System - Login</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 100%; max-width: 380px; text-align: center; }
        .login-card h2 { margin-bottom: 20px; color: #1a365d; }
        .form-group { margin-bottom: 15px; text-align: left; }
        .form-group label { display: block; margin-bottom: 5px; font-size: 14px; color: #4a5568; }
        .form-group input { width: 100%; padding: 10px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; font-size: 14px; }
        .btn-submit { width: 100%; padding: 12px; background-color: #2b6cb0; color: #ffffff; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
        .btn-submit:hover { background-color: #2c5282; }
        .error-msg { color: #e53e3e; font-size: 14px; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>SACCO System Login</h2>
        {% if error %}
            <div class="error-msg">{{ error }}</div>
        {% endif %}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="identity">Username or Email</label>
                <input type="text" id="identity" name="identity" placeholder="Enter username or email" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter password" required>
            </div>
            <button type="submit" class="btn-submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SACCO Management - Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background-color: #f7fafc; color: #2d3748; }
        .navbar { background-color: #1a365d; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .navbar h1 { font-size: 20px; }
        .user-info { display: flex; align-items: center; gap: 15px; }
        .logout-btn { background-color: #e53e3e; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 14px; }
        .logout-btn:hover { background-color: #c53030; }
        .container { max-width: 1100px; margin: 40px auto; padding: 0 20px; }
        .welcome-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 30px; }
        .welcome-card h2 { color: #2b6cb0; margin-bottom: 8px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; border-left: 5px solid #2b6cb0; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .card h3 { font-size: 16px; color: #4a5568; margin-bottom: 10px; }
        .card .number { font-size: 28px; font-weight: bold; color: #1a365d; }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>SACCO Admin Dashboard</h1>
        <div class="user-info">
            <span>Logged in as: <strong>{{ user.name }}</strong> ({{ user.role }})</span>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
    </div>
    <div class="container">
        <div class="welcome-card">
            <h2>Welcome Back, {{ user.name }}</h2>
            <p>System Overview and SACCO Operations Module.</p>
        </div>
        <div class="grid">
            <div class="card">
                <h3>Total Members</h3>
                <div class="number">128</div>
            </div>
            <div class="card" style="border-left-color: #38a169;">
                <h3>Active Loans</h3>
                <div class="number">42</div>
            </div>
            <div class="card" style="border-left-color: #d69e2e;">
                <h3>Total Savings (KES)</h3>
                <div class="number">1,450,000</div>
            </div>
            <div class="card" style="border-left-color: #e53e3e;">
                <h3>Pending Approvals</h3>
                <div class="number">5</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity') if not request.is_json else request.get_json().get('identity')
        password = request.form.get('password') if not request.is_json else request.get_json().get('password')

        user_found = None
        for uname, details in USERS.items():
            if identity in (uname, details['email']):
                user_found = details
                break

        if user_found and user_found['password'] == password:
            session['user'] = user_found
            if request.is_json:
                return jsonify({"status": "success", "redirect": "/dashboard"}), 200
            return redirect(url_for('dashboard'))
        
        error_msg = "Invalid credentials. Try username: admin / password: admin123"
        if request.is_json:
            return jsonify({"status": "error", "message": error_msg}), 401
        return render_template_string(LOGIN_HTML, error=error_msg)

    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_HTML, user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)