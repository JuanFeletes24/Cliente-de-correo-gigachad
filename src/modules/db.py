import sqlite3
from pathlib import Path
import os

DB_PATH = Path(__file__).parent / "local_mail.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Table for emails
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            account TEXT,
            sender TEXT,
            subject TEXT,
            date TEXT,
            body TEXT,
            is_new INTEGER DEFAULT 0,
            UNIQUE(uid, account)
        )
    ''')
    # Table for contacts keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            email TEXT PRIMARY KEY,
            encryption_key TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_email(uid, account, sender, subject, date, body, is_new=0):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO emails (uid, account, sender, subject, date, body, is_new)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (uid, account, sender, subject, date, body, is_new))
        conn.commit()
    except Exception as e:
        print(f"Error saving email: {e}")
    finally:
        conn.close()

def get_all_emails(account):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, uid, account, sender, subject, date, body, is_new 
        FROM emails 
        WHERE account = ?
        ORDER BY id DESC
    ''', (account,))
    rows = cursor.fetchall()
    conn.close()
    
    emails = []
    for row in rows:
        emails.append({
            "id": row[0],
            "uid": row[1],
            "account": row[2],
            "from": row[3],
            "subject": row[4],
            "date": row[5],
            "body": row[6],
            "is_new": bool(row[7])
        })
    return emails

def get_contact_key(email_address):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT encryption_key FROM contacts WHERE email = ?', (email_address,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_contact_key(email_address, key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contacts (email, encryption_key)
        VALUES (?, ?)
        ON CONFLICT(email) DO UPDATE SET encryption_key=excluded.encryption_key
    ''', (email_address, key))
    conn.commit()
    conn.close()

def get_all_contacts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT email, encryption_key FROM contacts')
    rows = cursor.fetchall()
    conn.close()
    return [{"email": r[0], "key": r[1]} for r in rows]

# Initialize db when module is loaded
init_db()
