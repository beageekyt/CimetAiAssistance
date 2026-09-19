"""Per-field validation/normalisation. The LLM only converses; every answer
that gets stored has passed through here first, so the server is the source
of truth on data quality.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
YES_WORDS = {"yes", "yep", "yeah", "sure", "correct", "go ahead", "ok", "okay", "affirmative", "please do"}
NO_WORDS = {"no", "nope", "nah", "don't", "do not", "stop", "not interested", "negative"}


@dataclass
class ValidationResult:
    ok: bool
    value: Optional[str] = None
    error: Optional[str] = None


def _contains_any(text: str, words: set[str]) -> bool:
    t = text.lower().strip()
    return any(w in t for w in words)


def validate_yes_no(raw: str) -> ValidationResult:
    t = raw.lower().strip()
    if _contains_any(t, NO_WORDS):
        return ValidationResult(ok=True, value="no")
    if _contains_any(t, YES_WORDS):
        return ValidationResult(ok=True, value="yes")
    return ValidationResult(ok=False, error="Could not detect a clear yes or no.")


def validate_text(raw: str) -> ValidationResult:
    t = raw.strip()
    if len(t) < 2:
        return ValidationResult(ok=False, error="Too short to be a valid answer.")
    return ValidationResult(ok=True, value=t)


def validate_address(raw: str) -> ValidationResult:
    t = raw.strip()
    if len(t) < 6 or not re.search(r"[A-Za-z]", t):
        return ValidationResult(ok=False, error="Doesn't look like a full address.")
    return ValidationResult(ok=True, value=t)


def validate_email(raw: str) -> ValidationResult:
    t = raw.strip().replace(" at ", "@").replace(" dot ", ".")
    t = t.replace(" ", "")
    if not EMAIL_RE.match(t):
        return ValidationResult(ok=False, error="That doesn't look like a valid email address.")
    return ValidationResult(ok=True, value=t.lower())


def validate_number(raw: str) -> ValidationResult:
    m = re.search(r"\d+", raw.replace(",", ""))
    if not m:
        return ValidationResult(ok=False, error="Could not find a number in the answer.")
    return ValidationResult(ok=True, value=m.group(0))


def validate_currency(raw: str) -> ValidationResult:
    cleaned = raw.replace(",", "").replace("$", "")
    m = re.search(r"\d+(\.\d{1,2})?", cleaned)
    if not m:
        return ValidationResult(ok=False, error="Could not find a dollar amount in the answer.")
    return ValidationResult(ok=True, value=m.group(0))


MONTH_NAMES = (
    "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
)


def validate_date(raw: str) -> ValidationResult:
    t = raw.strip()
    has_digit = re.search(r"\d", t)
    has_month = re.search(MONTH_NAMES, t.lower())
    has_relative = re.search(r"today|tomorrow|next week|next month|asap|immediately", t.lower())
    if not (has_digit or has_month or has_relative):
        return ValidationResult(ok=False, error="Could not understand that as a date.")
    if len(t) < 3:
        return ValidationResult(ok=False, error="Could not understand that as a date.")
    return ValidationResult(ok=True, value=t)


def validate_choice(raw: str, choices: list[str]) -> ValidationResult:
    t = raw.lower().strip()
    for c in choices:
        if c.lower() in t:
            return ValidationResult(ok=True, value=c)
    return ValidationResult(ok=False, error=f"Answer must be one of: {', '.join(choices)}.")


VALIDATORS = {
    "yes_no": validate_yes_no,
    "text": validate_text,
    "address": validate_address,
    "email": validate_email,
    "number": validate_number,
    "currency": validate_currency,
    "date": validate_date,
}


def validate_field(field_type: str, raw: str, choices: Optional[list[str]] = None) -> ValidationResult:
    if field_type == "choice":
        return validate_choice(raw, choices or [])
    validator = VALIDATORS.get(field_type, validate_text)
    return validator(raw)


# --- Card data guard -------------------------------------------------------

_DIGIT_RUN_RE = re.compile(r"(?:\d[ -]?){12,19}")


def luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 12:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def contains_card_number(text: str) -> bool:
    for match in _DIGIT_RUN_RE.finditer(text):
        if luhn_check(match.group(0)):
            return True
    return False


def redact_card_numbers(text: str) -> str:
    def _redact(match: re.Match) -> str:
        return "[REDACTED CARD NUMBER]" if luhn_check(match.group(0)) else match.group(0)

    return _DIGIT_RUN_RE.sub(_redact, text)
