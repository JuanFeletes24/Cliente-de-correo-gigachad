import sqlite3


def save(db, **overrides):
    values = {
        "protocol": "imap",
        "account": "user@example.test",
        "mailbox": "INBOX",
        "uid": "10",
        "uidvalidity": "777",
        "sender": "sender@example.test",
        "subject": "Subject",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "body": "Body",
        "is_read": False,
    }
    values.update(overrides)
    db.save_email(**values)


def test_save_filter_and_identity_rules(isolated_db):
    db = isolated_db
    save(db)
    save(db)
    save(db, mailbox="Archive")
    save(db, uidvalidity="888")
    save(db, protocol="pop", uid="pop-10", uidvalidity="")

    assert len(db.get_all_emails("user@example.test")) == 4
    assert len(db.get_all_emails("user@example.test", protocol="imap")) == 3
    assert len(db.get_all_emails(
        "user@example.test", protocol="imap", mailbox="INBOX"
    )) == 2
    assert len(db.get_all_emails(
        "user@example.test", protocol="pop", mailbox="INBOX"
    )) == 1


def test_mark_as_read_and_pop_resync_preserves_read(isolated_db):
    db = isolated_db
    save(db, protocol="pop", uid="uidl-1", uidvalidity="")

    db.mark_email_as_read(
        "pop", "user@example.test", "INBOX", "", "uidl-1"
    )
    save(db, protocol="pop", uid="uidl-1", uidvalidity="", is_read=False)

    message = db.get_all_emails(
        "user@example.test", protocol="pop", mailbox="INBOX"
    )[0]
    assert message["is_read"] is True


def test_contacts_survive_legacy_migration(monkeypatch, tmp_path):
    from modules import db

    database = tmp_path / "legacy.db"
    conn = sqlite3.connect(database)
    conn.executescript("""
        CREATE TABLE emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            account TEXT,
            sender TEXT,
            subject TEXT,
            date TEXT,
            body TEXT,
            is_new INTEGER DEFAULT 0,
            UNIQUE(uid, account)
        );
        CREATE TABLE contacts (
            email TEXT PRIMARY KEY,
            encryption_key TEXT
        );
        INSERT INTO contacts VALUES ('friend@example.test', 'key');
        INSERT INTO emails
            (uid, account, sender, subject, date, body, is_new)
        VALUES
            ('legacy-1', 'user@example.test', 'sender', 'old', '', 'body', 1);
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", database)
    db.init_db()

    assert db.get_contact_key("friend@example.test") == "key"
    message = db.get_all_emails("user@example.test")[0]
    assert message["protocol"] == "imap"
    assert message["mailbox"] == "INBOX"
    assert message["is_read"] is False
