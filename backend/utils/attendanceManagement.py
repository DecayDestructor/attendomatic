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
        TimetableSlots.user_id == user_id, TimetableSlots.day == day
    )
    results = session.exec(statement)
    timetable = results.all()
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
        raise HTTPException(status_code=404, detail="Timetable slot not found")
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
    previously_marked_log = session.exec(
        select(AttendanceLog).where(
            AttendanceLog.slot_id == slot.id,
            AttendanceLog.date_log == date_of_slot,
        )
    ).first()
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
    if previously_marked_log:
        if previously_marked_log.status == AttendanceStatus.PRESENT:
            attendance.attended_classes -= 1
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.ABSENT:
            attendance.total_classes -= 1
        elif previously_marked_log.status == AttendanceStatus.CANCELLED:
            pass
        session.delete(previously_marked_log)

    attendance_log = AttendanceLog(
        slot_id=slot.id,
        status=status,
        date_log=date_of_slot,
    )

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
