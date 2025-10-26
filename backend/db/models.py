from typing import Annotated
from fastapi.params import Depends
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select


from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    uid: str = Field(index=True)
    name: str = Field()
    div: str = Field()
    year: int = Field()
    batch: str = Field()
    branch: str = Field(default="COMPS")
    contact_id: str = Field(index=True, unique=True)
    adminStatus: bool = Field(default=False)


class Subjects(SQLModel, table=True):
    __tablename__ = "subjects"
    id: int | None = Field(default=None, primary_key=True)
    subject_code: str = Field(index=True, unique=True)
    subject_name: str = Field(index=True, unique=True)


from datetime import time, date
from enum import Enum


class DayEnum(str, Enum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class ClassType(str, Enum):
    LECTURE = "lecture"
    LAB = "lab"
    TUTORIAL = "tutorial"


class TimetableSlots(SQLModel, table=True):
    __tablename__ = "timetable_slots"
    __table_args__ = (UniqueConstraint("user_id", "day", "start_time", "end_time"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    day: DayEnum = Field(index=True)
    start_time: time
    end_time: time
    class_type: ClassType = Field()
    subject_code: str = Field(
        foreign_key="subjects.subject_code", index=True, ondelete="CASCADE"
    )


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    CANCELLED = "cancelled"


from datetime import date


class AttendanceLog(SQLModel, table=True):
    __tablename__ = "attendance_logs"

    id: int | None = Field(default=None, primary_key=True)
    slot_id: Annotated[int, Field(foreign_key="timetable_slots.id", ondelete="CASCADE")]
    status: AttendanceStatus = Field(index=True)
    date_log: date = Field(index=True)


class AttendanceStats(SQLModel, table=True):
    __tablename__ = "attendance_stats"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    subject_code: str = Field(
        foreign_key="subjects.subject_code", index=True, ondelete="CASCADE"
    )
    classType: ClassType = Field()
    total_classes: int = Field(default=0)
    attended_classes: int = Field(default=0)
