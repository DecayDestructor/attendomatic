from fastapi import HTTPException


def verify_secret_header(header_value: str, expected_token: str):
    """
    Verify that the incoming header matches the expected secret token.
    Raises HTTPException if verification fails.
    """
    if header_value != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")
