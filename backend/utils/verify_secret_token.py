from fastapi import HTTPException


def verify_secret_header(header_value: str, expected_token: str):
    if header_value != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")
