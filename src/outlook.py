"""
Outlook mailbox: signs in to Microsoft and reads unread emails
through the Microsoft Graph API.
"""

import logging
import os

import msal
import requests

from models import Email

log = logging.getLogger(__name__)

AUTHORITY = "https://login.microsoftonline.com/consumers"  # personal Microsoft accounts
SCOPES = ["Mail.Read"]                                     # read-only access to email
GRAPH_URL = "https://graph.microsoft.com/v1.0"
MAX_BODY_CHARS = 20000  # cut very long emails so a ticket stays readable


class OutlookMailbox:
    def __init__(self, client_id: str, cache_path: str):
        self.client_id = client_id    # Azure app registration ID
        self.cache_path = cache_path  # file where the login is remembered

    # --- Login -----------------------------------------------------------

    def _load_cache(self) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if os.path.exists(self.cache_path):
            with open(self.cache_path) as f:
                cache.deserialize(f.read())
        return cache

    def _save_cache(self, cache: msal.SerializableTokenCache) -> None:
        if cache.has_state_changed:
            with open(self.cache_path, "w") as f:
                f.write(cache.serialize())
            os.chmod(self.cache_path, 0o600)  # only the owner can read the login

    def get_token(self) -> str:
        """Return an access token, signing in with a device code if needed."""
        cache = self._load_cache()
        app = msal.PublicClientApplication(
            self.client_id, authority=AUTHORITY, token_cache=cache)

        # 1) Saved login: MSAL refreshes it silently when it expires
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])

        # 2) No saved login: show a link + code to sign in from any browser.
        #    In Docker, this message appears in the container logs.
        if not result:
            flow = app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"Could not start sign-in: {flow.get('error_description')}")
            log.warning("SIGN-IN NEEDED: %s", flow["message"])
            result = app.acquire_token_by_device_flow(flow)  # waits for you

        self._save_cache(cache)

        if "access_token" not in result:
            raise RuntimeError(f"Sign-in failed: {result.get('error_description')}")
        return result["access_token"]

    # --- Reading ---------------------------------------------------------

    def fetch_unread(self, limit: int = 25) -> list[Email]:
        """Return up to `limit` unread emails from the inbox."""
        token = self.get_token()
        response = requests.get(
            f"{GRAPH_URL}/me/mailFolders/inbox/messages",
            headers={
                "Authorization": f"Bearer {token}",
                # body as plain text (not HTML), and IDs that never change,
                # even if the email is moved to another folder later
                "Prefer": 'outlook.body-content-type="text", IdType="ImmutableId"',
            },
            params={
                "$filter": "isRead eq false",
                "$select": "id,subject,from,receivedDateTime,body",
                "$top": limit,
            },
            timeout=30,
        )
        response.raise_for_status()

        emails = []
        for item in response.json().get("value", []):
            emails.append(Email(
                id=item["id"],
                subject=item.get("subject") or "",
                sender=(item.get("from") or {}).get("emailAddress", {}).get("address", "unknown"),
                received=item.get("receivedDateTime", ""),
                body=((item.get("body") or {}).get("content") or "")[:MAX_BODY_CHARS],
            ))
        return emails
