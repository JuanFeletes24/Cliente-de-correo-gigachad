from email.message import EmailMessage


def raw_message(subject="Hello"):
    message = EmailMessage()
    message["From"] = "sender@example.test"
    message["To"] = "user@example.test"
    message["Subject"] = subject
    message["Date"] = "Mon, 1 Jan 2024 10:00:00 +0000"
    message.set_content("Body")
    return message.as_bytes()


class FakeIMAP:
    instances = []
    fail_fetch = False

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.calls = []
        self.logged_out = False
        self.__class__.instances.append(self)

    def login(self, user, password):
        self.calls.append(("login", user, password))
        return "OK", [b""]

    def list(self):
        self.calls.append(("list",))
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasChildren \\Noselect) "/" "[Provider]"',
            b'(\\HasNoChildren \\Sent) "/" "Sent Items"',
            b'(\\HasNoChildren \\Important) "/" "Important"',
            b'(\\Flagged \\HasNoChildren) "/" "Starred"',
            b'(\\HasNoChildren) "/" "Projects"',
        ]

    def select(self, mailbox):
        self.calls.append(("select", mailbox))
        return "OK", [b"2"]

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"777"]

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b"41 42"]
        if command == "FETCH":
            if self.fail_fetch:
                raise RuntimeError("fetch failed")
            uid = args[0]
            flags = b"\\Seen" if uid == b"42" else b""
            header = b"1 (UID " + uid + b" FLAGS (" + flags + b") BODY[] {100}"
            return "OK", [(header, raw_message(uid.decode())), b")"]
        if command == "STORE":
            return "OK", [b""]
        raise AssertionError(command)

    def logout(self):
        self.logged_out = True
        self.calls.append(("logout",))


def configure(monkeypatch, mail_config, isolated_db):
    FakeIMAP.instances.clear()
    FakeIMAP.fail_fetch = False
    monkeypatch.setattr(mail_config.imaplib, "IMAP4_SSL", FakeIMAP)
    monkeypatch.setattr(mail_config, "datetime", FixedDateTime)
    return mail_config.ImapEmail()


class FixedDateTime:
    @classmethod
    def now(cls):
        from datetime import datetime

        return datetime(2024, 1, 15)


def test_list_mailboxes_and_connection(monkeypatch, mail_config, isolated_db):
    client = configure(monkeypatch, mail_config, isolated_db)
    mailboxes = client.get_mailboxes()
    instance = FakeIMAP.instances[-1]

    assert (instance.server, instance.port) == ("imap.example.test", 1993)
    assert ("login", "user@example.test", "secret") in instance.calls
    assert mailboxes == [
        {"name": "INBOX", "special_use": None, "identity": "INBOX"},
        {"name": "Sent Items", "special_use": "\\Sent", "identity": "\\Sent"},
        {"name": "Important", "special_use": "\\Important", "identity": "\\Important"},
        {"name": "Starred", "special_use": "\\Flagged", "identity": "\\Flagged"},
        {"name": "Projects", "special_use": None, "identity": "Projects"},
    ]
    assert instance.logged_out


def test_uid_sync_flags_uidvalidity_and_peek(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_emails(
        mailbox="Sent Items",
        mailbox_identity="\\Sent",
        n_emails=2,
    )
    instance = FakeIMAP.instances[-1]

    assert ("select", '"Sent Items"') in instance.calls
    assert any(call[0:2] == ("uid", "SEARCH") for call in instance.calls)
    fetches = [call for call in instance.calls if call[0:2] == ("uid", "FETCH")]
    assert fetches
    assert all("BODY.PEEK[]" in call[3] for call in fetches)

    messages = isolated_db.get_all_emails(
        "user@example.test", protocol="imap", mailbox="\\Sent"
    )
    assert {message["uid"] for message in messages} == {"41", "42"}
    assert {message["uidvalidity"] for message in messages} == {"777"}
    assert {message["uid"]: message["is_read"] for message in messages} == {
        "41": False,
        "42": True,
    }
    assert instance.logged_out


def test_sync_does_not_mark_message_as_seen(
    monkeypatch, mail_config, isolated_db
):
    client = configure(monkeypatch, mail_config, isolated_db)
    client.get_emails()
    calls = FakeIMAP.instances[-1].calls

    assert not any(call[0:2] == ("uid", "STORE") for call in calls)
    assert all(
        "BODY.PEEK[]" in call[3]
        for call in calls
        if call[0:2] == ("uid", "FETCH")
    )


def test_mark_as_read_uses_uid_store(monkeypatch, mail_config, isolated_db):
    client = configure(monkeypatch, mail_config, isolated_db)
    isolated_db.save_email(
        protocol="imap", account=client.USER, mailbox="\\Sent", uid="41",
        uidvalidity="777", sender="sender", subject="subject", date="",
        body="body", is_read=False,
    )

    client.mark_as_read(
        "Sent Items",
        "41",
        "777",
        mailbox_identity="\\Sent",
    )
    calls = FakeIMAP.instances[-1].calls
    assert ("select", '"Sent Items"') in calls
    assert ("uid", "STORE", "41", "+FLAGS.SILENT", "(\\Seen)") in calls
    message = isolated_db.get_all_emails(
        client.USER,
        protocol="imap",
        mailbox="\\Sent",
    )[0]
    assert message["is_read"] is True


def test_logout_on_fetch_error(monkeypatch, mail_config, isolated_db):
    client = configure(monkeypatch, mail_config, isolated_db)
    FakeIMAP.fail_fetch = True
    client.get_emails()
    assert FakeIMAP.instances[-1].logged_out


def test_missing_credentials_does_not_connect(
    monkeypatch, mail_config, isolated_db
):
    FakeIMAP.instances.clear()
    monkeypatch.setitem(mail_config.config["auth"], "user", "")
    mail_config.ImapEmail().get_emails()
    assert FakeIMAP.instances == []
