"""Turn raw readings into CSV values and check them against each field's format."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "s": "5", "B": "8", "g": "9", "q": "9", "Z": "2", "z": "2"})


@dataclass
class Normalized:
    value: str
    valid: bool
    note: str = ""


def _date(raw: str, today: date) -> Normalized:
    parts = re.findall(r"\d+", raw.translate(DIGIT_LOOKALIKES))
    note = ""
    if len(parts) == 2:
        parts.append(str(today.year))
        note = "year not on label; assumed current year"
    if len(parts) != 3:
        return Normalized(raw, False, "not a date")
    month, day, year = (int(p) for p in parts)
    year += 2000 if year < 100 else 0
    try:
        parsed = date(year, month, day)
    except ValueError:
        return Normalized(raw, False, "impossible date")
    if parsed > today:
        return Normalized(f"{month}/{day}/{year}", False, "date is in the future")
    return Normalized(f"{month}/{day}/{year}", True, note)


def _digits(raw: str, prefix: str) -> Normalized:
    digits = re.sub(r"\D", "", raw.translate(DIGIT_LOOKALIKES))
    return Normalized(f"{prefix}{digits}", 3 <= len(digits) <= 5)


def _serial(raw: str) -> Normalized:
    compact = re.sub(r"\s", "", raw).upper()
    body = re.sub(r"^[A-Z]{0,3}", "", compact)
    digits = re.sub(r"\D", "", body.translate(DIGIT_LOOKALIKES))
    return Normalized(f"PP{digits}", 7 <= len(digits) <= 9)


def normalize(raw: str, spec: dict, today: date) -> Normalized:
    kind = spec["format"]
    if kind == "date":
        return _date(raw, today)
    if kind == "digits":
        return _digits(raw, spec.get("prefix", ""))
    if kind == "serial":
        return _serial(raw)
    text = " ".join(raw.split()).strip(" .,:;")
    return Normalized(text, bool(text))
