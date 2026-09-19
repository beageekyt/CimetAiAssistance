"""Persisted store of fully-completed connection applications, ready to hand
to the electricity provider. Written once a call finishes complete_journey.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent.parent / "data" / "processed_connections.json"

_lock = threading.Lock()


def _load() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(records: list[dict[str, Any]]) -> None:
    DATA_PATH.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def list_connections() -> list[dict[str, Any]]:
    return sorted(_load(), key=lambda r: r.get("submitted_at", 0), reverse=True)


def save_connection(lead_id: str, call_id: str, first_name: str, form: dict[str, str], reference: str) -> dict[str, Any]:
    record = {
        "lead_id": lead_id,
        "call_id": call_id,
        "first_name": first_name,
        "connection_provider": form.get("connection_provider"),
        "form": form,
        "reference": reference,
        "submitted_at": time.time(),
    }
    with _lock:
        records = _load()
        records.append(record)
        _save(records)
    return record
