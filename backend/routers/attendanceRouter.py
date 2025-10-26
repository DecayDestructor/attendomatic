from fastapi import APIRouter, Depends, HTTPException
from requests import session
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import *
from backend.utils.userManagement import read_user
from backend.utils.attendanceManagement import (
    get_daily_timetable_user,
    mark_attendance,
)
import json

router = APIRouter()


# POST ROUTES
@router.post("/create_subject")
def create_subject(subject: Subjects, session: Session = Depends(get_session)):
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
    # check for conflicting slots
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


# GET ROUTES

from backend.db.models import DayEnum


@router.get("/daily_timetable/{user_id}/{day}")
def get_daily_timetable(
    user_id: int, day: DayEnum, session: Session = Depends(get_session)
):
    return get_daily_timetable_user(user_id, day, session)


@router.get("/attendance_stat/{user_id}")
def get_attendance_stats(
    user_id: int,
    session: Session = Depends(get_session),
    subject_code: str | None = None,
    classType: ClassType | None = None,
):
    records = []
    if subject_code:
        attendance_record = session.exec(
            select(AttendanceStats).where(
                AttendanceStats.user_id == user_id,
                AttendanceStats.subject_code == subject_code,
                AttendanceStats.classType == classType,
            )
        ).first()
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


# PUT ROUTES
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


# DELETE ROUTES
@router.delete("/delete_subject")  # delete a single subject
def delete_subject(
    user: User, subject_code: str, session: Session = Depends(get_session)
):
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


@router.delete("/delete_slot/{slot_id}")  # delete a single timetable slot
def delete_slot(
    user_id: int,
    subject_code: str,
    day: DayEnum,
    start_time: time,
    end_time: time,
    classType: ClassType,
    session: Session = Depends(get_session),
):
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
