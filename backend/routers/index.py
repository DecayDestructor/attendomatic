from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.config import settings
from backend.db.database import get_session
from sqlmodel import Session, select
from backend.db.models import *
from backend.routers.attendanceRouter import (
    add_slot,
    create_subject,
    delete_subject,
    update_slot,
    get_attendance_stats,
    delete_slot,
)
from backend.utils.attendanceManagement import get_daily_timetable_user, mark_attendance
from backend.utils.userManagement import read_user
import json
from groq import Groq
from typing import Literal
from enum import Enum
from typing import Literal, Optional, List
from pydantic import BaseModel

# -------------------------------
# Intent Enum
# -------------------------------


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


router = APIRouter()
client = Groq(api_key=settings.GROQ_API_KEY)

import parsedatetime as pdt

from datetime import datetime

from backend.utils.date_extract import extract_dates_from_shift_message


@router.get("/main")
def read_main(
    user_message: str, contact_id: str, session: Session = Depends(get_session)
):
    try:
        user = read_user(contact_id, session)
    except HTTPException as e:
        raise HTTPException(
            status_code=400, detail="User not found. Please register first."
        )
    # Parse date
    extracted = extract_dates_from_shift_message(user_message)
    all_texts = [x[0] for x in extracted]
    all_dates = [x[1] for x in extracted]

    all_days = [(dates, dates.strftime("%a")) for dates in all_dates]
    all_weekdays = [date.strftime("%a") for date in all_dates]
    all_timetables = []
    for days in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        try:
            timetable = get_daily_timetable_user(user.id, days, session)
            if timetable:
                timetable_str = "\n".join(
                    [
                        f"{days}: {slot.start_time}-{slot.end_time} {slot.subject_code} ({slot.class_type})"
                        for slot in timetable
                    ]
                )
            all_timetables.append(timetable_str)
        except HTTPException:
            continue
    weekly_timetable_str = "\n".join(all_timetables)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an intelligent attendance management assistant. "
                "Your job is to read user messages and convert them into a strict JSON object that follows the LLMMultiResponse schema.\n\n"
                "Each user message may contain one or more separate actions (e.g., mark attendance, add slot, get stats, etc.). "
                "For every distinct operation mentioned by the user, create exactly **one separate object** in the 'actions' array.\n\n"
                "=== INTENT MAPPING RULES ===\n"
                "You must map each user instruction to exactly one of these intents:\n"
                "- create_subject\n"
                "- add_slot\n"
                "- mark_attendance\n"
                "- update_slot\n"
                "- get_daily_timetable\n"
                "- get_attendance_stats\n"
                "- delete_subject\n\n"
                "=== ACTION GENERATION RULES ===\n"
                "1. Each action in 'actions' must correspond to **exactly one intent**.\n"
                "2. If a user message contains multiple intents (e.g., 'mark attendance and get my stats'), output multiple actions — one for each.\n"
                "3. Never merge multiple intents or tasks into one action.\n"
                "4. Each action must have a valid HTTP method ('GET', 'POST', 'PUT', or 'DELETE') based on the operation.\n"
                "5. All optional fields in 'params' must be filled with null if not applicable.\n\n"
                "=== ATTENDANCE RULES ===\n"
                "1. If the user says anything like 'all lectures', 'all classes', 'attended everything', or 'I attended all classes', "
                "mark all lectures in the timetable as 'present'. Create one 'mark_attendance' action per slot, filling subject_code, classType, day_of_slot, start_time, end_time, and status.\n"
                "2. If the user says 'all lectures except X', mark all lectures as 'present' except those containing X in subject_code or class_type (which are 'absent'). Generate one action per slot accordingly.\n"
                "3. If the user lists only specific lectures, mark only those as 'present'.\n"
                "4. Do not mark excluded subjects as present.\n"
                "5. Always include date_of_slot.\n\n"
                "=== SLOT UPDATE RULES ===\n"
                "1. If the user says something like 'My DBMS Lab was shifted from Monday to Tuesday', create an action with intent 'update_slot'.\n"
                "   Include in 'params' the original slot’s subject_code, classType, old start_time, old end_time, and old day_of_slot. "
                "Include 'updatedSlot' containing the new day_of_slot, and optionally new start_time or end_time if mentioned.\n"
                "2. If the user says 'My OS lecture was moved to 10 AM', update only the time fields.\n"
                "3. Do not create or delete slots unless explicitly told ('add a new lecture', 'delete my ML lab').\n\n"
                "=== ATTENDANCE STATS RULES ===\n"
                "1. If the user asks for 'attendance stats', 'attendance percentage', or 'how many classes I attended', create an action with intent 'get_attendance_stats'.\n"
                "2. If the user specifies a subject or class type (e.g., 'OS labs' or 'DBMS lectures'), include those in params; otherwise, set to null.\n"
                "3. If both subject and classType are provided, return stats for that specific subject and class type.\n"
                "4. If only subject is provided, return stats for all class types of that subject.\n"
                "5. If neither is provided, set both to null.\n"
                "6. Do not assume subjects not in the timetable or database.\n\n"
                "=== CONFUSION FLAG ===\n"
                "1. If the user message is ambiguous or contains conflicting instructions, set 'confusion_flag = True' in the params.\n"
                "2. Do not assume the intent in ambiguous cases. Leave other fields as null if unsure.\n"
                "3. The system will prompt the user to clarify before executing any action.\n\n"
                "=== OUTPUT REQUIREMENTS ===\n"
                "1. Output **valid JSON only**, following the LLMMultiResponse schema (no natural language explanations).\n"
                "2. Each element in 'actions' must contain exactly one intent and one HTTP method.\n"
                "3. Never merge multiple tasks into a single params.\n"
                "4. When marking multiple classes or slots, output **one action per slot**.\n"
                "5. If something is missing or not applicable, set it to null."
            ),
        },
        {
            "role": "system",
            "content": (
                f"The user's timetable is as follows:\n{weekly_timetable_str}\n"
            ),
        },
        {
            "role": "system",
            "content": (
                "The user's message has been analyzed for date and day references. "
                "Below is a list of extracted phrases along with their parsed dates:\n\n"
                + "\n".join(
                    f"- '{text}' -> {date.strftime('%Y-%m-%d')} ({weekday})"
                    for text, date, weekday in zip(all_texts, all_dates, all_weekdays)
                )
                + "\n\nUse this information to determine the days or dates relevant for actions."
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    response = client.chat.completions.create(
        model="moonshotai/kimi-k2-instruct-0905",
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "product_review",
                "schema": LLMMultiResponse.model_json_schema(),
            },
        },
    )
    # print("LLM Response:", response)
    review = LLMMultiResponse.model_validate(
        json.loads(response.choices[0].message.content)
    )
    print("Review : ", review)
    final_response = []
    for item in review.actions:
        function_call = item.intent
        if function_call == IntentEnum.CREATE_SUBJECT:
            try:
                create_subject(
                    subject=Subjects(
                        subject_code=item.params.subject_code,
                        subject_name=item.params.subject_name,
                    ),
                    session=session,
                )
                final_response.append(
                    f"Subject created successfully. {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(f"Failed to create subject. {e.detail}")
        elif function_call == IntentEnum.ADD_SLOT:
            try:
                add_slot(
                    slots=TimetableSlots(
                        user_id=user.id,
                        day=item.params.day_of_slot,
                        start_time=item.params.start_time,
                        end_time=item.params.end_time,
                        subject_code=item.params.subject_code,
                        class_type=item.params.classType,
                    ),
                    session=session,
                )
                final_response.append(
                    f"Slot added successfully for {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(f"Failed to add slot. {e.detail}")
        elif function_call == IntentEnum.MARK_ATTENDANCE:
            try:
                day_of_week = item.params.day_of_slot
                old_date = item.params.date_of_slot
                mark_attendance(
                    user_id=user.id,
                    subject_code=item.params.subject_code,
                    day=item.params.day_of_slot or day_of_week,
                    start_time=item.params.start_time,
                    end_time=item.params.end_time,
                    status=item.params.status,
                    classType=item.params.classType,
                    session=session,
                    date_of_slot=old_date,
                )
                final_response.append(
                    f"Attendance marked successfully for {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(
                    f"Failed to mark attendance for {item.params.subject_code} {item.params.classType}. {e.detail}"
                )
        elif function_call == IntentEnum.GET_DAILY_TIMETABLE:
            try:
                timetable = get_daily_timetable_user(
                    user.id, item.params.day_of_slot, session
                )
                if not timetable:
                    final_response.append(
                        f"No timetable available for {item.params.day_of_slot}."
                    )
                else:
                    timetable_str = "\n".join(
                        [
                            f"{idx+1}. {slot.start_time}-{slot.end_time} {slot.subject_code} - {slot.class_type}"
                            for idx, slot in enumerate(timetable)
                        ]
                    )
                    final_response.append(
                        f"Timetable for {item.params.day_of_slot}:\n{timetable_str}"
                    )
            except HTTPException as e:
                final_response.append(f"Failed to retrieve timetable. {e.detail}")
        elif function_call == IntentEnum.UPDATE_SLOT:
            try:
                update_slot(
                    user_id=user.id,
                    day=item.params.day_of_slot,
                    start_time=item.params.start_time,
                    end_time=item.params.end_time,
                    subject_code=item.params.subject_code,
                    classType=item.params.classType,
                    updated_slot=item.params.updatedSlot,
                    session=session,
                )
                final_response.append(
                    f"Slot updated successfully for {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(f"Failed to update slot. {e.detail}")
        elif function_call == IntentEnum.DELETE_SUBJECT:
            try:
                delete_subject(
                    user=user,
                    subject_code=item.params.subject_code,
                    session=session,
                )
                final_response.append(
                    f"Subject deleted successfully. {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(f"Failed to delete subject. {e.detail}")
        elif function_call == IntentEnum.GET_ATTENDANCE_STATS:
            try:
                attendance_record = get_attendance_stats(
                    user_id=user.id,
                    session=session,
                    subject_code=item.params.subject_code or None,
                    classType=item.params.classType or None,
                )
                for record in attendance_record:
                    final_response.append(
                        f"Attendance stats for {record.subject_code} {record.classType}: {record.total_classes} total classes, {record.attended_classes} attended classes."
                    )
            except HTTPException as e:
                final_response.append(
                    f"Failed to retrieve attendance stats. {e.detail}"
                )
        elif function_call == IntentEnum.DELETE_SLOT:
            try:
                delete_slot(
                    user_id=user.id,
                    day=item.params.day_of_slot,
                    start_time=item.params.start_time,
                    end_time=item.params.end_time,
                    classType=item.params.classType,
                    subject_code=item.params.subject_code,
                    session=session,
                )
                final_response.append(
                    f"Slot deleted successfully for {item.params.subject_code} "
                )
            except HTTPException as e:
                final_response.append(f"Failed to delete slot. {e.detail}")
        elif item.params.confusion_flag:
            final_response.append(
                f"I'm sorry, I couldn't understand your request regarding the following request: {item}. Could you please clarify?"
            )
    print("Review : ", review)
    return {"review": review, "message": "\n".join(final_response)}
