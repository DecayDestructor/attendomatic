"""
Index router — the brain of the bot.

1. `read_main`    — Takes a natural-language user message, extracts dates,
                     builds context (timetable + parsed dates), calls the Groq LLM,
                     and stores the result as a PendingAction awaiting confirmation.

2. `perform_intent` — Executes confirmed actions by dispatching each intent
                       to the appropriate CRUD function.
"""

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
from backend.utils.attendanceManagement import (
    get_daily_timetable_user,
    mark_attendance,
    get_attendance_logs,
)
from backend.utils.userManagement import read_user
from backend.utils.pending_actions import *
import json
from groq import Groq
from backend.utils.verify_secret_token import verify_api_secret


# All routes in this router require the X-Api-Secret-Key header
router = APIRouter(dependencies=[Depends(verify_api_secret)])
client = Groq(api_key=settings.GROQ_API_KEY)

import parsedatetime as pdt

from datetime import datetime

from backend.utils.date_extract import extract_dates_from_shift_message


@router.get("/main")
def read_main(
    user_message: str, contact_id: str, session: Session = Depends(get_session)
):
    """
    Parse a natural-language message into structured actions via the Groq LLM.

    Steps:
    1. Validate user exists.
    2. Extract date references from the message.
    3. Fetch the user's full weekly timetable for LLM context.
    4. Send everything to the LLM and parse the JSON response.
    5. Store the parsed intent as a PendingAction and return a confirmation message.
    """
    try:
        user = read_user(contact_id, session)
    except HTTPException as e:
        raise HTTPException(
            status_code=400, detail="User not found. Please register first."
        )
    # Extract date/day phrases from the user's message
    extracted = extract_dates_from_shift_message(user_message)
    all_texts = [x[0] for x in extracted]
    all_dates = [x[1] for x in extracted]

    all_weekdays = [date.strftime("%a") for date in all_dates]
    all_timetables = []
    # print("Extracted texts:", all_texts)
    # print("Extracted dates:", all_dates)
    print(
        "Below is a list of extracted phrases along with their parsed dates and weekdays:\n\n"
        + "\n".join(
            f"- '{text}' -> Date: {date.strftime('%Y-%m-%d')} Day:({weekday})"
            for text, date, weekday in zip(all_texts, all_dates, all_weekdays)
        )
        + "\n\nUse this information to determine the days or dates relevant for actions."
    )
    for days in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        try:
            timetable = get_daily_timetable_user(user.id, days, session)
            if timetable:
                timetable_str = "\n".join(
                    [
                        f"{days}: {slot.start_time}-{slot.end_time} {slot.subject_code} ({slot.class_type}) {'[TEMP]' if slot.is_temporary else ''}"
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
                "Your ONLY job is to convert user messages into a structured JSON response following the LLMMultiResponse schema.\n\n"
                "CRITICAL: You are in INTENT CONFIRMATION MODE.\n"
                "You MUST NOT answer the user's question.\n"
                "You MUST NOT provide timetable data, attendance stats, or any database information.\n"
                "You MUST ONLY extract intent and ask for confirmation.\n\n"
                "Each user message may contain one or more separate actions. "
                "Create exactly one action object per distinct intent.\n\n"
                "=== INTENT MAPPING RULES ===\n"
                "Map each instruction to exactly one intent:\n"
                "- create_subject\n"
                "- add_slot\n"
                "- mark_attendance\n"
                "- update_slot\n"
                "- get_daily_timetable\n"
                "- get_attendance_stats\n"
                "- delete_subject\n"
                "- get_attendance_logs_for_date\n\n"
                "=== DAY ENUM RULE ===\n"
                "If day_of_slot is present, it MUST be exactly one of:\n"
                "- Mon\n"
                "- Tue\n"
                "- Wed\n"
                "- Thu\n"
                "- Fri\n"
                "- Sat\n"
                "- Sun\n\n"
                "=== DATE INTERPRETATION RULES ===\n"
                "If date text is misspelled, ambiguous, or invalid:\n"
                "- DO NOT guess\n"
                "- DO NOT autocorrect\n"
                "- Set confusion_flag = True\n"
                "- Set date_of_slot = null\n"
                "- Set day_of_slot = null\n\n"
                "=== DATE AND DAY CONSISTENCY RULE ===\n"
                "If date_of_slot is known, you MUST also set day_of_slot.\n"
                "Use the weekday provided in the parsed reference.\n"
                "NEVER leave day_of_slot null if date_of_slot exists.\n\n"
                "Example:\n"
                "'tomorrow' -> 2026-02-16 (Mon)\n"
                "Correct:\n"
                "date_of_slot='2026-02-16'\n"
                "day_of_slot='Mon'\n\n"
                "=== ACTION GENERATION RULES ===\n"
                "1. One intent per action object.\n"
                "2. Multiple intents → multiple action objects.\n"
                "3. Never merge intents.\n"
                "4. HTTP method mapping:\n"
                "   POST → create or mark attendance\n"
                "   GET → retrieve timetable or stats\n"
                "   PUT → update\n"
                "   DELETE → delete\n"
                "5. All params fields must exist.\n"
                "6. start_time and end_time MUST be populated from timetable if matching slot exists.\n"
                "7. start_time and end_time MUST NOT be null if timetable contains the slot.\n\n"
                "=== ATTENDANCE RULES ===\n"
                "If user implies attendance, use status='present'.\n"
                "Always include date_of_slot, day_of_slot, start_time, and end_time if slot exists in timetable.\n\n"
                "=== SLOT TIME RESOLUTION RULE (CRITICAL) ===\n"
                "The user's timetable is provided below and is the authoritative source.\n\n"
                "When intent is mark_attendance, update_slot, or slot-related action:\n"
                "You MUST resolve start_time and end_time from the timetable using:\n"
                "- subject_code\n"
                "- day_of_slot\n"
                "- classType (if available)\n\n"
                "If matching slot exists in timetable:\n"
                "- start_time MUST equal timetable start_time\n"
                "- end_time MUST equal timetable end_time\n"
                "- NEVER leave start_time or end_time null\n\n"
                "Example:\n"
                "Timetable:\n"
                "Tue: BDA lab 09:00–11:00\n\n"
                "User:\n"
                "'Mark BDA lab today attended'\n\n"
                "Correct params:\n"
                "start_time='09:00'\n"
                "end_time='11:00'\n\n"
                "Incorrect params:\n"
                "start_time=null\n"
                "end_time=null\n\n"
                "If no matching slot exists in timetable:\n"
                "- start_time=null\n"
                "- end_time=null\n"
                "- backend will handle temporary slot creation\n\n"
                "=== TEMPORARY SLOT RULES ===\n"
                "If the subject+classType combination does NOT exist in the user's timetable FOR THAT SPECIFIC DAY:\n"
                "- STILL use intent='mark_attendance'\n"
                "- DO NOT use add_slot\n"
                "- DO NOT set confusion_flag\n"
                "- start_time and end_time will be null\n"
                "- In confirmation_message, you MUST explicitly state that this class is NOT in the timetable for that day and a TEMPORARY slot will be created.\n"
                "- Example: 'BDA lab is not in your timetable for Tuesday. A temporary slot will be created and attendance will be marked as attended on Tuesday, 17 February 2026. Is that correct?'\n\n"
                "=== TIMETABLE REQUEST RULE ===\n"
                "If user asks to see timetable:\n"
                "- Use intent='get_daily_timetable'\n"
                "- DO NOT include timetable data in confirmation_message\n\n"
                "=== ATTENDANCE STATS RULE ===\n"
                "If user asks for attendance stats:\n"
                "- Use intent='get_attendance_stats'\n"
                "- DO NOT include stats in confirmation_message\n\n"
                "=== ATTENDANCE LOGS FOR DATE RULE ===\n"
                "If user asks what classes they attended/missed on a specific date:\n"
                "- Use intent='get_attendance_logs_for_date'\n"
                "- Requires date_of_slot and day_of_slot\n"
                "- DO NOT include log data in confirmation_message\n\n"
                "=== CONFUSION RULE ===\n"
                "Set confusion_flag=True ONLY if instruction is ambiguous or invalid.\n\n"
                "=== OUTPUT RULES ===\n"
                "Output VALID JSON ONLY.\n"
                "NO explanations.\n"
                "NO answering questions.\n\n"
                "=== CONFIRMATION MESSAGE RULE ===\n"
                "confirmation_message MUST ONLY confirm intent.\n"
                "DO NOT provide timetable data.\n"
                "DO NOT provide attendance stats.\n"
                "DO NOT provide attendance logs.\n\n"
                "The confirmation MUST be PRECISE and include ALL relevant details so the user can verify:\n\n"
                "For mark_attendance:\n"
                "- Subject code\n"
                "- Class type (lecture/lab/tutorial)\n"
                "- Full date (e.g. 17 February 2026) and day (e.g. Tuesday)\n"
                "- Time slot (start-end) if available in timetable\n"
                "- Status (attended/bunked/cancelled)\n"
                "- Whether a temporary slot will be created (if not in timetable)\n"
                "Example: 'Mark BDA lab on Tuesday, 17 February 2026 (09:00-11:00) as attended. Confirm?'\n\n"
                "For create_subject:\n"
                "- Subject code and subject name\n"
                "Example: 'Create subject BDA (Big Data Analytics). Confirm?'\n\n"
                "For add_slot:\n"
                "- Subject code, class type, day, start time, end time\n"
                "Example: 'Add BDA lab slot on Tuesday from 09:00 to 11:00. Confirm?'\n\n"
                "For update_slot:\n"
                "- What is being updated and from what to what\n"
                "Example: 'Update BDA lab on Tuesday from 09:00-11:00 to 10:00-12:00. Confirm?'\n\n"
                "For delete_subject:\n"
                "- Subject code\n"
                "Example: 'Delete subject BDA and all its slots. Confirm?'\n\n"
                "For get_daily_timetable:\n"
                "- Day being requested\n"
                "Example: 'Fetch your timetable for Tuesday. Confirm?'\n\n"
                "For get_attendance_stats:\n"
                "- Subject code if specified, or 'all subjects'\n"
                "Example: 'Fetch attendance stats for BDA. Confirm?'\n\n"
                "For get_attendance_logs_for_date:\n"
                "- Full date\n"
                "Example: 'Fetch attendance logs for 17 February 2026. Confirm?'\n\n"
                "For MULTIPLE actions, list each action as a numbered item.\n"
                "Example: '1. Mark BDA lab on Tue, 17 Feb 2026 (09:00-11:00) as attended.\\n2. Mark OS lecture on Tue, 17 Feb 2026 (11:00-12:00) as bunked.\\nConfirm?'\n"
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
                "The user's message has been analyzed for date references.\n\n"
                "Extracted references:\n\n"
                + "\n".join(
                    f"- '{text}' -> {date.strftime('%Y-%m-%d')} ({weekday})"
                    for text, date, weekday in zip(all_texts, all_dates, all_weekdays)
                )
                + "\n\nUse these parsed values to fill date_of_slot and day_of_slot.\n"
                "You MUST populate BOTH fields when date exists."
            ),
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    # --- Call Groq LLM with structured JSON output ---
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "product_review",
                "schema": LLMMultiResponse.model_json_schema(),
            },
        },
    )

    # Validate the LLM's JSON output against our Pydantic schema
    review = LLMMultiResponse.model_validate(
        json.loads(response.choices[0].message.content)
    )

    print("LLM Response:", review)

    # Store as a pending action so the user can confirm before execution
    create_pending_action(
        confirmation_message=review.confirmation_message,
        review=review,
        contact_id=contact_id,
        session=session,
    )
    return {
        "review": review,
        "contact_id": contact_id,
        "confirmation_message": review.confirmation_message,
    }


