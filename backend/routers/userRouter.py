from fastapi import APIRouter, Depends, HTTPException
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import User, AttendanceLog
from backend.utils.userManagement import create_user, read_user

router = APIRouter()


@router.post("/users/", response_model=User)
def create_single_user(user: User, session: Session = Depends(get_session)):
    return create_user(user, session)
