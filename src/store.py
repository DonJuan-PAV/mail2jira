"""
Memory of mail2jira: a small SQLite database (a single file, no server needed).

It records every email that has been handled, so the same email never
creates two tickets, even after a restart.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from models import Email

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed (
    email_id      TEXT PRIMARY KEY,   -- Outlook's ID for the email
    subject       TEXT,
    sender        TEXT,
    received      TEXT,
    ticket_created INTEGER NOT NULL,  -- 1 = ticket created, 0 = skipped as noise
    skip_reason   TEXT,               -- why it was skipped (NULL if a ticket was created)
    ticket_key    TEXT,               -- the Jira ticket, e.g. SUP-12 (DRY-RUN in dry-run mode)
    processed_at  TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        with self._db() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        """Open the database, save changes when done, and always close it."""
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:  # commits on success, rolls back on error
                yield conn
        finally:
            conn.close()

    def is_processed(self, email: Email) -> bool:
        with self._db() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed WHERE email_id = ?", (email.id,)
            ).fetchone()
        return row is not None

    def mark_processed(self, email: Email, ticket_created: bool,
                       skip_reason: str | None = None,
                       ticket_key: str | None = None) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed VALUES (?,?,?,?,?,?,?,?)",
                (email.id, email.subject, email.sender, email.received,
                 int(ticket_created), skip_reason, ticket_key, now),
            )

    def count(self, ticket_created: bool) -> int:
        """How many emails became tickets (True) or were skipped (False)."""
        with self._db() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM processed WHERE ticket_created = ?",
                (int(ticket_created),)).fetchone()[0]
