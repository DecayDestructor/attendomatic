"""
Attendance router — CRUD endpoints for subjects, timetable slots, and attendance.

Provides REST API routes for:
- Creating / deleting subjects
- Adding / updating / deleting timetable slots
- Marking attendance
- Fetching daily timetable and attendance stats
"""

from fastapi import APIRouter, Depends, HTTPException
from requests import session
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import *
from backend.utils.userManagement import read_user
from backend.utils.attendanceManagement import (
    get_attendance_logs,
    get_daily_timetable_user,
    mark_attendance,
)
import json
from backend.utils.verify_secret_token import verify_api_secret

# All routes in this router require the X-Api-Secret-Key header
router = APIRouter(dependencies=[Depends(verify_api_secret)])


# ──────────── POST ROUTES ────────────


@router.post("/create_subject")
def create_subject(
    subject: Subjects,
    session: Session = Depends(get_session),
):
    """Create a new subject. Fails if code or name already exists."""
    existing_subject = session.exec(
        select(Subjects).where(
            (Subjects.subject_code == subject.subject_code)
            | (Subjects.subject_name == subject.subject_name)
        )
    ).first()
    if existing_subject:
        raise HTTPException(
            status_code=400,
            detail="Subject with the same code or name already exists",
        )
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return {"message": "Subject created successfully!", "subject": subject}


@router.post("/add_slot")
def add_slot(slots: TimetableSlots, session: Session = Depends(get_session)):
    """Add a new timetable slot. Rejects if it overlaps with an existing slot."""
    # Check for time-overlapping slots on the same day for this user
    conflict = session.exec(
        select(TimetableSlots).where(
            TimetableSlots.user_id == slots.user_id,
            TimetableSlots.day == slots.day,
            TimetableSlots.start_time < slots.end_time,
            TimetableSlots.end_time > slots.start_time,
        )
    ).first()

    if conflict:
        raise HTTPException(
            status_code=400,
            detail=f"Conflicting slot found: {conflict.subject_code} ({conflict.start_time}-{conflict.end_time})",
        )

    session.add(slots)
    session.commit()
    session.refresh(slots)
    return {"message": "Timetable slot added successfully!"}


from backend.db.models import DayEnum, AttendanceStatus


@router.post("/mark_attendance")
def mark_attendance_route(
    user_id: int,
    subject_code: str,
    day: DayEnum,
    start_time: time,
    end_time: time,
    status: AttendanceStatus,
    classType: ClassType,
    session: Session = Depends(get_session),
):
    """Mark attendance for a specific slot. Delegates to the utility function."""
    attendance_log = mark_attendance(
        user_id,
        subject_code,
        day,
        start_time,
        end_time,
        status,
        classType,
        session,
    )
    return {
        "message": "Attendance marked successfully!",
        "attendance_log": attendance_log,
    }


# ──────────── GET ROUTES ────────────


from backend.db.models import DayEnum


@router.get("/daily_timetable/{user_id}/{day}")
def get_daily_timetable(
    user_id: int, day: DayEnum, session: Session = Depends(get_session)
):
    """Return all timetable slots for a user on a given day."""
    return get_daily_timetable_user(user_id, day, session)


@router.get("/attendance_stat/{user_id}")
def get_attendance_stats(
    user_id: int,
    session: Session = Depends(get_session),
    subject_code: str | None = None,
    classType: ClassType | None = None,
):
    """
    Return attendance stats for a user.

    If subject_code and classType are provided, returns stats for that
    specific combination; otherwise returns all records for the user.
    """
    records = []
    if subject_code:
        attendance_record = session.exec(
            select(AttendanceStats).where(
                AttendanceStats.user_id == user_id,
                AttendanceStats.subject_code == subject_code,
                AttendanceStats.classType == classType,
            )
        ).first()
        print(
            f"Queried attendance record for user_id={user_id}, subject_code={subject_code}, classType={classType}: {attendance_record}"
        )
        if not attendance_record:
            raise HTTPException(
                status_code=404,
                detail=f"No attendance record found for subject code '{subject_code}'",
            )
        records.append(attendance_record)
        return records
    attendance_records = session.exec(
        select(AttendanceStats).where(AttendanceStats.user_id == user_id)
    ).all()
    if not attendance_records:
        raise HTTPException(
            status_code=404, detail="No attendance records found for this user"
        )
    return attendance_records


