import os
from flask import Flask, request, jsonify, render_template_string, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sacco_secret_key_123")

# Sample in-memory user store
# Accepts logins by username OR email
USERS = {
    "admin": {
        "password": "admin123",
        "email": "admin@sacco.com",
        "role": "Admin"
    }
}

# HTML Template for Login (Served directly by Flask to avoid cached static files)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SACCO Management System - Login</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f6f9;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .login-card {
            background: #ffffff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 380px;
            text-align: center;
        }
        .login-card h2 {
            margin-bottom: 20px;
            color: #1a365d;
        }
        .form-group {
            margin-bottom: 15px;
            text-align: left;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
            color: #4a5568;
        }
        .form-group input {
            width: 100%;
            padding: 10px;
            border: 1px solid #cbd5e0;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14px;
        }
        .btn-submit {
            width: 100%;
            padding: 12px;
            background-color: #2b6cb0;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
        }
        .btn-submit:hover {
            background-color: #2c5282;
        }
        .error-msg {
            color: #e53e3e;
            font-size: 14px;
            margin-bottom: 15px;
        }
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

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Accept JSON data or Form Data
        if request.is_json:
            data = request.get_json()
            identity = data.get('identity') or data.get('username') or data.get('email')
            password = data.get('password')
        else:
            identity = request.form.get('identity') or request.form.get('username') or request.form.get('email')
            password = request.form.get('password')

        # Check credentials against username or email
        user_found = None
        for uname, details in USERS.items():
            if identity in (uname, details['email']):
                user_found = details
                break

        if user_found and user_found['password'] == password:
            if request.is_json:
                return jsonify({"status": "success", "message": "Login successful"}), 200
            return f"<h2>Welcome to SACCO Dashboard! Logged in as: {user_found['role']}</h2>"
        
        error_message = "Invalid credentials. Try username: admin / password: admin123"
        if request.is_json:
            return jsonify({"status": "error", "message": error_message}), 401
        return render_template_string(LOGIN_HTML, error=error_message)

    return render_template_string(LOGIN_HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)