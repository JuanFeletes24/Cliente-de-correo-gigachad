import imaplib
import smtplib
import ssl
import uuid
from email.message import EmailMessage

import pytest


pytestmark = pytest.mark.integration
REAL_IMAP_SSL = imaplib.IMAP4_SSL


def configure(mail_config, monkeypatch):
    values = {
        "auth": {"user": "user@example.test", "password": "secret"},
        "imap": {"server": "127.0.0.1", "port": "3993"},
        "app": {"days": "14"},
    }
    for section, options in values.items():
        for key, value in options.items():
            monkeypatch.setitem(mail_config.config[section], key, value)


def send_message(subject):
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "user@example.test"
    message["Subject"] = subject
    message.set_content("GreenMail integration body")
    with smtplib.SMTP("127.0.0.1", 3025) as smtp:
        smtp.send_message(message)


def imap_connection():
    context = ssl._create_unverified_context()
    mail = REAL_IMAP_SSL("127.0.0.1", 3993, ssl_context=context)
    mail.login("user@example.test", "secret")
    return mail


def test_imap_download_uid_seen_and_no_duplicates(
    monkeypatch, mail_config, isolated_db
):
    configure(mail_config, monkeypatch)
    monkeypatch.setattr(
        mail_config.imaplib,
        "IMAP4_SSL",
        lambda server, port: REAL_IMAP_SSL(
            server, port, ssl_context=ssl._create_unverified_context()
        ),
    )
    subject = f"imap-{uuid.uuid4()}"
    send_message(subject)

    client = mail_config.ImapEmail()
    client.get_emails(n_emails=50)
    client.get_emails(n_emails=50)
    messages = [
        message for message in isolated_db.get_all_emails(
            client.USER, protocol="imap", mailbox="INBOX"
        )
        if message["subject"] == subject
    ]

    assert len(messages) == 1
    message = messages[0]
    assert message["uid"].isdigit()
    assert message["uidvalidity"]
    assert message["is_read"] is False

    direct = imap_connection()
    direct.select("INBOX")
    status, unseen = direct.uid("SEARCH", None, f"UID {message['uid']} UNSEEN")
    assert status == "OK" and message["uid"].encode() in unseen[0].split()
    direct.logout()

    assert client.mark_as_read(
        message["mailbox"], message["uid"], message["uidvalidity"]
    )
    direct = imap_connection()
    direct.select("INBOX")
    status, seen = direct.uid("SEARCH", None, f"UID {message['uid']} SEEN")
    assert status == "OK" and message["uid"].encode() in seen[0].split()
    direct.logout()


def test_imap_mailboxes_do_not_mix(
    monkeypatch, mail_config, isolated_db
):
    configure(mail_config, monkeypatch)
    monkeypatch.setattr(
        mail_config.imaplib,
        "IMAP4_SSL",
        lambda server, port: REAL_IMAP_SSL(
            server, port, ssl_context=ssl._create_unverified_context()
        ),
    )
    subject = f"mailboxes-{uuid.uuid4()}"
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "user@example.test"
    message["Subject"] = subject
    message.set_content("Stored in two mailboxes")

    direct = imap_connection()
    direct.create("Archive")
    direct.append("INBOX", None, None, message.as_bytes())
    direct.append("Archive", None, None, message.as_bytes())
    direct.logout()

    client = mail_config.ImapEmail()
    assert any(item["name"] == "Archive" for item in client.get_mailboxes())
    client.get_emails(mailbox="INBOX", n_emails=50)
    client.get_emails(mailbox="Archive", n_emails=50)

    inbox_messages = isolated_db.get_all_emails(
        client.USER, protocol="imap", mailbox="INBOX"
    )
    archive_messages = isolated_db.get_all_emails(
        client.USER, protocol="imap", mailbox="Archive"
    )
    assert sum(item["subject"] == subject for item in inbox_messages) == 1
    assert sum(item["subject"] == subject for item in archive_messages) == 1