# ──────────── PUT ROUTES ────────────


@router.put("/update_slot/{slot_id}")
def update_slot(
    user_id: int,
    day: DayEnum,
    start_time: time,
    end_time: time,
    classType: ClassType,
    subject_code: str,
    updated_slot: TimetableSlots,
    session: Session = Depends(get_session),
):
    """
    Update an existing timetable slot.

    Finds the slot by (user_id, day, start_time, end_time, classType, subject_code),
    checks for conflicts with the new values, then applies the update.
    """
    slot = session.exec(
        select(TimetableSlots).where(
            TimetableSlots.user_id == user_id,
            TimetableSlots.day == day,
            TimetableSlots.start_time == start_time,
            TimetableSlots.end_time == end_time,
            TimetableSlots.class_type == classType,
            TimetableSlots.subject_code == subject_code,
        )
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    conflict_slot = session.exec(
        select(TimetableSlots).where(
            TimetableSlots.user_id == user_id,
            TimetableSlots.day == updated_slot.day,
            TimetableSlots.id != slot.id,
            TimetableSlots.start_time < updated_slot.end_time,
            TimetableSlots.end_time > updated_slot.start_time,
        )
    ).first()
    if conflict_slot:
        raise HTTPException(
            status_code=400,
            detail="Updated slot conflicts with an existing slot",
        )
    slot.day = updated_slot.day
    slot.start_time = updated_slot.start_time
    slot.end_time = updated_slot.end_time
    slot.class_type = updated_slot.class_type
    slot.subject_code = updated_slot.subject_code

    session.add(slot)
    session.commit()
    session.refresh(slot)
    return {"message": "Timetable slot updated successfully!"}


# ──────────── DELETE ROUTES ────────────


@router.delete("/delete_subject")
def delete_subject(
    user: User, subject_code: str, session: Session = Depends(get_session)
):
    """Delete a subject. Only users with adminStatus=True may perform this."""
    if not user.adminStatus:
        raise HTTPException(status_code=403, detail="Only admins can delete subjects")
    subject = session.exec(
        select(Subjects).where(Subjects.subject_code == subject_code)
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    session.delete(subject)
    session.commit()
    return {"message": f"Subject with code '{subject_code}' deleted successfully!"}


@router.delete("/delete_slot/{slot_id}")
def delete_slot(
    user_id: int,
    subject_code: str,
    day: DayEnum,
    start_time: time,
    end_time: time,
    classType: ClassType,
    session: Session = Depends(get_session),
):
    """Delete a single timetable slot identified by its composite key."""
    slot = session.exec(
        select(TimetableSlots).where(
            TimetableSlots.user_id == user_id,
            TimetableSlots.subject_code == subject_code,
            TimetableSlots.day == day,
            TimetableSlots.start_time == start_time,
            TimetableSlots.end_time == end_time,
            TimetableSlots.class_type == classType,
        )
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    session.delete(slot)
    session.commit()
    return {"message": "Timetable slot deleted successfully!"}


@router.get("/attendance_log_for_date")
def get_attendance_log_for_date(
    user_id: int, date_of_slot: date, session: Session = Depends(get_session)
):
    """Return all attendance logs for a user on a specific date."""
    logs = get_attendance_logs(user_id, date_of_slot, session)
    print(
        f"Queried attendance logs for user_id={user_id} on date={date_of_slot}: {logs}"
    )
    return logs
