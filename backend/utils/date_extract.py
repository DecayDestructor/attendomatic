import re
import parsedatetime as pdt
from datetime import datetime

cal = pdt.Calendar()


def extract_dates_from_shift_message(message: str, base: datetime = None):
    """
    Extract dates and day references including possessives
    (like "tomorrow's", "Monday's", etc.)

    Supports:
    - Weekdays: Monday, Tuesday, etc. (with optional next/last/this)
    - Relative: today, tomorrow, yesterday
    - Dates: 27th October 2025, 15 Nov, etc.
    - Possessives: tomorrow's, Monday's, etc.
    """
    if not message or not message.strip():
        return []

    if base is None:
        base = datetime.now()

    # Regex for dates and days only
    date_pattern = re.compile(
        r"\b(?:on\s+)?("  # optional "on"
        r"(?:next|last|this)?\s*"  # optional modifiers
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"  # weekdays
        r"|today|tomorrow|yesterday"  # relative simple words
        r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:\s+\d{4})?"  # "27th October 2025"
        r")(?:'s)?",  # optional possessive
        re.IGNORECASE,
    )

    match = date_pattern.search(message)
    if not match:
        return []

    date_text = match.group(1).strip()

    # Parse using parsedatetime
    parsed_dt, success = cal.parseDT(date_text, base)
    if not success:
        # Skip and continue with remaining text
        remaining_text = message[match.end() :]
        return extract_dates_from_shift_message(remaining_text, base=base)

    # Recurse on remaining text
    remaining_text = message[match.end() :]
    remaining_dates = extract_dates_from_shift_message(remaining_text, base=base)

    return [(date_text, parsed_dt)] + remaining_dates


if __name__ == "__main__":
    test_messages = [
        "tomorrow's timetable",
        "yesterday's attendance",
        "Monday's schedule",
        "next Friday's classes",
        "I need today's and tomorrow's assignments",
        "Meeting on 27th October 2025",
        "yesterday's notes and next Tuesday",
    ]

    for msg in test_messages:
        print(f"\nMessage: {msg}")
        extracted = extract_dates_from_shift_message(msg)
        for text, dt in extracted:
            print(f"  → '{text}' = {dt.strftime('%Y-%m-%d %A')}")
