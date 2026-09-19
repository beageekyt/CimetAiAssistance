"""Loads and serves the lead queue from data/leads.json (swap for the real
dataset on the day — see services/leads.py note in README)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).parent.parent / "data" / "leads.json"

_lock = threading.Lock()


def _load() -> list[dict[str, Any]]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _save(leads: list[dict[str, Any]]) -> None:
    DATA_PATH.write_text(json.dumps(leads, indent=2), encoding="utf-8")


def list_leads() -> list[dict[str, Any]]:
    return _load()


def get_lead(lead_id: str) -> Optional[dict[str, Any]]:
    for lead in _load():
        if lead["id"] == lead_id:
            return lead
    return None


def next_eligible_lead(exclude_statuses: Optional[set[str]] = None, suppressed: Optional[set[str]] = None) -> Optional[dict[str, Any]]:
    suppressed = suppressed or set()
    for lead in _load():
        if lead["id"] in suppressed:
            continue
        if lead.get("status") == "completed":
            continue
        return lead
    return None


def suppress_lead(lead_id: str) -> None:
    with _lock:
        leads = _load()
        for lead in leads:
            if lead["id"] == lead_id:
                lead["suppressed"] = True
        _save(leads)


def mark_completed(lead_id: str) -> None:
    """Flip the lead's status to 'completed' once the AI agent has collected
    every field. Remove this field from leads.json to re-run that lead again."""
    with _lock:
        leads = _load()
        for lead in leads:
            if lead["id"] == lead_id:
                lead["status"] = "completed"
        _save(leads)
