import re
import parsedatetime as pdt
from datetime import datetime

cal = pdt.Calendar()


import re
import parsedatetime as pdt
from datetime import datetime

cal = pdt.Calendar()


def extract_dates_from_shift_message(message: str, base: datetime = None):
    """
    Recursively extract all dates and day references (like 'Monday', 'next Friday',
    '27 October 2025', 'today', 'tomorrow', 'yesterday', etc.) using parsedatetime.

    Args:
        message: input text
        base: base datetime for relative parsing (defaults to now)

    Returns:
        List of tuples: [(matched_text, datetime_object), ...]
    """
    if not message or not message.strip():
        return []

    if base is None:
        base = datetime.now()

    # --- Step 1: Regex to capture various date-like words or phrases ---
    date_pattern = re.compile(
        r"\b(?:on\s+)?("  # optional "on"
        r"(?:next|last|this)?\s*"  # optional modifiers
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"  # weekdays
        r"|today|tomorrow|yesterday"  # relative simple words
        r"|day\s+after\s+tomorrow"  # "day after tomorrow"
        r"|day\s+before\s+yesterday"  # "day before yesterday"
        r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:\s+\d{4})?"  # "27th October 2025"
        r")\b",
        re.IGNORECASE,
    )

    # --- Step 2: Find first match ---
    match = date_pattern.search(message)
    if not match:
        return []

    date_text = match.group(1).strip()

    # --- Step 3: Parse using parsedatetime ---
    parsed_dt, success = cal.parseDT(date_text, base)
    if not success:
        return []

    # --- Step 4: Recurse on the remaining text ---
    remaining_text = message[match.end() :]
    remaining_dates = extract_dates_from_shift_message(remaining_text, base=base)

    return [(date_text, parsed_dt)] + remaining_dates


if __name__ == "__main__":
    test_message = (
        "I will attend all classes today, tomorrow, on Monday, next Tuesday, "
        "and on 27th October 2025 and the day after tomorrow."
    )

    extracted = extract_dates_from_shift_message(test_message)

    print("\n=== FINAL RESULTS ===")
    for text, dt in extracted:
        print(f"Extracted: '{text}' -> {dt}")
