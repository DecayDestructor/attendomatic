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
    statement = select(User)
    results = session.exec(statement)
    users = results.all()
    return users


from backend.db.models import DayEnum


def get_daily_timetable_user(
    user_id: int, day: DayEnum, session: Session = Depends(get_session)
):
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
        # create a temporary slot with the given details and mark attendance for it
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
    # Check if attendance has already been marked for this slot and date along with the same status
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
    # Check if attendance has already been marked for this slot and date with a different status
    previously_marked_log = session.exec(
        select(AttendanceLog).where(
            AttendanceLog.slot_id == slot.id,
            AttendanceLog.date_log == date_of_slot,
        )
    ).first()
    # Get or create attendance stats for the subject and class type
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
    # If attendance was previously marked with a different status, we need to reset the counts before marking the new status
    # We are deleting the previously marked log and adjusting the counts based on its status before marking the new attendance status
    if previously_marked_log:
        if previously_marked_log.status == AttendanceStatus.PRESENT:
            attendance.attended_classes -= 1
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.ABSENT:
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.CANCELLED:
            pass
        session.delete(previously_marked_log)

    # Now we can mark the new attendance status and update the counts accordingly
    attendance_log = AttendanceLog(
        slot_id=slot.id,
        status=status,
        date_log=date_of_slot,
    )
    # Update attendance stats based on the new status
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
