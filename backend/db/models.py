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


from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class PendingAction(SQLModel, table=True):
    __tablename__ = "pending_actions"

    id: Optional[int] = Field(default=None, primary_key=True)

    contact_id: str = Field(index=True)

    intent_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))

    # Human-readable confirmation message
    confirmation_message: str = Field(nullable=False)

    status: str = Field(default="pending", index=True)

    # timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=5), index=True
    )


# -------------------------------
from typing import Literal
from enum import Enum
from typing import Literal, Optional, List
from pydantic import BaseModel


class IntentEnum(str, Enum):
    CREATE_SUBJECT = "create_subject"
    ADD_SLOT = "add_slot"
    MARK_ATTENDANCE = "mark_attendance"
    GET_DAILY_TIMETABLE = "get_daily_timetable"
    GET_ATTENDANCE_STATS = "get_attendance_stats"
    UPDATE_SLOT = "update_slot"
    DELETE_SUBJECT = "delete_subject"
    DELETE_SLOT = "delete_slot"


# -------------------------------
# Supporting models
# -------------------------------
from datetime import date, datetime, time
from backend.db.models import DayEnum, ClassType, AttendanceStatus


class UpdatedSlot(BaseModel):
    day: Optional[DayEnum] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    subject_code: Optional[str] = None
    class_type: Optional[ClassType] = None


class Slot(BaseModel):
    user_id: int
    date_of_slot: Optional[date] = None
    start_time: time
    end_time: time
    subject_code: str
    class_type: ClassType


# -------------------------------
# Main parameters schema
# -------------------------------


class Params(BaseModel):
    user_id: Optional[int] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    date_of_slot: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[AttendanceStatus] = None
    classType: Optional[ClassType] = None
    slot_id: Optional[int] = None
    updatedSlot: Optional[UpdatedSlot] = None
    day_of_slot: Optional[DayEnum] = None
    confusion_flag: Optional[bool] = None


# -------------------------------
# LLM output schema
# -------------------------------


class LLMResponseSchema(BaseModel):
    intent: IntentEnum
    method: Literal["GET", "POST", "PUT", "DELETE"]
    params: Params


class LLMMultiResponse(BaseModel):
    actions: List[LLMResponseSchema]
    confirmation_message: str
