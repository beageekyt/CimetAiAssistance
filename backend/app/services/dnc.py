"""DNC / calling-hours gate. This is a stub for the real ACMA "Do Not Call
Register" check; it shows where that integration sits, plus an internal
opt-out suppression list and (optionally) permitted calling hours.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import get_settings

DATA_PATH = Path(__file__).parent.parent / "data" / "dnc_list.json"


@dataclass
class GateResult:
    allowed: bool
    reason: Optional[str] = None


def _load() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_on_dnc_register(phone: str) -> bool:
    """Stub for the real ACMA Do Not Call Register lookup API."""
    data = _load()
    return phone in data.get("numbers", [])


def is_opted_out(phone: str) -> bool:
    data = _load()
    return phone in data.get("opt_out", [])


def add_opt_out(phone: str) -> None:
    data = _load()
    if phone not in data.get("opt_out", []):
        data.setdefault("opt_out", []).append(phone)
        _save(data)


def within_calling_hours() -> bool:
    settings = get_settings()
    if not settings.enforce_calling_hours:
        return True
    hour = datetime.now().hour
    return settings.calling_hours_start <= hour < settings.calling_hours_end


def check(phone: str) -> GateResult:
    if is_on_dnc_register(phone):
        return GateResult(allowed=False, reason="On the Do Not Call Register.")
    if is_opted_out(phone):
        return GateResult(allowed=False, reason="Previously opted out.")
    if not within_calling_hours():
        return GateResult(allowed=False, reason="Outside permitted calling hours.")
    return GateResult(allowed=True)
