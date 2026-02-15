"""
User management helpers.

Provides create and read operations for User records.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import User, AttendanceLog


def create_user(user: User, session: Session = Depends(get_session)):
    """Create a new user, raising 400 if a user with the same UID already exists."""
    existing_user = session.exec(select(User).where(User.uid == user.uid)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this UID already exists")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def read_user(contact_id: str, session: Session = Depends(get_session)):
    """Look up a user by their Telegram contact_id. Raises 404 if not found."""
    statement = select(User).where(User.contact_id == contact_id)
    results = session.exec(statement)
    user = results.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
