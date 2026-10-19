"""Tests for one full check of the mailbox, with a fake mailbox and a fake Jira."""

from conftest import make_email
from config import Settings, validate
from main import process_once


class FakeMailbox:
    def __init__(self, emails):
        self.emails = emails

    def fetch_unread(self):
        return list(self.emails)


class FakeJira:
    def __init__(self, fail=False):
        self.created = []
        self.fail = fail

    def create_ticket(self, email):
        if self.fail:
            raise ConnectionError("Jira is down")
        self.created.append(email)
        return f"SUP-{len(self.created)}"


def test_important_creates_ticket_and_noise_is_skipped(store):
    mailbox = FakeMailbox([
        make_email(id="1", subject="Printer broken"),
        make_email(id="2", subject="RE: Printer broken"),
        make_email(id="3", subject="Your receipt", sender="noreply@shop.com"),
    ])
    jira = FakeJira()
    counts = process_once(mailbox, store, jira)

    assert [e.subject for e in jira.created] == ["Printer broken"]
    assert counts == {"tickets": 1, "skipped": 2, "failed": 0}


def test_no_duplicate_tickets_across_checks(store):
    """The email stays unread in Outlook, so every check sees it again."""
    mailbox = FakeMailbox([make_email(id="1")])
    jira = FakeJira()
    for _ in range(5):
        process_once(mailbox, store, jira)
    assert len(jira.created) == 1


def test_failed_ticket_is_retried_next_check(store):
    mailbox = FakeMailbox([make_email(id="1")])

    counts = process_once(mailbox, store, FakeJira(fail=True))
    assert counts["failed"] == 1
    assert not store.is_processed(make_email(id="1"))  # not lost

    working = FakeJira()
    process_once(mailbox, store, working)
    assert len(working.created) == 1


def _settings(**changes):
    base = dict(client_id="abc", poll_seconds=15, data_dir="data", jira_dry_run=True,
                jira_url="", jira_email="", jira_api_token="", jira_project_key="SUP",
                jira_issue_type="Task")
    base.update(changes)
    return Settings(**base)


def test_dry_run_needs_no_jira_account():
    assert validate(_settings()) == []


def test_real_jira_requires_credentials():
    problems = validate(_settings(jira_dry_run=False))
    assert any("JIRA_API_TOKEN" in p for p in problems)
    assert any("JIRA_URL" in p for p in problems)


def test_bad_values_are_reported():
    problems = validate(_settings(client_id="", poll_seconds=1))
    assert len(problems) == 2
