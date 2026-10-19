"""
Tests for the Outlook reader, with a FAKE Microsoft Graph (no account needed).
"""

from unittest.mock import MagicMock, patch

from outlook import OutlookMailbox


def graph_reply(items):
    response = MagicMock()
    response.json.return_value = {"value": items}
    return response


def item(id, subject, received):
    return {"id": id, "subject": subject, "receivedDateTime": received,
            "from": {"emailAddress": {"address": "client@example.com"}},
            "body": {"content": "Hello"}}


def fetch(items):
    mailbox = OutlookMailbox(client_id="abc", cache_path="unused.json")
    with patch.object(OutlookMailbox, "get_token", return_value="fake-token"), \
         patch("outlook.requests.get", return_value=graph_reply(items)) as get:
        emails = mailbox.fetch_unread()
    return emails, get.call_args.kwargs["params"]


def test_asks_for_newest_recent_unread_first():
    _, params = fetch([])
    assert params["$orderby"] == "receivedDateTime desc"
    # the ordered field must come first in the filter, or Graph rejects the request
    assert params["$filter"].startswith("receivedDateTime ge ")
    assert params["$filter"].endswith("and isRead eq false")


def test_returns_oldest_first_for_ticket_order():
    # Graph answers newest first...
    emails, _ = fetch([
        item("3", "Third", "2026-10-19T12:00:00Z"),
        item("2", "Second", "2026-10-19T11:00:00Z"),
        item("1", "First", "2026-10-19T10:00:00Z"),
    ])
    # ...and tickets are created in the order the emails arrived
    assert [e.subject for e in emails] == ["First", "Second", "Third"]


def test_missing_fields_do_not_crash():
    emails, _ = fetch([{"id": "1", "subject": None, "from": None, "body": None}])
    assert emails[0].subject == "" and emails[0].sender == "unknown" and emails[0].body == ""
