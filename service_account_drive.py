#!/usr/bin/env python3
"""
Service Account helper for Google Drive access.

This module mints short-lived OAuth2 access tokens using a Google Cloud
service account JSON key. Tokens can be used with the existing requests-based
Drive calls (Authorization: Bearer <token>).
"""

import os
import json
from typing import Optional

from datetime import datetime, timedelta

_CACHED_TOKEN: Optional[str] = None
_CACHED_EXPIRY: Optional[datetime] = None


def _load_google_auth():
    """Import google-auth lazily to avoid import errors if not installed yet."""
    try:
        from google.oauth2 import service_account  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "google-auth is required. Add `google-auth` to requirements and install."
        ) from exc
    return service_account


def get_service_account_access_token(scopes=None, user_email=None) -> str:
    """
    Return a valid access token for Google Drive using a service account.
    
    For shared folders, we need to impersonate the user who shared the folder.
    This requires domain-wide delegation to be set up in Google Workspace.

    Env vars:
    - SERVICE_ACCOUNT_JSON_PATH: absolute path to the service account key JSON
    - SERVICE_ACCOUNT_SCOPES: optional comma-separated scopes override
    - IMPERSONATE_USER_EMAIL: email of user to impersonate (for shared folders)

    Args:
        scopes: Optional list of scopes. Defaults to Drive readonly + userinfo.email.
        user_email: Email of user to impersonate (for accessing shared folders)

    Returns:
        OAuth2 access token string.
    """
    global _CACHED_TOKEN, _CACHED_EXPIRY

    # Return cached if valid for at least 2 minutes
    if _CACHED_TOKEN and _CACHED_EXPIRY and datetime.utcnow() < (_CACHED_EXPIRY - timedelta(minutes=2)):
        return _CACHED_TOKEN

    key_path = os.getenv('SERVICE_ACCOUNT_JSON_PATH')
    if not key_path or not os.path.exists(key_path):
        raise RuntimeError("SERVICE_ACCOUNT_JSON_PATH not set or file not found")

    # Determine scopes
    scopes_from_env = os.getenv('SERVICE_ACCOUNT_SCOPES')
    if scopes_from_env:
        scopes_list = [s.strip() for s in scopes_from_env.split(',') if s.strip()]
    else:
        scopes_list = scopes or [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/userinfo.email',
        ]

    service_account = _load_google_auth()

    # Check if we need to impersonate a user (for shared folders)
    impersonate_email = user_email or os.getenv('IMPERSONATE_USER_EMAIL')
    
    if impersonate_email:
        print(f"🔑 Impersonating user: {impersonate_email}")
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=scopes_list,
        )
        
        # Create delegated credentials
        delegated_credentials = credentials.with_subject(impersonate_email)
    else:
        print("🔑 Using service account directly")
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=scopes_list,
        )
        delegated_credentials = credentials

    # Refresh to get token
    import google.auth.transport.requests  # type: ignore

    request = google.auth.transport.requests.Request()
    delegated_credentials.refresh(request)

    access_token = delegated_credentials.token
    expiry = delegated_credentials.expiry  # datetime

    if not access_token:
        raise RuntimeError("Failed to obtain service account access token")

    _CACHED_TOKEN = access_token
    _CACHED_EXPIRY = expiry or (datetime.utcnow() + timedelta(minutes=45))
    return access_token


def get_bot_service_account_email() -> Optional[str]:
    """Return the bot's service account email for sharing instructions."""
    # Prefer explicit env; fallback to reading from JSON file for convenience.
    email = os.getenv('BOT_SERVICE_ACCOUNT_EMAIL')
    if email:
        return email

    key_path = os.getenv('SERVICE_ACCOUNT_JSON_PATH')
    if key_path and os.path.exists(key_path):
        try:
            with open(key_path, 'r') as f:
                data = json.load(f)
            return data.get('client_email')
        except Exception:
            return None
    return None


