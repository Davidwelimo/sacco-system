from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'sacco_secret_key_change_in_production'

def get_db_connection():
    conn = sqlite3.connect('sacco.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# 1. Main Dashboard with System Totals
@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    members = conn.execute('SELECT * FROM members').fetchall()
    
    # Calculate Total SACCO Deposits automatically
    total_funds = conn.execute('SELECT SUM(amount) FROM transactions').fetchone()[0] or 0.0
    conn.close()
    
    return render_template_string('''
        <h2>SACCO Main Dashboard</h2>
        <p>Logged in as: <strong>{{ session['username'] }}</strong> (Role: {{ session['role'] }}) | <a href="/logout">Logout</a></p>
        
        <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; width: 300px;">
            <h3>Total Vault Savings: KSH {{ "%.2f"|format(total_funds) }}</h3>
        </div>
        <hr>
        
        <h3>Actions</h3>
        <ul>
            <li><a href="/add_member">Register New Member</a></li>
            <li><a href="/add_transaction">Record Money Deposit</a></li>
        </ul>
        <hr>
        
        <h3>Registered Members & Statement Access</h3>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr style="background-color: #ddd;">
                <th>ID</th><th>Full Name</th><th>Phone</th><th>Date Joined</th><th>Action</th>
            </tr>
            {% for member in members %}
            <tr>
                <td>{{ member['member_id'] }}</td>
                <td>{{ member['full_name'] }}</td>
                <td>{{ member['phone'] }}</td>
                <td>{{ member['date_joined'] }}</td>
                <td><a href="/statement/{{ member['member_id'] }}">View Statement</a></td>
            </tr>
            {% endfor %}
        </table>
    ''', members=members, total_funds=total_funds)

# 2. Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                            (username, password)).fetchone()
        conn.close()

        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials! <a href='/login'>Try again</a>"

    return '''
        <h2>SACCO System Login</h2>
        <form method="post">
            Username: <input type="text" name="username" required><br><br>
            Password: <input type="password" name="password" required><br><br>
            <input type="submit" value="Login">
        </form>
    '''

# 3. Register Member
@app.route('/add_member', methods=['GET', 'POST'])
@login_required
def add_member():
    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone']

        conn = get_db_connection()
        conn.execute('INSERT INTO members (full_name, phone) VALUES (?, ?)', (full_name, phone))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return '''
        <h2>Register New Member</h2>
        <form method="post">
            Full Name: <input type="text" name="full_name" required><br><br>
            Phone Number: <input type="text" name="phone"><br><br>
            <input type="submit" value="Save Member">
        </form>
        <br><a href="/">Back to Dashboard</a>
    '''

# 4. Record Deposit Transaction
@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    conn = get_db_connection()
    members = conn.execute('SELECT * FROM members').fetchall()

    if request.method == 'POST':
        member_id = request.form['member_id']
        amount = request.form['amount']
        tx_type = request.form['tx_type']
        recorded_by = session['username']

        conn.execute('''
            INSERT INTO transactions (member_id, amount, tx_type, recorded_by)
            VALUES (?, ?, ?, ?)
        ''', (member_id, amount, tx_type, recorded_by))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template_string('''
        <h2>Record Money Deposit</h2>
        <form method="post">
            Select Member: 
            <select name="member_id" required>
                {% for member in members %}
                    <option value="{{ member['member_id'] }}">{{ member['full_name'] }} (ID: {{ member['member_id'] }})</option>
                {% endfor %}
            </select><br><br>
            
            Amount (KSH): <input type="number" step="0.01" name="amount" required><br><br>
            
            Type: 
            <select name="tx_type">
                <option value="Savings Deposit">Savings Deposit</option>
                <option value="Shares Contribution">Shares Contribution</option>
                <option value="Registration Fee">Registration Fee</option>
            </select><br><br>
            
            <input type="submit" value="Record Transaction">
        </form>
        <br><a href="/">Back to Dashboard</a>
    ''', members=members)

# 5. Automated Member Statement & Calculations
@app.route('/statement/<int:member_id>')
@login_required
def statement(member_id):
    conn = get_db_connection()
    member = conn.execute('SELECT * FROM members WHERE member_id = ?', (member_id,)).fetchone()
    transactions = conn.execute('SELECT * FROM transactions WHERE member_id = ? ORDER BY date_recorded DESC', (member_id,)).fetchall()
    
    # Calculate automated total for this specific member
    total_savings = conn.execute('SELECT SUM(amount) FROM transactions WHERE member_id = ?', (member_id,)).fetchone()[0] or 0.0
    conn.close()

    return render_template_string('''
        <h2>Member Account Statement</h2>
        <p><strong>Member Name:</strong> {{ member['full_name'] }}</p>
        <p><strong>Member ID:</strong> {{ member['member_id'] }}</p>
        <p><strong>Total Accumulated Savings:</strong> KSH {{ "%.2f"|format(total_savings) }}</p>
        <hr>
        
        <h3>Transaction History Log</h3>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr style="background-color: #ddd;">
                <th>Tx ID</th><th>Type</th><th>Amount (KSH)</th><th>Date & Time Stamp</th><th>Recorded By</th>
            </tr>
            {% for tx in transactions %}
            <tr>
                <td>{{ tx['tx_id'] }}</td>
                <td>{{ tx['tx_type'] }}</td>
                <td>{{ "%.2f"|format(tx['amount']) }}</td>
                <td>{{ tx['date_recorded'] }}</td>
                <td>{{ tx['recorded_by'] }}</td>
            </tr>
            {% endfor %}
        </table>
        <br><a href="/">Back to Dashboard</a>
    ''', member=member, transactions=transactions, total_savings=total_savings)

# 6. Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)