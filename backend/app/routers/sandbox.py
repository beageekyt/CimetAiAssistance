"""Mock journey-completion sandbox. On the day, set JOURNEY_SANDBOX_URL and
adapt build_payload() to whatever payload the real endpoint expects."""
from __future__ import annotations

import random
import string
import time
from typing import Any

import httpx
from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


def build_payload(lead_id: str, answers: dict[str, str]) -> dict[str, Any]:
    return {"lead_id": lead_id, "submitted_at": time.time(), "answers": answers}


def _generate_reference() -> str:
    return "ECX-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


async def submit_journey(lead_id: str, answers: dict[str, str]) -> str:
    settings = get_settings()
    payload = build_payload(lead_id, answers)

    if settings.journey_sandbox_url:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(settings.journey_sandbox_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("reference") or data.get("id") or _generate_reference()

    # Built-in mock: just fabricate a reference number.
    return _generate_reference()


@router.post("/submit")
async def submit_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Mock endpoint standing in for the real journey sandbox during dev."""
    return {"reference": _generate_reference(), "received": payload}
