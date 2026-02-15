"""
Telegram webhook secret token verification.

Ensures that incoming webhook requests actually originate from Telegram
by comparing the X-Telegram-Bot-Api-Secret-Token header against our secret.
"""

from fastapi import HTTPException


def verify_secret_header(header_value: str, expected_token: str):
    """Raise 403 if the provided header value doesn't match the expected secret."""
    if header_value != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")
