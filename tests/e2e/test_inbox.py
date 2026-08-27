import pytest

from views import inbox_view


pytestmark = pytest.mark.e2e


class FakePage:
    def __init__(self):
        self.controls = []
        self.tasks = []
        self.appbar = None
        self.floating_action_button = None

    def clean(self):
        self.controls.clear()

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.dialog = None

    def run_task(self, handler, *args, **kwargs):
        self.tasks.append((handler, args, kwargs))


def configure_protocol(monkeypatch, protocol):
    monkeypatch.setitem(inbox_view.config["app"], "protocol", protocol)
    monkeypatch.setitem(
        inbox_view.config["auth"], "user", "user@example.test"
    )


def mailbox_control(page):
    root_row = page.controls[0]
    left_panel = root_row.controls[0]
    return left_panel.controls[0]


@pytest.mark.parametrize(
    ("protocol", "expected_visible"),
    [("imap", True), ("pop", False)],
)
def test_mailbox_selector_visibility(
    monkeypatch, protocol, expected_visible
):
    configure_protocol(monkeypatch, protocol)
    monkeypatch.setattr(inbox_view.db, "get_all_emails", lambda *a, **k: [])
    page = FakePage()

    inbox_view.show_inbox(page)

    assert mailbox_control(page).visible is expected_visible
    assert mailbox_control(page).content.key == "mailbox-selector"


async def test_open_unread_pop_message_marks_it_read(monkeypatch):
    configure_protocol(monkeypatch, "pop")
    message = {
        "id": 1,
        "protocol": "pop",
        "account": "user@example.test",
        "mailbox": "INBOX",
        "uid": "uidl-1",
        "uidvalidity": "",
        "from": "sender@example.test",
        "subject": "Unread subject",
        "date": "today",
        "body": "Local body",
        "is_read": False,
    }

    monkeypatch.setattr(
        inbox_view.db,
        "get_all_emails",
        lambda *args, **kwargs: [message],
    )

    def mark_read(*args):
        message["is_read"] = True

    monkeypatch.setattr(inbox_view.db, "mark_email_as_read", mark_read)

    async def run_immediately(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(inbox_view.asyncio, "to_thread", run_immediately)
    page = FakePage()
    inbox_view.show_inbox(page)
    left_panel = page.controls[0].controls[0]
    card = left_panel.controls[1].controls[0]

    await card.on_click(None)

    right_column = page.controls[0].controls[1]
    markdown = right_column.content.controls[-1]
    assert markdown.value == "Local body"
    assert message["is_read"] is True


async def test_account_change_resets_visual_session(monkeypatch):
    configure_protocol(monkeypatch, "imap")
    message = {
        "id": 1,
        "protocol": "imap",
        "account": "user@example.test",
        "mailbox": "INBOX",
        "uid": "41",
        "uidvalidity": "777",
        "from": "sender@example.test",
        "subject": "Old account message",
        "date": "today",
        "body": "Old body",
        "is_read": True,
    }
    requested_accounts = []

    def get_emails(account, **kwargs):
        requested_accounts.append(account)
        return [message] if account == "user@example.test" else []

    monkeypatch.setattr(inbox_view.db, "get_all_emails", get_emails)

    async def run_immediately(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(inbox_view.asyncio, "to_thread", run_immediately)
    monkeypatch.setattr(inbox_view.config, "read", lambda *args: None)

    def update_config(values):
        for section, options in values.items():
            for key, value in options.items():
                inbox_view.config[section][key] = str(value)

    monkeypatch.setattr(inbox_view, "update_config_file", update_config)
    page = FakePage()
    inbox_view.show_inbox(page)
    card = page.controls[0].controls[0].controls[1].controls[0]
    await card.on_click(None)

    page.appbar.actions[2].on_click(None)
    settings = page.dialog
    settings.content.controls[0].value = "new@example.test"
    settings.actions[1].on_click(None)

    right_column = page.controls[0].controls[1]
    assert right_column.content.controls[0].value == "Bienvenido a tu Cliente de Correo"
    assert right_column.content.controls[1].value == ""
    assert right_column.content.controls[-1].value == inbox_view.SAMPLE_TEXT
    assert right_column.content.controls[2].controls[1].visible is False
    assert mailbox_control(page).content.value == "INBOX"
    assert requested_accounts[-1] == "new@example.test"


async def test_same_account_settings_preserve_open_message(monkeypatch):
    configure_protocol(monkeypatch, "imap")
    message = {
        "id": 1,
        "protocol": "imap",
        "account": "user@example.test",
        "mailbox": "INBOX",
        "uid": "41",
        "uidvalidity": "777",
        "from": "sender@example.test",
        "subject": "Keep this message",
        "date": "today",
        "body": "Keep this body",
        "is_read": True,
    }
    monkeypatch.setattr(
        inbox_view.db,
        "get_all_emails",
        lambda *args, **kwargs: [message],
    )

    async def run_immediately(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(inbox_view.asyncio, "to_thread", run_immediately)
    monkeypatch.setattr(inbox_view.config, "read", lambda *args: None)

    def update_config(values):
        for section, options in values.items():
            for key, value in options.items():
                inbox_view.config[section][key] = str(value)

    monkeypatch.setattr(inbox_view, "update_config_file", update_config)
    page = FakePage()
    inbox_view.show_inbox(page)
    card = page.controls[0].controls[0].controls[1].controls[0]
    await card.on_click(None)

    page.appbar.actions[2].on_click(None)
    settings = page.dialog
    settings.content.controls[3].controls[1].value = "2993"
    settings.actions[1].on_click(None)

    right_column = page.controls[0].controls[1]
    assert right_column.content.controls[0].value == "Keep this message"
    assert right_column.content.controls[-1].value == "Keep this body"
