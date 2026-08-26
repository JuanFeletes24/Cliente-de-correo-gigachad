from datetime import datetime
from email.message import EmailMessage


def raw_message(subject, date="Mon, 15 Jan 2024 10:00:00 +0000", message_id=None):
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "user@example.test"
    message["Subject"] = subject
    if date:
        message["Date"] = date
    if message_id:
        message["Message-ID"] = message_id
    message.set_content("Body")
    return message.as_bytes().splitlines()


class FakePOP:
    instances = []
    uidl_supported = True
    auth_error = False

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.calls = []
        self.closed = False
        self.messages = [
            raw_message("Old", "Mon, 1 Jan 2020 10:00:00 +0000", "<old>"),
            raw_message("One", message_id="<one>"),
            raw_message("Bad date", "not-a-date", "<bad>"),
        ]
        self.__class__.instances.append(self)

    def user(self, user):
        self.calls.append(("user", user))

    def pass_(self, password):
        self.calls.append(("pass", password))
        if self.auth_error:
            raise RuntimeError("authentication failed")

    def list(self):
        self.calls.append(("list",))
        return b"+OK", [b"1 100", b"2 100", b"3 100"], 300

    def uidl(self):
        self.calls.append(("uidl",))
        if not self.uidl_supported:
            raise RuntimeError("UIDL unsupported")
        return b"+OK", [b"1 uidl-old", b"2 uidl-one", b"3 uidl-bad"], 30

    def retr(self, number):
        self.calls.append(("retr", number))
        return b"+OK", self.messages[number - 1], 100

    def dele(self, *args):
        raise AssertionError("POP client must never issue DELE")

    def quit(self):
        self.calls.append(("quit",))
        self.closed = True


class FixedDateTime:
    @classmethod
    def now(cls):
        return datetime(2024, 1, 15)


def configure(monkeypatch, mail_config, isolated_db):
    FakePOP.instances.clear()
    FakePOP.uidl_supported = True
    FakePOP.auth_error = False
    monkeypatch.setattr(mail_config.poplib, "POP3_SSL", FakePOP)
    monkeypatch.setattr(mail_config, "datetime", FixedDateTime)
    return mail_config.PopEmail()


def test_pop_uses_uidl_retr_limit_and_quit(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_mails(n_emails=2)
    instance = FakePOP.instances[-1]

    assert (instance.server, instance.port) == ("pop.example.test", 1995)
    assert ("user", "user@example.test") in instance.calls
    assert ("pass", "secret") in instance.calls
    assert ("uidl",) in instance.calls
    assert [call for call in instance.calls if call[0] == "retr"] == [
        ("retr", 2), ("retr", 3)
    ]
    assert instance.closed
    assert {m["uid"] for m in isolated_db.get_all_emails(client.USER)} == {
        "uidl-one", "uidl-bad"
    }


def test_pop_uidl_fallback_to_message_id(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    FakePOP.uidl_supported = False
    client.get_mails(n_emails=1)
    assert isolated_db.get_all_emails(client.USER)[0]["uid"] == "<bad>"
    assert FakePOP.instances[-1].closed


def test_pop_filters_old_mail_and_new_mail_is_unread(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_mails(n_emails=3)
    messages = isolated_db.get_all_emails(client.USER)
    assert {message["subject"] for message in messages} == {"One", "Bad date"}
    assert all(message["is_read"] is False for message in messages)


def test_pop_resync_preserves_local_read_state(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_mails(n_emails=1)
    isolated_db.mark_email_as_read(
        "pop", client.USER, "INBOX", "", "uidl-bad"
    )
    configure(monkeypatch, mail_config, isolated_db).get_mails(n_emails=1)
    assert isolated_db.get_all_emails(client.USER)[0]["is_read"] is True


def test_pop_never_deletes_messages(monkeypatch, mail_config, isolated_db):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_mails(n_emails=3)
    assert not any(call[0] == "dele" for call in FakePOP.instances[-1].calls)
    assert FakePOP.instances[-1].closed


def test_auth_error_still_quits(monkeypatch, mail_config, isolated_db):
    FakePOP.instances.clear()
    FakePOP.auth_error = True
    monkeypatch.setattr(mail_config.poplib, "POP3_SSL", FakePOP)
    client = mail_config.PopEmail()
    assert client.mail is None
    assert FakePOP.instances[-1].closed
