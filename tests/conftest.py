"""Shared helpers for the tests."""

import pytest

from models import Email
from store import Store


def make_email(id="1", subject="Cannot log in to the app", sender="client@example.com",
               body="Hello,\n\nI can't log in since this morning.\n\nThanks"):
    return Email(id=id, subject=subject, sender=sender,
                 received="2026-10-18T14:00:00Z", body=body)


@pytest.fixture
def store(tmp_path):
    """A fresh, empty database in a temporary folder for each test."""
    return Store(str(tmp_path / "test.db"))
