"""
Natural-language date extraction utility.

Uses regex + parsedatetime to pull date/day references out of messages
(e.g. "tomorrow", "next Monday", "27th October 2025") and resolve them
to Python datetime objects.  Supports possessives ("tomorrow's").
"""

import re
import parsedatetime as pdt
from datetime import datetime

cal = pdt.Calendar()


def extract_dates_from_shift_message(message: str, base: datetime = None):
    """
    Recursively extract all date/day phrases from a message.

    Returns a list of (matched_text, parsed_datetime) tuples.

    Supported patterns:
    - Weekdays: Monday, Tuesday, etc. (with optional next/last/this)
    - Relative words: today, tomorrow, yesterday
    - Explicit dates: 27th October 2025, 15 Nov, etc.
    - Possessives: tomorrow's, Monday's, etc.
    """
    if not message or not message.strip():
        return []

    if base is None:
        base = datetime.now()

    # Regex pattern matching day names, relative words, and explicit date formats
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

    # Use parsedatetime to resolve the matched text to a datetime
    parsed_dt, success = cal.parseDT(date_text, base)
    if not success:
        # If parsing failed, skip this match and continue with the rest
        remaining_text = message[match.end() :]
        return extract_dates_from_shift_message(remaining_text, base=base)

    # Recurse on the remaining text after the matched portion
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
