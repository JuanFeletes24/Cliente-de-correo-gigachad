import sys
import os
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
TEST_BOOTSTRAP_DB = (
    Path(tempfile.gettempdir()) / f"cliente-correo-tests-{os.getpid()}.db"
)
os.environ["MAIL_DB_PATH"] = str(TEST_BOOTSTRAP_DB)

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def pytest_collection_modifyitems(config, items):
    gates = {
        "integration": "RUN_MAIL_INTEGRATION",
        "e2e": "RUN_FLET_E2E",
        "live": "RUN_MAIL_LIVE",
    }
    for item in items:
        for marker, variable in gates.items():
            if item.get_closest_marker(marker) and os.getenv(variable) != "1":
                item.add_marker(pytest.mark.skip(
                    reason=f"set {variable}=1 to run {marker} tests"
                ))


def pytest_sessionfinish(session, exitstatus):
    TEST_BOOTSTRAP_DB.unlink(missing_ok=True)


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from modules import db

    database = tmp_path / "mail.db"
    monkeypatch.setattr(db, "DB_PATH", database)
    db.init_db()
    return db


@pytest.fixture
def mail_config(monkeypatch):
    from modules import email as email_module

    values = {
        "auth": {"user": "user@example.test", "password": "secret"},
        "imap": {"server": "imap.example.test", "port": "1993"},
        "pop": {"server": "pop.example.test", "port": "1995"},
        "app": {"protocol": "imap", "days": "14"},
    }

    for section, options in values.items():
        if not email_module.config.has_section(section):
            email_module.config.add_section(section)
        for key, value in options.items():
            monkeypatch.setitem(email_module.config[section], key, value)

    return email_module
