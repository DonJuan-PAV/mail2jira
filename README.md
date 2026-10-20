# mail2jira

![tests](https://github.com/PAV-JUAN/mail2jira/actions/workflows/tests.yml/badge.svg)

Watches an Outlook support mailbox 24/7 and turns **real client requests** into Jira tickets, while ignoring the noise: replies, forwards, out-of-office messages, no-reply senders and spam.

Inspired by a similar tool used in my IT support job, which ran 24/7 on a virtual machine and made sure auto-replies and `RE:` emails didn't create tickets for no reason. This version is rebuilt from scratch for an Outlook mailbox.

## How it works

```
Outlook inbox ──► mail2jira (every 15 s) ──► filter ──► important ──► Jira ticket
(Microsoft Graph)        │                     │
                         │                     └──► noise ──► skipped (logged)
                         ▼
                   SQLite memory (no duplicate tickets, even after a restart)
```

- **Reads** unread emails through the Microsoft Graph API with a secure OAuth sign-in (no password stored).
- **Filters** noise with bilingual (English/French) rules: `RE:`, `FW:`, `TR:`, auto-replies, `noreply@`, delivery failures, common spam.
- **Remembers** every handled email in a SQLite database, so the same email never creates two tickets.
- **Retries** automatically: an email is only marked as handled once Jira accepted the ticket. If Jira is down, nothing is lost.
- **Dry-run mode** (default) builds every ticket but only logs it, so the project runs without a Jira account.
- **Tested** with pytest and GitHub Actions, including a fake Jira, so the API integration is checked on every push.

## Example output

```
2026-10-18 21:31:39 INFO Watching the inbox every 15 s. Jira: DRY RUN (no Jira account needed)
2026-10-18 21:31:39 INFO DRY RUN - would create Task in SUP: "Printer broken on 2nd floor" (from client@example.com)
2026-10-18 21:31:39 INFO Skipped "RE: Printer broken" -> reply/forward (RE:)
2026-10-18 21:31:39 INFO Skipped "Your receipt" -> automated sender (noreply)
```

With `JIRA_DRY_RUN=false`:
```
2026-10-18 21:31:54 INFO Created Jira ticket SUP-12: "Cannot access VPN" (from client@example.com)
```

## Setup

### 1. Register an app with Microsoft (free, one time)

1. Sign in at [portal.azure.com](https://portal.azure.com) → **App registrations** → **New registration**.
2. Name: `mail2jira`. Supported account types: **Personal Microsoft accounts only** (or "any organizational directory and personal Microsoft accounts"). Leave Redirect URI empty → **Register**.
3. Copy the **Application (client) ID**.
4. **Authentication** → **Allow public client flows** → **Yes** → Save. (Needed for the device-code sign-in.)
5. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated** → **Mail.Read** → Add.

### 2. Configure

```bash
git clone https://github.com/DonJuan-PAV/mail2jira.git
cd mail2jira
cp .env.example .env     # then edit .env and paste your CLIENT_ID
```

### 3a. Run with Docker (recommended, runs 24/7)

```bash
docker compose up -d --build
docker logs -f mail2jira     # first run: open the link shown and enter the code to sign in
```

The sign-in is saved in `./data/`, so it survives restarts and updates.

### 3b. Or run with Python

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py --once    # single check, good for testing
python src/main.py           # runs until Ctrl+C
```

### 4. Create real Jira tickets

Out of the box, mail2jira runs in **dry-run mode** and only logs the tickets it would create. To send them to Jira Cloud, create an [API token](https://id.atlassian.com/manage-profile/security/api-tokens) and set in `.env`:

```
JIRA_DRY_RUN=false
JIRA_URL=https://your-site.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=SUP
```

Emails already handled in dry-run mode are remembered and won't be re-sent. Delete `data/mail2jira.db` to start fresh.

## Filter rules

All rules are plain lists at the top of [`src/filters.py`](src/filters.py), so adding a keyword doesn't require touching the logic.

| Rule | Examples skipped |
|---|---|
| Reply / forward prefix | `RE:`, `Re :`, `FW:`, `FWD:`, `TR:` |
| Automated sender | `noreply@`, `do-not-reply@`, `mailer-daemon@` |
| Automatic message | Out of office, Réponse automatique, Undeliverable |
| Spam keywords | "you have won", "lottery", "félicitations" |
| Empty subject | nothing to use as a ticket title |

`Reset password` and `Treasury report` are **not** skipped: a prefix only counts when followed by a colon.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Covers the filter rules, duplicate prevention, retry after a failed ticket, dry-run mode, settings validation, and the Jira API request (with a fake Jira, so no account is needed).

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

**`AADSTS16000: User account ... does not exist in tenant 'Microsoft Services'`** when opening App registrations in the Azure portal
A personal Microsoft account has no Azure directory (tenant) of its own. Create a free Azure account at [azure.microsoft.com/free](https://azure.microsoft.com/free) (use a private window); this creates your own tenant, and App registrations then work.

**`Sign-in failed`** on first run
Check that *Allow public client flows* is set to **Yes** in the app's Authentication page, and that `CLIENT_ID` in `.env` matches the Application (client) ID.

**Jira returns 401**
The API token or email is wrong. Jira Cloud uses your Atlassian account email + an API token, never your password.

**Jira returns 400**
Usually the project key or issue type doesn't exist in your Jira site. Check `JIRA_PROJECT_KEY` and `JIRA_ISSUE_TYPE`.

## Roadmap

- [x] Read Outlook via Microsoft Graph
- [x] Bilingual noise filter
- [x] Duplicate prevention and retry
- [x] Jira Cloud tickets (tested with a fake Jira) + dry-run mode
- [x] Docker deployment
- [ ] Add replies (`RE:`) as comments on the existing ticket instead of skipping them
- [ ] End-to-end test against a real Jira Cloud site
