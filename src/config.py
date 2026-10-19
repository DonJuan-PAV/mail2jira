"""
Settings for mail2jira.

Every setting comes from environment variables, usually loaded from the .env
file. Nothing personal is ever written in the code itself, which is what makes
the project safe to publish on GitHub.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    client_id: str          # Azure app registration ID (Outlook sign-in)
    poll_seconds: int       # how often to check the mailbox
    data_dir: str           # folder for the database and the saved login
    jira_dry_run: bool      # True = only log the tickets, don't call Jira
    jira_url: str           # e.g. https://your-site.atlassian.net
    jira_email: str         # Jira account email
    jira_api_token: str     # Jira API token (never your password)
    jira_project_key: str   # project the tickets go into, e.g. SUP
    jira_issue_type: str    # type of ticket, e.g. Task


def _as_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_settings() -> Settings:
    """Read the .env file and build the settings, with sensible defaults."""
    load_dotenv()
    return Settings(
        client_id=os.getenv("CLIENT_ID", "").strip(),
        poll_seconds=int(os.getenv("POLL_SECONDS", "15")),
        data_dir=os.getenv("DATA_DIR", "data").strip(),
        # Dry run is ON by default, so the project runs without a Jira account
        jira_dry_run=_as_bool(os.getenv("JIRA_DRY_RUN", "true")),
        jira_url=os.getenv("JIRA_URL", "").strip().rstrip("/"),
        jira_email=os.getenv("JIRA_EMAIL", "").strip(),
        jira_api_token=os.getenv("JIRA_API_TOKEN", "").strip(),
        jira_project_key=os.getenv("JIRA_PROJECT_KEY", "SUP").strip(),
        jira_issue_type=os.getenv("JIRA_ISSUE_TYPE", "Task").strip(),
    )


def validate(settings: Settings) -> list[str]:
    """Return a list of problems with the settings (empty list = all good)."""
    problems = []
    if not settings.client_id:
        problems.append("CLIENT_ID is missing (your Azure app's Application ID).")
    if settings.poll_seconds < 5:
        problems.append("POLL_SECONDS must be at least 5, to stay well within Microsoft's limits.")
    if not settings.jira_project_key:
        problems.append("JIRA_PROJECT_KEY is missing (for example SUP).")
    if not settings.jira_dry_run:
        for name, value in [
            ("JIRA_URL", settings.jira_url),
            ("JIRA_EMAIL", settings.jira_email),
            ("JIRA_API_TOKEN", settings.jira_api_token),
        ]:
            if not value:
                problems.append(f"{name} is required when JIRA_DRY_RUN=false.")
    return problems
