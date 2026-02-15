"""
Database table definitions (SQLModel) and Pydantic schemas used by the LLM.

Contains:
- User, Subjects, TimetableSlots, AttendanceLog, AttendanceStats, PendingAction  (DB tables)
- IntentEnum, LLMResponseSchema, LLMMultiResponse  (Pydantic models for LLM output)
- Params, Slot, UpdatedSlot  (supporting parameter schemas)
"""

from typing import Annotated
from fastapi.params import Depends
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select


from sqlmodel import Field, SQLModel


# ───────────────────────────────────────────────
# Database Table Models
# ───────────────────────────────────────────────


class User(SQLModel, table=True):
    """A registered student. Identified externally by their Telegram contact_id."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    uid: str = Field(index=True)  # University / roll-number ID
    name: str = Field()
    div: str = Field()  # Division (e.g. "A", "B")
    year: int = Field()  # Academic year (1-4)
    batch: str = Field()  # Lab batch (e.g. "B1")
    branch: str = Field(default="COMPS")  # Branch / department
    contact_id: str = Field(index=True, unique=True)  # Telegram user ID (string)
    adminStatus: bool = Field(default=False)  # True if user has admin privileges


class Subjects(SQLModel, table=True):
    """A subject (course) that can appear in timetable slots."""

    __tablename__ = "subjects"
    id: int | None = Field(default=None, primary_key=True)
    subject_code: str = Field(index=True, unique=True)  # Short code, e.g. "DC"
    subject_name: str = Field(
        index=True, unique=True
    )  # Full name, e.g. "Digital Communication"


from datetime import time, date
from enum import Enum


class DayEnum(str, Enum):
    """Days of the week used for timetable slots."""

    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class ClassType(str, Enum):
    """Type of class session."""

    LECTURE = "lecture"
    LAB = "lab"
    TUTORIAL = "tutorial"


class TimetableSlots(SQLModel, table=True):
    """
    A single timetable slot for a user on a given day.

    Uniqueness: one user cannot have two slots with the same day + start + end.
    is_temporary=True means the slot was auto-created when marking attendance
    for a class not in the regular timetable.
    """

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
    is_temporary: bool = Field(default=False)


class AttendanceStatus(str, Enum):
    """Possible attendance statuses for a class."""

    PRESENT = "present"
    ABSENT = "absent"
    CANCELLED = "cancelled"  # Class was cancelled — doesn't affect totals


from datetime import date


class AttendanceLog(SQLModel, table=True):
    """A single attendance record tying a timetable slot to a date and status."""

    __tablename__ = "attendance_logs"

    id: int | None = Field(default=None, primary_key=True)
    slot_id: Annotated[int, Field(foreign_key="timetable_slots.id", ondelete="CASCADE")]
    status: AttendanceStatus = Field(index=True)
    date_log: date = Field(index=True)


class AttendanceStats(SQLModel, table=True):
    """
    Aggregated attendance counters per user + subject + class type.

    Updated incrementally whenever attendance is marked or corrected.
    """

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
    """
    Stores an LLM-parsed action that awaits user confirmation.

    Flow: bot parses message → creates PendingAction (status='pending')
    → user replies yes/no → status becomes 'confirmed' or 'cancelled'.
    Automatically expires after 5 minutes.
    """

    __tablename__ = "pending_actions"

    id: Optional[int] = Field(default=None, primary_key=True)

    contact_id: str = Field(index=True)  # Telegram user ID

    intent_json: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False)
    )  # Serialized LLMMultiResponse

    # Human-readable confirmation message sent to the user
    confirmation_message: str = Field(nullable=False)

    status: str = Field(default="pending", index=True)

    # timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=5), index=True
    )


# ───────────────────────────────────────────────
# LLM Intent / Response Schemas (Pydantic only)
# ───────────────────────────────────────────────

from typing import Literal
from enum import Enum
from typing import Literal, Optional, List
from pydantic import BaseModel


class IntentEnum(str, Enum):
    """All possible intents the LLM can return for a user message."""

    CREATE_SUBJECT = "create_subject"
    ADD_SLOT = "add_slot"
    MARK_ATTENDANCE = "mark_attendance"
    GET_DAILY_TIMETABLE = "get_daily_timetable"
    GET_ATTENDANCE_STATS = "get_attendance_stats"
    UPDATE_SLOT = "update_slot"
    DELETE_SUBJECT = "delete_subject"
    DELETE_SLOT = "delete_slot"
    TEMPORARY_SLOT = "temporary_slot"


# ───────────────────────────────────────────────
# Supporting parameter models
# ───────────────────────────────────────────────
from datetime import date, datetime, time
from backend.db.models import DayEnum, ClassType, AttendanceStatus


class UpdatedSlot(BaseModel):
    """Fields that can be changed when updating an existing timetable slot."""

    day: Optional[DayEnum] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    subject_code: Optional[str] = None
    class_type: Optional[ClassType] = None


class Slot(BaseModel):
    """Describes a single timetable slot (used in add_slot actions)."""

    user_id: int
    date_of_slot: Optional[date] = None
    start_time: time
    end_time: time
    subject_code: str
    class_type: ClassType


# ───────────────────────────────────────────────
# Main parameters schema sent per action
# ───────────────────────────────────────────────


class Params(BaseModel):
    """All possible parameters for any intent. Unused fields are null."""

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
    confusion_flag: Optional[bool] = (
        None  # True when the LLM can't understand the request
    )


# ───────────────────────────────────────────────
# LLM output schema
# ───────────────────────────────────────────────


class LLMResponseSchema(BaseModel):
    """A single action parsed from the user's message."""

    intent: IntentEnum
    method: Literal["GET", "POST", "PUT", "DELETE"]
    params: Params


class LLMMultiResponse(BaseModel):
    """
    Top-level LLM output: one or more actions plus a human-readable
    confirmation message to send back to the user.
    """

    actions: List[LLMResponseSchema]
    confirmation_message: str
