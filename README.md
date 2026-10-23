# mail2jira

[![tests](https://github.com/PAV-JUAN/mail2jira/actions/workflows/tests.yml/badge.svg)](https://github.com/PAV-JUAN/mail2jira/actions/workflows/tests.yml)

Watches an Outlook support mailbox and turns real client requests into Jira tickets. Replies, forwards, out-of-office messages, no-reply senders and spam are skipped.

## Why I built this

At my job, a lot of support requests come in by email, and we used to create a Jira ticket for each one by hand. So we built an app to do it: it reads the support mailbox, figures out which emails are real requests or questions, and creates a Jira ticket with a copy of the email and everyone who was in CC. It runs 24/7 on a virtual machine and checks the mailbox every 10-15 seconds.

From there, we answer clients through Jira's own email feature, so every message back and forth lands on the same ticket. That's why the filter matters so much. A reply like "RE: thanks!" already belongs to an existing ticket, and an out-of-office message isn't a request at all. If those became new tickets, the board would fill up with duplicates that someone has to close by hand.

mail2jira is my own version, rebuilt from scratch on my own time for an Outlook mailbox, so I can show how it works without sharing anything from work. It also goes with the Jira automation rules I set up at work, which read incoming tickets for keywords and label them before they're assigned. Those rules sort the tickets; this decides what deserves a ticket in the first place.

## How it works

Every 15 seconds, mail2jira:

1. Reads unread emails through the Microsoft Graph API. It signs in with OAuth, so no password is stored anywhere.
2. Runs each email through the filter rules. Noise gets skipped and logged with the reason.
3. Turns each real request into a Jira ticket.
4. Saves the email's ID in a small SQLite database, so the same email never creates two tickets, even after a restart.

An email only counts as handled once Jira has accepted the ticket. If Jira is down, the email is tried again on the next check instead of being lost.

```
Outlook inbox → mail2jira (every 15 s) → filter → real request → Jira ticket
                        ↓                    ↓
                  SQLite memory           noise → skipped (logged)
```

By default it runs in dry-run mode: it builds every ticket exactly as it would send it, but only logs it. That way anyone can try it on their own mailbox before connecting a Jira site.

## What it looks like running

```
2026-10-18 21:31:39 INFO Watching the inbox every 15 s. Jira: DRY RUN (no Jira account needed)
2026-10-18 21:31:39 INFO DRY RUN - would create Task in SUP: "Printer broken on 2nd floor" (from client@example.com)
2026-10-18 21:31:39 INFO Skipped "RE: Printer broken" -> reply/forward (RE:)
2026-10-18 21:31:39 INFO Skipped "Your receipt" -> automated sender (noreply)
```

Connected to Jira (`JIRA_DRY_RUN=false`):

```
2026-10-18 21:31:54 INFO Created Jira ticket SUP-12: "Cannot access VPN" (from client@example.com)
```

## The filter rules

Our clients write in English and French, so the rules cover both. They're plain lists at the top of [`src/filters.py`](src/filters.py), so adding a keyword doesn't mean touching the logic.

| Rule | Examples skipped |
|---|---|
| Reply / forward prefix | `RE:`, `Re :`, `FW:`, `FWD:`, `TR:` |
| Automated sender | `noreply@`, `do-not-reply@`, `mailer-daemon@` |
| Automatic message | Out of office, Réponse automatique, Undeliverable |
| Spam keywords | "you have won", "lottery", "félicitations" |
| Empty subject | nothing to use as a ticket title |

The French forward prefix `TR:` caused an interesting problem. A simple "starts with TR" check would also skip an email titled "Treasury report", and "RE" would catch "Reset password". So a prefix only counts when it's followed by a colon, with or without a space before it, since French puts one there.

## Setup

### 1. Register an app with Microsoft (free, one time)

1. Sign in at [portal.azure.com](https://portal.azure.com) → **App registrations** → **New registration**.
2. Name: `mail2jira`. Supported account types: **Personal Microsoft accounts only** (or "any organizational directory and personal Microsoft accounts"). Leave Redirect URI empty → **Register**.
3. Copy the **Application (client) ID**.
4. **Authentication** → **Allow public client flows** → **Yes** → Save. (Needed for the device-code sign-in.)
5. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated** → **Mail.Read** → Add.

If App registrations gives you an `AADSTS16000` error, see Troubleshooting. That one got me too.

### 2. Configure

```bash
git clone https://github.com/PAV-JUAN/mail2jira.git
cd mail2jira
cp .env.example .env     # then edit .env and paste your CLIENT_ID
```

### 3a. Run with Docker (runs 24/7)

```bash
docker compose up -d --build
docker logs -f mail2jira     # first run: open the link shown and enter the code to sign in
```

The sign-in is saved in `./data/`, so it survives restarts and updates.

### 3b. Or run with Python

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py --once    # a single check, good for testing
python src/main.py           # runs until Ctrl+C
```

### 4. Connect it to Jira

Create an [API token](https://id.atlassian.com/manage-profile/security/api-tokens) and set this in `.env`:

```
JIRA_DRY_RUN=false
JIRA_URL=https://your-site.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=SUP
```

Emails already handled in dry-run mode are remembered and won't be sent again. Delete `data/mail2jira.db` to start fresh.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

The tests cover the filter rules, duplicate prevention, retrying after a failed ticket, dry-run mode, settings validation, and the Jira API request (against a fake Jira, so the tests don't touch a real site). They run on every push with GitHub Actions.

## Project structure

```
src/
  main.py          the 24/7 loop
  outlook.py       Microsoft sign-in + reading emails (Graph API)
  filters.py       noise rules
  jira_client.py   builds and creates Jira tickets (or logs them in dry-run mode)
  store.py         SQLite memory of handled emails
  config.py        settings from .env
tests/             pytest suite
```

## Troubleshooting

**`AADSTS16000: User account ... does not exist in tenant 'Microsoft Services'`** when opening App registrations. A personal Microsoft account doesn't come with its own Azure directory (tenant). Create a free Azure account at [azure.microsoft.com/free](https://azure.microsoft.com/free) (in a private window). That creates a tenant, and App registrations will work.

**`Sign-in failed`** on the first run. Check that *Allow public client flows* is set to **Yes** on the app's Authentication page, and that `CLIENT_ID` in `.env` matches the Application (client) ID.

**Jira returns 401.** The API token or email is wrong. Jira Cloud uses your Atlassian account email plus an API token, never your password.

**Jira returns 400.** Usually the project key or issue type doesn't exist on your Jira site. Check `JIRA_PROJECT_KEY` and `JIRA_ISSUE_TYPE`.

## What's next

- An option for teams that don't reply through Jira's email feature: add `RE:` replies as comments on the existing ticket instead of skipping them.
