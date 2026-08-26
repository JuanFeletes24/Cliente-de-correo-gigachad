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
        pass

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
