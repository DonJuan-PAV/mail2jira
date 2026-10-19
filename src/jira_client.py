"""
Jira: turns an important email into a Jira ticket (Jira Cloud REST API v3).

Dry-run mode (the default) builds exactly the same ticket but only logs it
instead of sending it, so the project runs without any Jira account.
Set JIRA_DRY_RUN=false with your Jira site and API token to create real tickets.
"""

import logging

import requests

from models import Email

log = logging.getLogger(__name__)

DRY_RUN_KEY = "DRY-RUN"  # recorded instead of a real ticket key in dry-run mode


class JiraError(Exception):
    pass


class JiraClient:
    MAX_SUMMARY = 250       # Jira refuses ticket titles longer than 255 characters
    MAX_BODY_LINES = 200    # keep tickets readable

    def __init__(self, project_key: str, issue_type: str = "Task", dry_run: bool = True,
                 url: str = "", email: str = "", api_token: str = ""):
        self.project_key = project_key
        self.issue_type = issue_type
        self.dry_run = dry_run
        self.url = url.rstrip("/")
        self.auth = (email, api_token)  # Jira Cloud: account email + API token

    @staticmethod
    def _paragraph(text: str) -> dict:
        """One paragraph in Atlassian Document Format (Jira's rich-text format)."""
        return {"type": "paragraph", "content": [{"type": "text", "text": text}]}

    def build_payload(self, email: Email) -> dict:
        """Turn an email into the JSON Jira expects to create a ticket."""
        # Ticket title: the subject on one line, trimmed to Jira's limit
        summary = " ".join(email.subject.split())[: self.MAX_SUMMARY] or "(no subject)"

        # Ticket description: who sent it and when, then the email itself.
        # Jira rejects empty text blocks, so blank lines are dropped.
        lines = [f"From: {email.sender}", f"Received: {email.received}", "----"]
        body_lines = [line.strip() for line in email.body.splitlines() if line.strip()]
        lines += body_lines[: self.MAX_BODY_LINES] or ["(empty email)"]

        return {
            "fields": {
                "project": {"key": self.project_key},
                "issuetype": {"name": self.issue_type},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [self._paragraph(line) for line in lines],
                },
            }
        }

    def create_ticket(self, email: Email) -> str:
        """Create the ticket and return its key (e.g. SUP-12), or raise JiraError."""
        payload = self.build_payload(email)

        if self.dry_run:
            log.info("DRY RUN - would create %s in %s: \"%s\" (from %s)",
                     self.issue_type, self.project_key,
                     payload["fields"]["summary"], email.sender)
            return DRY_RUN_KEY

        response = requests.post(
            f"{self.url}/rest/api/3/issue",
            json=payload,
            auth=self.auth,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if response.status_code >= 400:
            # Short error text only, never the token
            raise JiraError(f"Jira returned {response.status_code}: {response.text[:300]}")
        key = response.json()["key"]
        log.info("Created Jira ticket %s: \"%s\" (from %s)", key,
                 payload["fields"]["summary"], email.sender)
        return key