def perform_intent(
    contact_id: str,
    session: Session,
    review: LLMMultiResponse | dict = None,
):
    """
    Execute each action in the confirmed LLM response.

    Iterates over review.actions and dispatches to the matching CRUD function
    (create_subject, add_slot, mark_attendance, etc.).  Collects per-action
    success/failure messages and returns them joined.
    """
    final_response = []

    try:
        user = read_user(contact_id, session)
    except HTTPException:
        raise HTTPException(
            status_code=400, detail="User not found. Please register first."
        )

    # Normalize review into Pydantic model
    if isinstance(review, dict):
        review_model = LLMMultiResponse(**review)
    elif isinstance(review, LLMMultiResponse):
        review_model = review
    else:
        raise ValueError(f"Invalid review type: {type(review)}")

    print("Performing intent for review:", review_model.model_dump())

    for item in review_model.actions:
        if item.params.date_of_slot and not item.params.day_of_slot:
            item.params.day_of_slot = DayEnum(item.params.date_of_slot.strftime("%a"))
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
                is_temp = (
                    item.params.start_time is None and item.params.end_time is None
                )
                day_name = (
                    item.params.day_of_slot.value if item.params.day_of_slot else ""
                )
                temp_note = (
                    f" (not in timetable for {day_name} — temporary slot created)"
                    if is_temp
                    else ""
                )
                final_response.append(
                    f"Attendance marked as {item.params.status.value} for {item.params.subject_code} "
                    f"({item.params.classType.value}) on {item.params.date_of_slot}{temp_note}."
                )
            except HTTPException as e:
                final_response.append(
                    f"Failed to mark attendance for {item.params.subject_code} {item.params.classType.value}. {e.detail}"
                )
        elif function_call == IntentEnum.GET_DAILY_TIMETABLE:
            try:
                timetable = get_daily_timetable_user(
                    user.id, item.params.day_of_slot, session
                )
                if not timetable:
                    final_response.append(
                        f"No timetable available for {item.params.day_of_slot.value}."
                    )
                else:
                    timetable_str = "\n".join(
                        [
                            f"{idx+1}. {slot.start_time}-{slot.end_time} {slot.subject_code} - {slot.class_type.value}"
                            for idx, slot in enumerate(timetable)
                        ]
                    )
                    final_response.append(
                        f"Timetable for {item.params.day_of_slot.value}:\n{timetable_str}"
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
                        f"Attendance stats for {record.subject_code} {record.classType.value}: {record.total_classes} total classes, {record.attended_classes} attended classes."
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
        elif function_call == IntentEnum.GET_ATTENDANCE_LOGS_FOR_DATE:
            try:
                logs = get_attendance_logs(
                    user_id=user.id,
                    date=item.params.date_of_slot,
                    session=session,
                )
                if not logs:
                    final_response.append(
                        f"No attendance records found for {item.params.date_of_slot}."
                    )
                else:
                    logs_str = "\n".join(
                        [
                            f"{idx+1}. {log['slot']['subject_code']} ({log['slot']['class_type']}) "
                            f"{log['slot']['start_time']}-{log['slot']['end_time']} — {log['attendance']['status']}"
                            for idx, log in enumerate(logs)
                        ]
                    )
                    final_response.append(
                        f"Attendance on {item.params.date_of_slot}:\n{logs_str}"
                    )
            except HTTPException as e:
                final_response.append(f"Failed to retrieve attendance logs. {e.detail}")
        elif item.params.confusion_flag:
            final_response.append(
                f"I'm sorry, I couldn't understand your request regarding the following request: {item}. Could you please clarify?"
            )
    return {"review": review, "message": "\n".join(final_response)}
