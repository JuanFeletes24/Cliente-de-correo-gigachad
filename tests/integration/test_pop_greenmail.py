import poplib
import smtplib
import ssl
import uuid
from email.message import EmailMessage

import pytest


pytestmark = pytest.mark.integration
REAL_POP_SSL = poplib.POP3_SSL


def send_message(subject):
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "user@example.test"
    message["Subject"] = subject
    message.set_content("GreenMail POP body")
    with smtplib.SMTP("127.0.0.1", 3025) as smtp:
        smtp.send_message(message)


def server_uidls():
    mail = REAL_POP_SSL(
        "127.0.0.1", 3995, context=ssl._create_unverified_context()
    )
    mail.user("user@example.test")
    mail.pass_("secret")
    uidls = {line.split(maxsplit=1)[1] for line in mail.uidl()[1]}
    mail.quit()
    return uidls


def test_pop_retr_uidl_quit_and_server_preservation(
    monkeypatch, mail_config, isolated_db
):
    monkeypatch.setitem(mail_config.config["auth"], "user", "user@example.test")
    monkeypatch.setitem(mail_config.config["auth"], "password", "secret")
    monkeypatch.setitem(mail_config.config["pop"], "server", "127.0.0.1")
    monkeypatch.setitem(mail_config.config["pop"], "port", "3995")
    monkeypatch.setattr(
        mail_config.poplib,
        "POP3_SSL",
        lambda server, port: REAL_POP_SSL(
            server, port, context=ssl._create_unverified_context()
        ),
    )
    subject = f"pop-{uuid.uuid4()}"
    send_message(subject)
    before = server_uidls()

    first = mail_config.PopEmail()
    first.get_mails(n_emails=50)
    messages = [
        message for message in isolated_db.get_all_emails(
            first.USER, protocol="pop", mailbox="INBOX"
        )
        if message["subject"] == subject
    ]
    assert len(messages) == 1
    assert messages[0]["uid"].encode() in before

    isolated_db.mark_email_as_read(
        "pop", first.USER, "INBOX", "", messages[0]["uid"]
    )
    mail_config.PopEmail().get_mails(n_emails=50)

    after = server_uidls()
    assert before <= after
    refreshed = isolated_db.get_all_emails(
        first.USER, protocol="pop", mailbox="INBOX"
    )
    selected = next(item for item in refreshed if item["subject"] == subject)
    assert selected["is_read"] is True
