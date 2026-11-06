import sqlite3

def init_db():
    # Connects to database (creates it if it doesn't exist)
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # 1. Users Table (Stores login details & roles)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # 2. Members Table (Stores SACCO member details)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Transactions Table (Stores deposits with timestamps & who recorded them)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            tx_type TEXT NOT NULL,
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            recorded_by TEXT NOT NULL,
            FOREIGN KEY (member_id) REFERENCES members (member_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and tables created successfully!")

if __name__ == '__main__':
    init_db()