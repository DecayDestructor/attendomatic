"""
User router — exposes HTTP endpoints for user management.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import User, AttendanceLog
from backend.utils.userManagement import create_user, read_user

router = APIRouter()


@router.post("/users/", response_model=User)
def create_single_user(user: User, session: Session = Depends(get_session)):
    """Create a new user record."""
    return create_user(user, session)
