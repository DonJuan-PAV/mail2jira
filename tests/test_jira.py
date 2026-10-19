"""
Tests for the Jira client, using a FAKE Jira.

requests.post is replaced by a mock, so no Jira account or internet is needed.
These tests prove mail2jira sends the request Jira's API documentation asks for.
"""

from unittest.mock import MagicMock, patch

import pytest

from conftest import make_email
from jira_client import DRY_RUN_KEY, JiraClient, JiraError


@pytest.fixture
def jira():
    return JiraClient(project_key="SUP", dry_run=False, url="https://example.atlassian.net/",
                      email="bot@example.com", api_token="fake-token")


def fake_response(status, data=None, text=""):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = data or {}
    response.text = text
    return response


def test_creates_ticket_and_returns_key(jira):
    with patch("jira_client.requests.post",
               return_value=fake_response(201, {"key": "SUP-12"})) as post:
        assert jira.create_ticket(make_email()) == "SUP-12"

    args, kwargs = post.call_args
    assert args[0] == "https://example.atlassian.net/rest/api/3/issue"  # no double slash
    assert kwargs["auth"] == ("bot@example.com", "fake-token")
    assert kwargs["timeout"] == 30


def test_dry_run_never_calls_jira():
    jira = JiraClient(project_key="SUP")  # dry run is the default
    with patch("jira_client.requests.post") as post:
        assert jira.create_ticket(make_email()) == DRY_RUN_KEY
    post.assert_not_called()


def test_payload_matches_jira_format(jira):
    fields = jira.build_payload(make_email())["fields"]
    assert fields["project"] == {"key": "SUP"}
    assert fields["issuetype"] == {"name": "Task"}
    assert fields["summary"] == "Cannot log in to the app"

    description = fields["description"]
    assert description["type"] == "doc" and description["version"] == 1
    texts = [p["content"][0]["text"] for p in description["content"]]
    assert "From: client@example.com" in texts
    assert "I can't log in since this morning." in texts
    assert all(text.strip() for text in texts)  # Jira rejects empty text blocks


def test_long_or_multiline_subject_is_cleaned(jira):
    email = make_email(subject="Line one\nline two " + "x" * 400)
    summary = jira.build_payload(email)["fields"]["summary"]
    assert "\n" not in summary
    assert len(summary) <= 250


def test_empty_body_still_valid(jira):
    texts = [p["content"][0]["text"]
             for p in jira.build_payload(make_email(body=""))["fields"]["description"]["content"]]
    assert "(empty email)" in texts


def test_jira_error_raises_without_leaking_token(jira):
    with patch("jira_client.requests.post",
               return_value=fake_response(401, text="Unauthorized")):
        with pytest.raises(JiraError) as error:
            jira.create_ticket(make_email())
    assert "401" in str(error.value)
    assert "fake-token" not in str(error.value)
