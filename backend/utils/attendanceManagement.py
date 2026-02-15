"""
Core attendance and timetable logic.

Contains the main business functions called by both the REST routes
and the LLM intent dispatcher:
- get_all_users          — list every user
- get_daily_timetable_user — return regular (non-temporary) slots for a day
- mark_attendance        — record present/absent/cancelled with auto-stat tracking
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import (
    AttendanceLog,
    AttendanceStats,
    Subjects,
    TimetableSlots,
    User,
)


def get_all_users(session: Session = Depends(get_session)):
    """Return all registered users."""
    statement = select(User)
    results = session.exec(statement)
    users = results.all()
    return users


from backend.db.models import DayEnum


def get_daily_timetable_user(
    user_id: int, day: DayEnum, session: Session = Depends(get_session)
):
    """Return the user's non-temporary timetable slots for a given day of the week."""
    statement = select(TimetableSlots).where(
        TimetableSlots.user_id == user_id,
        TimetableSlots.day == day,
        TimetableSlots.is_temporary == False,
    )
    results = session.exec(statement)
    timetable = results.all()
    print(day, timetable)
    if not timetable:
        raise HTTPException(status_code=404, detail="No timetable found for " + day)
    return timetable


from datetime import date, time

from backend.db.models import ClassType, DayEnum, AttendanceStatus


def mark_attendance(
    user_id: int,
    subject_code: str,
    day: DayEnum,
    start_time: time,
    end_time: time,
    status: AttendanceStatus,
    classType: ClassType,
    session: Session = Depends(get_session),
    date_of_slot: date = date.today(),
):
    """
    Mark attendance for a specific class on a given date.

    Behaviour:
    - If the timetable slot doesn't exist, a temporary slot is auto-created.
    - If attendance was already marked with the SAME status, raises 400.
    - If attendance was marked with a DIFFERENT status, the old record is
      replaced and the AttendanceStats counters are adjusted accordingly.
    - AttendanceStats (total_classes, attended_classes) are updated
      incrementally based on the new status.
    """
    # print everything
    print(
        f"Marking attendance for user_id: {user_id}, subject_code: {subject_code}, day: {day}, start_time: {start_time}, end_time: {end_time}, status: {status}, classType: {classType}, date_of_slot: {date_of_slot}"
    )
    # Get the timetable slot for the given parameters
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
        # Slot not in regular timetable — create a temporary one on the fly
        temp_slot = TimetableSlots(
            user_id=user_id,
            subject_code=subject_code,
            day=day,
            start_time=start_time,
            end_time=end_time,
            class_type=classType,
            is_temporary=True,
            date_of_slot=date_of_slot,
        )
        session.add(temp_slot)
        session.commit()
        session.refresh(temp_slot)
        slot = temp_slot
    # Prevent duplicate attendance with the same status
    existing_log = session.exec(
        select(AttendanceLog).where(
            AttendanceLog.slot_id == slot.id,
            AttendanceLog.date_log == date_of_slot,
            AttendanceLog.status == status,
        )
    ).first()
    if existing_log:
        raise HTTPException(
            status_code=400, detail="Attendance already marked for this class"
        )
    # Check if there's a previous record with a different status (for correction)
    previously_marked_log = session.exec(
        select(AttendanceLog).where(
            AttendanceLog.slot_id == slot.id,
            AttendanceLog.date_log == date_of_slot,
        )
    ).first()
    # Get or create the running attendance stats row for this user + subject + classType
    attendance = session.exec(
        select(AttendanceStats).where(
            AttendanceStats.user_id == user_id,
            AttendanceStats.subject_code == subject_code,
            AttendanceStats.classType == classType,
        )
    ).first()

    if not attendance:
        attendance = AttendanceStats(
            user_id=user_id,
            subject_code=subject_code,
            total_classes=0,
            attended_classes=0,
            classType=classType,
        )
        session.add(attendance)
    # If correcting a previous status, reverse its effect on the counters first
    if previously_marked_log:
        if previously_marked_log.status == AttendanceStatus.PRESENT:
            attendance.attended_classes -= 1
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.ABSENT:
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.CANCELLED:
            pass
        session.delete(previously_marked_log)

    # Create the new attendance log entry
    attendance_log = AttendanceLog(
        slot_id=slot.id,
        status=status,
        date_log=date_of_slot,
    )
    # Apply the new status to the cumulative counters
    if status == AttendanceStatus.PRESENT:
        attendance.total_classes += 1
        attendance.attended_classes += 1
    elif status == AttendanceStatus.ABSENT:
        attendance.total_classes += 1
    elif status == AttendanceStatus.CANCELLED:
        pass
    else:
        raise HTTPException(status_code=400, detail="Invalid attendance status")
    session.add_all([attendance, attendance_log])
    session.commit()
    session.refresh(attendance_log)
    session.refresh(attendance)
    return attendance_log
