"""
Telegram webhook secret token verification.

Ensures that incoming webhook requests actually originate from Telegram
by comparing the X-Telegram-Bot-Api-Secret-Token header against our secret.
"""

from fastapi import HTTPException, Header

from backend.config import settings


def verify_secret_header(header_value: str, expected_token: str):
    """Raise 403 if the provided header value doesn't match the expected secret."""
    if header_value != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")


def verify_api_secret(x_api_secret_key: str = Header(None)):
    """Dependency that validates API secret header"""
    verify_secret_header(
        header_value=x_api_secret_key,
        expected_token=settings.API_SECRET_KEY,
    )
