import sqlite3
from pathlib import Path
import os

DB_PATH = Path(
    os.environ.get(
        "MAIL_DB_PATH",
        Path(__file__).parent / "local_mail.db",
    )
)


def get_connection():
    return sqlite3.connect(DB_PATH)


def _create_emails_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocol TEXT NOT NULL,
            account TEXT NOT NULL,
            mailbox TEXT NOT NULL,
            uid TEXT NOT NULL,
            uidvalidity TEXT NOT NULL DEFAULT '',
            sender TEXT,
            subject TEXT,
            date TEXT,
            body TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            UNIQUE(protocol, account, mailbox, uidvalidity, uid)
        )
    ''')


def _migrate_legacy_emails(cursor):
    columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(emails)").fetchall()
    }

    if not columns or "protocol" in columns:
        return

    cursor.execute("ALTER TABLE emails RENAME TO emails_legacy")
    _create_emails_table(cursor)
    cursor.execute('''
        INSERT OR IGNORE INTO emails (
            protocol, account, mailbox, uid, uidvalidity,
            sender, subject, date, body, is_read
        )
        SELECT
            'imap', account, 'INBOX', uid, '',
            sender, subject, date, body,
            CASE WHEN is_new = 1 THEN 0 ELSE 1 END
        FROM emails_legacy
    ''')
    cursor.execute("DROP TABLE emails_legacy")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    _create_emails_table(cursor)
    _migrate_legacy_emails(cursor)

    # Table for contacts keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            email TEXT PRIMARY KEY,
            encryption_key TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_email(
    uid,
    account,
    sender,
    subject,
    date,
    body,
    is_new=None,
    protocol="imap",
    mailbox="INBOX",
    uidvalidity="",
    is_read=None,
):
    if is_read is None:
        is_read = not bool(is_new) if is_new is not None else False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO emails (
                protocol, account, mailbox, uid, uidvalidity,
                sender, subject, date, body, is_read
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(protocol, account, mailbox, uidvalidity, uid)
            DO UPDATE SET
                sender = excluded.sender,
                subject = excluded.subject,
                date = excluded.date,
                body = excluded.body,
                is_read = CASE
                    WHEN emails.protocol = 'pop' AND emails.is_read = 1 THEN 1
                    ELSE excluded.is_read
                END
        ''', (
            protocol,
            account,
            mailbox,
            str(uid),
            str(uidvalidity or ""),
            sender,
            subject,
            date,
            body,
            int(bool(is_read)),
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving email: {e}")
    finally:
        conn.close()


def get_all_emails(account, protocol=None, mailbox=None):
    conn = get_connection()
    cursor = conn.cursor()
    filters = ["account = ?"]
    values = [account]

    if protocol is not None:
        filters.append("protocol = ?")
        values.append(protocol)

    if mailbox is not None:
        filters.append("mailbox = ?")
        values.append(mailbox)

    cursor.execute(f'''
        SELECT
            id, protocol, account, mailbox, uid, uidvalidity,
            sender, subject, date, body, is_read
        FROM emails
        WHERE {" AND ".join(filters)}
        ORDER BY id DESC
    ''', values)
    rows = cursor.fetchall()
    conn.close()

    emails = []
    for row in rows:
        emails.append({
            "id": row[0],
            "protocol": row[1],
            "account": row[2],
            "mailbox": row[3],
            "uid": row[4],
            "uidvalidity": row[5],
            "from": row[6],
            "subject": row[7],
            "date": row[8],
            "body": row[9],
            "is_read": bool(row[10]),
        })
    return emails


def mark_email_as_read(protocol, account, mailbox, uidvalidity, uid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE emails
        SET is_read = 1
        WHERE protocol = ?
          AND account = ?
          AND mailbox = ?
          AND uidvalidity = ?
          AND uid = ?
    ''', (
        protocol,
        account,
        mailbox,
        str(uidvalidity or ""),
        str(uid),
    ))
    conn.commit()
    conn.close()


def migrate_mailbox_identity(account, server_name, mailbox_identity):
    if server_name == mailbox_identity:
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE OR IGNORE emails
        SET mailbox = ?
        WHERE protocol = 'imap'
          AND account = ?
          AND mailbox = ?
    ''', (
        mailbox_identity,
        account,
        server_name,
    ))
    conn.commit()
    conn.close()


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
