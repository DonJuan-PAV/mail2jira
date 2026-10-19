"""The shape of an email inside mail2jira."""

from dataclasses import dataclass


@dataclass
class Email:
    id: str         # unique ID given by Outlook (never changes)
    subject: str
    sender: str     # sender's email address
    received: str   # date and time received (ISO format)
    body: str = ""  # plain-text content
