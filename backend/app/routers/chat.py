"""Text-only simulation of a call, for local testing of the journey engine
without needing real Vapi credentials. Uses the exact same tool handlers as
the live webhook, so behaviour matches what happens on a real call.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException

from ..journey.schema import get_journey
from ..services import leads
from ..services.call_state import get_store
from .vapi import (
    _tool_complete_journey,
    _tool_escalate,
    _tool_flag_capture_problem,
    _tool_log_outcome,
    _tool_record_field,
    check_customer_signal_and_escalate,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/start")
async def start_chat(payload: dict[str, Any]) -> dict[str, Any]:
    lead_id = payload.get("lead_id")
    lead = leads.get_lead(lead_id) if lead_id else None
    if not lead:
        raise HTTPException(404, "Lead not found")

    store = get_store()
    journey = get_journey()
    record = store.create_call(lead_id=lead["id"], phone=lead["phone"], first_name=lead["first_name"])
    form = lead.get("connectionForm", {})
    # Consent is asked fresh every call; after that, next_field naturally resumes
    # wherever the connectionForm left off (confirm-flagged fields are never pre-seeded).
    resume_field = journey.first_field()
    confirm_ids = {f.id for f in journey.all_fields if f.confirm_if_prefilled}
    record.answers.update({k: v for k, v in form.items() if v is not None and k not in confirm_ids})
    initial_message, awaiting = resume_field.script, False
    store.update(
        record.call_id,
        status="in_progress",
        current_field_id=resume_field.id,
        current_section_id=resume_field.section_id,
        awaiting_confirmation=awaiting,
    )
    store.add_transcript(record.call_id, "assistant", initial_message)
    await store.publish("call_in_progress", store.get(record.call_id).to_dict())

    return {"call_id": record.call_id, "message": initial_message}


@router.post("/message")
async def send_message(payload: dict[str, Any]) -> dict[str, Any]:
    call_id = payload.get("call_id")
    text = payload.get("text", "")
    store = get_store()
    record = store.get(call_id) if call_id else None
    if not record:
        raise HTTPException(404, "Call not found")

    store.add_transcript(call_id, "customer", text)
    await store.publish("transcript", {"call_id": call_id, "role": "customer", "text": text})

    escalated = await check_customer_signal_and_escalate(call_id, text)
    if escalated:
        message = get_journey().scripts["escalation"]
        store.add_transcript(call_id, "assistant", message)
        await store.publish("transcript", {"call_id": call_id, "role": "assistant", "text": message})
        return {"valid": False, "action": "escalate", "message": message, "escalated": True}

    result = _tool_record_field(call_id, {"field_id": record.current_field_id, "raw_answer": text})
    message = result.get("message", "")
    store.add_transcript(call_id, "assistant", message)
    await store.publish("transcript", {"call_id": call_id, "role": "assistant", "text": message})

    if result.get("action") == "escalate":
        return {**result, "escalated": True}
    if result.get("action") == "ready_to_submit":
        return result

    return result


@router.post("/complete")
async def complete_chat(payload: dict[str, Any]) -> dict[str, Any]:
    call_id = payload.get("call_id")
    if not get_store().get(call_id):
        raise HTTPException(404, "Call not found")
    result = await _tool_complete_journey(call_id, {})
    if result.get("message"):
        get_store().add_transcript(call_id, "assistant", result["message"])
        await get_store().publish("transcript", {"call_id": call_id, "role": "assistant", "text": result["message"]})
    return result
