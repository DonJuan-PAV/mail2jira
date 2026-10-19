"""
mail2jira - watches an Outlook mailbox and turns important emails into Jira tickets.

Every POLL_SECONDS seconds it:
  1. Reads the unread emails in the inbox.
  2. Ignores the ones it has already handled (remembered in a database).
  3. Skips noise: replies, forwards, auto-replies, no-reply senders, spam.
  4. Creates a Jira ticket for each important email
     (or only logs it, in dry-run mode, the default).

Run it:
    python src/main.py          # runs forever (Ctrl+C to stop)
    python src/main.py --once   # one check, then exit (handy for testing)
"""

import argparse
import logging
import os
import signal
import sys
import threading

from config import load_settings, validate
from filters import get_skip_reason
from jira_client import JiraClient
from outlook import OutlookMailbox
from store import Store

log = logging.getLogger("mail2jira")


def process_once(mailbox, store: Store, jira) -> dict:
    """
    One check of the mailbox. Returns counts of what happened, for the logs.

    An important email is only marked as handled AFTER Jira accepted the ticket.
    If Jira is down, the email is retried on the next check instead of being lost.
    """
    counts = {"tickets": 0, "skipped": 0, "failed": 0}

    for email in mailbox.fetch_unread():
        if store.is_processed(email):
            continue  # already handled on an earlier check: no duplicate ticket

        reason = get_skip_reason(email.subject, email.sender)
        if reason:
            store.mark_processed(email, ticket_created=False, skip_reason=reason)
            log.info("Skipped \"%s\" -> %s", email.subject or "(no subject)", reason)
            counts["skipped"] += 1
            continue

        try:
            key = jira.create_ticket(email)
        except Exception as exc:  # network error, Jira down, bad credentials...
            log.error("Could not create ticket for \"%s\" (will retry next check): %s",
                      email.subject, exc)
            counts["failed"] += 1
            continue

        store.mark_processed(email, ticket_created=True, ticket_key=key)
        counts["tickets"] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn important emails into Jira tickets.")
    parser.add_argument("--once", action="store_true", help="check once and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = load_settings()
    problems = validate(settings)
    if problems:
        for problem in problems:
            log.error(problem)
        sys.exit("Fix the settings in your .env file, then try again.")

    os.makedirs(settings.data_dir, exist_ok=True)
    store = Store(os.path.join(settings.data_dir, "mail2jira.db"))
    mailbox = OutlookMailbox(
        client_id=settings.client_id,
        cache_path=os.path.join(settings.data_dir, "token_cache.json"),
    )
    jira = JiraClient(
        project_key=settings.jira_project_key,
        issue_type=settings.jira_issue_type,
        dry_run=settings.jira_dry_run,
        url=settings.jira_url,
        email=settings.jira_email,
        api_token=settings.jira_api_token,
    )
    mode = "DRY RUN (no Jira account needed)" if settings.jira_dry_run else settings.jira_url

    if args.once:
        log.info("Jira: %s", mode)
        log.info("Result: %s", process_once(mailbox, store, jira))
        return

    # Stop cleanly on Ctrl+C or when Docker stops the container
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    log.info("Watching the inbox every %s s. Jira: %s", settings.poll_seconds, mode)

    while not stop.is_set():
        try:
            counts = process_once(mailbox, store, jira)
            if any(counts.values()):
                log.info("Check done: %s", counts)
        except Exception:
            # A failed check (internet down, Microsoft busy...) must never
            # kill the program: log it and try again next time.
            log.exception("Check failed, retrying in %s s", settings.poll_seconds)
        stop.wait(settings.poll_seconds)  # sleeps, but wakes up at once on stop

    log.info("Stopped.")


if __name__ == "__main__":
    main()
