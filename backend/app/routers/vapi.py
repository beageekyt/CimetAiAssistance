"""Everything that talks to Vapi: outbound dialing, the webhook (tool calls +
status/transcript events), the lead queue, and the SSE stream the console
subscribes to. The LLM only converses; every decision that matters (next
field, validation, escalation, submission) happens here.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..journey.schema import get_journey
from ..journey.signals import MAX_FIELD_ATTEMPTS, scan_utterance
from ..journey.validate import ValidationResult, redact_card_numbers, validate_field
from ..services import connections, dnc, leads
from ..services.call_state import get_store
from ..services.metrics import compute_metrics

router = APIRouter(prefix="/api/vapi", tags=["vapi"])


def _template(text: str, **kwargs: Any) -> str:
    for k, v in kwargs.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def _initial_prompt_for_field(field, existing_value: Optional[str]) -> tuple[str, bool]:
    """Prefilled fields flagged confirm_if_prefilled get a keep-or-change question
    instead of being asked (or silently skipped) again."""
    if field.confirm_if_prefilled and existing_value is not None and field.confirm_script:
        return _template(field.confirm_script, value=existing_value), True
    return field.script, False


# ---------------------------------------------------------------------------
# Lead queue
# ---------------------------------------------------------------------------

@router.get("/leads")
async def list_leads() -> list[dict[str, Any]]:
    store = get_store()
    out = []
    for lead in leads.list_leads():
        # Hackathon toggle: remove "status": "completed" from the lead in leads.json
        # to bring it back into the queue and re-run it.
        if lead.get("status") == "completed":
            continue
        gate = dnc.check(lead["phone"])
        calls = [c for c in store.all_calls() if c.lead_id == lead["id"]]
        last_call = calls[0] if calls else None
        out.append(
            {
                **lead,
                "dnc_blocked": not gate.allowed,
                "dnc_reason": gate.reason,
                "last_call": last_call.to_dict() if last_call else None,
            }
        )
    return out


@router.post("/leads/{lead_id}/call")
async def call_lead(lead_id: str) -> dict[str, Any]:
    lead = leads.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return await _dial(lead)


@router.post("/leads/run-next")
async def run_next() -> dict[str, Any]:
    store = get_store()
    active_lead_ids = {c.lead_id for c in store.all_calls() if c.status in {"queued", "dialing", "in_progress", "escalated"}}
    suppressed = {l["id"] for l in leads.list_leads() if l.get("suppressed")}
    lead = leads.next_eligible_lead(suppressed=suppressed | active_lead_ids)
    if not lead:
        return {"dialed": False, "reason": "No eligible leads."}
    result = await _dial(lead)
    result["dialed"] = True
    return result


async def _dial(lead: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    settings = get_settings()
    gate = dnc.check(lead["phone"])

    record = store.create_call(lead_id=lead["id"], phone=lead["phone"], first_name=lead["first_name"])
    journey = get_journey()
    form = lead.get("connectionForm", {})
    # Consent to being recorded/continuing is asked fresh every call; once given, the
    # normal field-by-field walk naturally resumes wherever the connectionForm left off.
    resume_field = journey.first_field()
    record.current_section_id = resume_field.section_id
    record.current_field_id = resume_field.id
    confirm_ids = {f.id for f in journey.all_fields if f.confirm_if_prefilled}
    record.answers.update({k: v for k, v in form.items() if v is not None and k not in confirm_ids})
    initial_message, awaiting = resume_field.script, False
    record.awaiting_confirmation = awaiting

    if not gate.allowed:
        store.update(record.call_id, status="blocked", blocked_reason=gate.reason, ended_at=_now())
        await store.publish("call_blocked", record.to_dict())
        return {"call_id": record.call_id, "status": "blocked", "reason": gate.reason}

    store.update(record.call_id, status="dialing")
    await store.publish("call_dialing", record.to_dict())

    if not settings.vapi_api_key or not settings.vapi_assistant_id or not settings.vapi_phone_number_id:
        # Not configured yet — we can't place a real PSTN call, so fall back to a
        # text-driven local simulation of the same call (same tool handlers as a
        # real webhook) so the console still shows a live, working transcript.
        store.update(record.call_id, status="in_progress")
        store.add_transcript(record.call_id, "assistant", initial_message)
        await store.publish(
            "call_note",
            {"call_id": record.call_id, "note": "Vapi is not fully configured (VAPI_API_KEY / VAPI_ASSISTANT_ID / VAPI_PHONE_NUMBER_ID), so this is a local text simulation — reply in the console's message box to continue the conversation."},
        )
        await store.publish("call_in_progress", store.get(record.call_id).to_dict())
        return {"call_id": record.call_id, "status": "in_progress", "note": "vapi not configured", "mode": "simulated"}

    payload = {
        "assistantId": settings.vapi_assistant_id,
        "phoneNumberId": settings.vapi_phone_number_id,
        "customer": {"number": lead["phone"]},
        "metadata": {"internal_call_id": record.call_id, "lead_id": lead["id"]},
        "assistantOverrides": {
            "variableValues": {
                "first_name": lead["first_name"],
                "lead_context": json.dumps({"lead": lead}),
            }
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.vapi_base_url}/call",
                headers={"Authorization": f"Bearer {settings.vapi_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            vapi_call_id = data.get("id")
            store.update(record.call_id, vapi_call_id=vapi_call_id, status="in_progress")
    except httpx.HTTPError as exc:
        store.update(record.call_id, status="ended", ended_at=_now())
        await store.publish("call_error", {"call_id": record.call_id, "error": str(exc)})
        raise HTTPException(502, f"Vapi dial failed: {exc}") from exc

    await store.publish("call_in_progress", record.to_dict())
    return {"call_id": record.call_id, "status": "in_progress"}


def _now() -> float:
    import time

    return time.time()


# ---------------------------------------------------------------------------
# Webhook (tool calls + call lifecycle events from Vapi)
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def webhook(request: Request, x_vapi_secret: Optional[str] = Header(default=None)) -> dict[str, Any]:
    settings = get_settings()
    if settings.vapi_webhook_secret and x_vapi_secret != settings.vapi_webhook_secret:
        raise HTTPException(401, "Invalid webhook secret")

    body = await request.json()
    message = body.get("message", body)
    msg_type = message.get("type")

    if msg_type == "tool-calls":
        return await _handle_tool_calls(message)
    if msg_type == "status-update":
        await _handle_status_update(message)
        return {"ok": True}
    if msg_type == "transcript":
        await _handle_transcript(message)
        return {"ok": True}
    if msg_type == "end-of-call-report":
        await _handle_end_of_call(message)
        return {"ok": True}

    return {"ok": True}


def _find_call_id(message: dict[str, Any]) -> Optional[str]:
    call = message.get("call", {})
    metadata = call.get("metadata", {}) or {}
    internal_id = metadata.get("internal_call_id")
    if internal_id:
        return internal_id
    vapi_call_id = call.get("id")
    if vapi_call_id:
        record = get_store().get_by_vapi_id(vapi_call_id)
        if record:
            return record.call_id
    return None


async def _handle_status_update(message: dict[str, Any]) -> None:
    store = get_store()
    call_id = _find_call_id(message)
    if not call_id:
        return
    status = message.get("status") or message.get("call", {}).get("status")
    if status == "ended":
        record = store.get(call_id)
        if record and record.status not in {"completed", "declined", "blocked"}:
            store.update(call_id, status="ended", ended_at=_now())
        await store.publish("call_ended", {"call_id": call_id})


async def _handle_transcript(message: dict[str, Any]) -> None:
    store = get_store()
    call_id = _find_call_id(message)
    if not call_id:
        return
    role = message.get("role", "customer")
    text = message.get("transcript") or message.get("transcriptText") or ""
    transcript_type = message.get("transcriptType", "final")
    if not text or transcript_type != "final":
        return

    safe_text = redact_card_numbers(text)
    store.add_transcript(call_id, role="assistant" if role == "assistant" else "customer", text=safe_text)
    await store.publish("transcript", {"call_id": call_id, "role": role, "text": safe_text})

    if role != "assistant":
        await check_customer_signal_and_escalate(call_id, text)


async def check_customer_signal_and_escalate(call_id: str, text: str) -> bool:
    """Server-side safety net: scan a customer utterance for escalation signals
    (anger, human request, advice, sensitive topics) regardless of whether the
    LLM itself decided to call escalate_to_human. Used by both the real Vapi
    webhook and the local text-chat simulation so behaviour matches."""
    store = get_store()
    signal = scan_utterance(text)
    record = store.get(call_id)
    if signal.escalate and record and record.status not in TERMINAL_STATUSES:
        _apply_escalation(call_id, reason=signal.category or "other", note=signal.reason or "")
        await store.publish("escalation", store.get(call_id).to_dict())
        return True
    return False


async def _handle_end_of_call(message: dict[str, Any]) -> None:
    store = get_store()
    call_id = _find_call_id(message)
    if not call_id:
        return
    record = store.get(call_id)
    if record and record.status not in {"completed", "declined", "blocked"}:
        store.update(call_id, status="ended", ended_at=_now())
    await store.publish("call_ended", {"call_id": call_id})


# ---------------------------------------------------------------------------
# Tool call handling
# ---------------------------------------------------------------------------

async def _handle_tool_calls(message: dict[str, Any]) -> dict[str, Any]:
    call_id = _find_call_id(message)
    tool_calls = message.get("toolCallList") or message.get("toolCalls") or []
    results = []
    for tc in tool_calls:
        tool_call_id = tc.get("id")
        function = tc.get("function", {})
        name = function.get("name")
        raw_args = function.get("arguments", {})
        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})

        if not call_id:
            result: Any = {"error": "Unknown call; internal_call_id metadata missing."}
        elif name == "record_field":
            result = _tool_record_field(call_id, args)
        elif name == "flag_capture_problem":
            result = _tool_flag_capture_problem(call_id, args)
        elif name == "log_outcome":
            result = _tool_log_outcome(call_id, args)
        elif name == "escalate_to_human":
            result = _tool_escalate(call_id, args)
        elif name == "complete_journey":
            result = await _tool_complete_journey(call_id, args)
        else:
            result = {"error": f"Unknown tool '{name}'"}

        results.append({"toolCallId": tool_call_id, "result": json.dumps(result) if not isinstance(result, str) else result})

    return {"results": results}


TERMINAL_STATUSES = {"escalated", "completed", "declined", "blocked", "ended"}
KEEP_WORDS = ("keep", "same", "no change", "that's right", "thats right", "correct", "leave it", "don't change", "dont change")


def _wants_to_keep_prefilled(raw: str) -> bool:
    t = raw.lower()
    return any(w in t for w in KEEP_WORDS)


def _tool_record_field(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    record = store.get(call_id)
    if not record:
        return {"error": "call not found"}
    if record.status in TERMINAL_STATUSES:
        return {"valid": False, "action": "noop", "message": "This call has already ended or been handed off; no further fields are collected."}
    journey = get_journey()

    field_id = args.get("field_id", record.current_field_id)
    raw_answer = args.get("raw_answer", "")
    field = journey.field(field_id) or journey.field(record.current_field_id)
    if not field:
        return {"error": "unknown field"}

    if record.awaiting_confirmation and field.id == record.current_field_id:
        record.awaiting_confirmation = False
        store.update(call_id, awaiting_confirmation=False)
        if _wants_to_keep_prefilled(raw_answer):
            lead = leads.get_lead(record.lead_id)
            existing_value = (lead.get("connectionForm") or {}).get(field.id) if lead else None
            validation = ValidationResult(ok=True, value=existing_value)
        else:
            validation = validate_field(field.type, raw_answer, field.choices)
    else:
        validation = validate_field(field.type, raw_answer, field.choices)

    if not validation.ok:
        attempts = record.attempts.get(field.id, 0) + 1
        record.attempts[field.id] = attempts
        store.update(call_id, attempts=record.attempts)
        get_store().publish_nowait("field_attempt", {"call_id": call_id, "field_id": field.id, "attempts": attempts, "valid": False})
        if attempts >= MAX_FIELD_ATTEMPTS:
            _apply_escalation(call_id, reason="repeated_failure", note=f"3 failed attempts on field '{field.id}'.")
            return {
                "valid": False,
                "action": "escalate",
                "message": "I'm having trouble catching that, so let me connect you with a colleague who can help.",
            }
        return {"valid": False, "action": "reprompt", "message": field.reprompt}

    record.answers[field.id] = validation.value or raw_answer
    if field.on_no == "decline" and validation.value == "no":
        store.update(call_id, answers=record.answers, status="declined", ended_at=_now())
        get_store().publish_nowait("call_declined", record.to_dict())
        return {"valid": True, "action": "decline", "message": journey.scripts["decline"]}

    next_field = journey.next_field(field.id, set(record.answers.keys()))
    if next_field is None:
        store.update(call_id, answers=record.answers, current_field_id=None)
        get_store().publish_nowait("field_recorded", {"call_id": call_id, "field_id": field.id, "value": validation.value})
        summary = ", ".join(f"{k}: {v}" for k, v in record.answers.items())
        return {
            "valid": True,
            "action": "ready_to_submit",
            "message": f"Here's what I've got: {summary}. Please read this back and confirm with the consent_declaration field, then call complete_journey.",
        }

    lead = leads.get_lead(record.lead_id)
    existing_value = (lead.get("connectionForm") or {}).get(next_field.id) if lead else None
    next_message, next_awaiting = _initial_prompt_for_field(next_field, existing_value)
    store.update(
        call_id,
        answers=record.answers,
        current_field_id=next_field.id,
        current_section_id=next_field.section_id,
        awaiting_confirmation=next_awaiting,
    )
    get_store().publish_nowait("field_recorded", {"call_id": call_id, "field_id": field.id, "value": validation.value, "next_field_id": next_field.id})

    section_changed = next_field.section_id != field.section_id
    section = journey.section(next_field.section_id)
    prefix = (section.intro_script + " ") if section_changed and section and section.intro_script else ""
    return {
        "valid": True,
        "action": "continue",
        "next_field_id": next_field.id,
        "message": prefix + next_message,
    }


def _tool_flag_capture_problem(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    journey = get_journey()
    problem_type = args.get("type", "other")
    get_store().publish_nowait("capture_problem", {"call_id": call_id, "type": problem_type, "note": args.get("note", "")})
    if problem_type == "card_data":
        return {"message": journey.scripts["card_data_redirect"]}
    return {"message": "Noted, let's continue."}


def _tool_log_outcome(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    record = store.get(call_id)
    outcome = args.get("outcome", "other")
    status_map = {"declined": "declined", "no_consent": "declined", "completed": "completed", "voicemail": "ended", "other": "ended"}
    status = status_map.get(outcome, "ended")
    store.update(call_id, status=status, ended_at=_now())
    if outcome in {"declined", "no_consent"} and record:
        leads.suppress_lead(record.lead_id)
        dnc.add_opt_out(record.phone)
    get_store().publish_nowait("outcome_logged", {"call_id": call_id, "outcome": outcome, "note": args.get("note", "")})
    journey = get_journey()
    return {"message": journey.scripts["decline"] if status == "declined" else "Understood, thank you."}


def _tool_escalate(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    reason = args.get("reason", "other")
    note = args.get("note", "")
    _apply_escalation(call_id, reason=reason, note=note)
    record = get_store().get(call_id)
    return {"message": get_journey().scripts["escalation"], "briefing": record.escalation if record else None}


def _apply_escalation(call_id: str, reason: str, note: str) -> None:
    store = get_store()
    settings = get_settings()
    record = store.get(call_id)
    if not record:
        return
    journey = get_journey()
    answers_summary = "; ".join(f"{k}: {v}" for k, v in record.answers.items()) or "No fields captured yet."
    briefing = {
        "reason": reason,
        "note": note,
        "summary": f"Lead {record.lead_id} ({record.first_name}). Reason: {reason}. Captured so far — {answers_summary}",
        "opening_line": _template(
            journey.scripts["handoff_opening_line"],
            human_agent_name=settings.human_agent_name,
            first_name=record.first_name,
        ),
    }
    store.update(call_id, status="escalated", escalation=briefing)
    store.publish_nowait("escalation", store.get(call_id).to_dict())


async def _tool_complete_journey(call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    record = store.get(call_id)
    if not record:
        return {"error": "call not found"}
    journey = get_journey()
    missing = [f.id for f in journey.all_fields if f.required and f.id not in record.answers]
    if missing:
        return {"valid": False, "message": f"Still missing: {', '.join(missing)}."}

    from .sandbox import submit_journey

    form = {k: v for k, v in record.answers.items() if k != "consent_recording"}
    reference = await submit_journey(record.lead_id, record.answers)
    connections.save_connection(record.lead_id, call_id, record.first_name, form, reference)
    leads.mark_completed(record.lead_id)
    store.update(call_id, status="completed", reference=reference, ended_at=_now())
    store.publish_nowait("call_completed", store.get(call_id).to_dict())
    message = _template(journey.scripts["close"], first_name=record.first_name, reference=reference)
    return {"valid": True, "message": message, "reference": reference}


# ---------------------------------------------------------------------------
# SSE stream + metrics
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream() -> StreamingResponse:
    store = get_store()
    queue = store.subscribe()

    async def event_gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                event = await queue.get()
                yield f"event: {event['type']}\ndata: {json.dumps(event['payload'], default=str)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            store.unsubscribe(queue)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/calls")
async def list_calls() -> list[dict[str, Any]]:
    return [c.to_dict() for c in get_store().all_calls()]


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    return compute_metrics()


@router.get("/connections")
async def list_connections() -> list[dict[str, Any]]:
    """Fully completed connection applications, ready to hand to the provider —
    what the console shows as 'converted by AI agent'."""
    return connections.list_connections()
