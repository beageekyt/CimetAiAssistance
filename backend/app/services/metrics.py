"""Efficiency metrics vs an ASSUMED manual baseline (labelled as an
assumption — replace with a measured baseline on the day).
"""
from __future__ import annotations

from typing import Any

from .call_state import get_store

MANUAL_SECONDS_PER_FIELD = 25
MANUAL_OVERHEAD_SECONDS = 90


def compute_metrics() -> dict[str, Any]:
    calls = get_store().all_calls()
    total = len(calls)
    completed = [c for c in calls if c.status == "completed"]
    escalated = [c for c in calls if c.status == "escalated"]
    declined = [c for c in calls if c.status == "declined"]
    blocked = [c for c in calls if c.status == "blocked"]

    fields_captured = sum(len(c.answers) for c in calls)
    ava_seconds = sum(
        (c.ended_at - c.created_at) for c in calls if c.ended_at is not None
    )
    manual_seconds_estimate = fields_captured * MANUAL_SECONDS_PER_FIELD + len(calls) * MANUAL_OVERHEAD_SECONDS
    time_saved_seconds = max(0, manual_seconds_estimate - ava_seconds)

    return {
        "total_calls": total,
        "completed": len(completed),
        "escalated": len(escalated),
        "declined": len(declined),
        "blocked": len(blocked),
        "fields_captured": fields_captured,
        "ava_seconds": round(ava_seconds, 1),
        "manual_seconds_estimate": manual_seconds_estimate,
        "time_saved_seconds": round(time_saved_seconds, 1),
        "baseline_assumption": {
            "seconds_per_field": MANUAL_SECONDS_PER_FIELD,
            "overhead_seconds": MANUAL_OVERHEAD_SECONDS,
            "note": "Assumed manual baseline, not a measurement — replace with real data on the day.",
        },
    }
