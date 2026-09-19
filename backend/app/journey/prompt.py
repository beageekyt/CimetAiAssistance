"""Builds the Vapi assistant config: system prompt + tool definitions.
Used by scripts/create_assistant.py to create/patch the assistant, and kept
here (not duplicated) so the prompt and the tool contracts stay in sync with
the journey engine.
"""
from __future__ import annotations

from typing import Any

from .schema import get_journey

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-3-5-sonnet-20241022"
VOICE_PROVIDER = "11labs"
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def build_system_prompt(human_agent_name: str) -> str:
    journey = get_journey()
    lines = [
        "You are CIMET PowerBridge ai, a warm, efficient voice agent handling new electricity connection applications.",
        "You are calling customers who started a new connection application online and didn't finish it.",
        "Your job: resume the application by voice, collect the remaining fields, validate them, and submit it.",
        "",
        "Hard rules, no exceptions:",
        "- Never proceed past consent. If the customer does not clearly consent to being recorded/continuing, call log_outcome with outcome='declined' and end the call politely.",
        "- Ask ONE question at a time, using the exact wording of the current field's script the server gives you.",
        "- Some fields (like the connection provider) may already have a value from the online form. When the server gives you a 'keep or change' confirmation question instead of a normal question, ask exactly that, and record whatever the customer says via `record_field` as usual — the server figures out whether they kept it or changed it.",
        "- After every customer answer to a data question, call the `record_field` tool with the field id and the raw text you heard. Do not guess or normalise the value yourself — the server validates it and tells you what to do next.",
        "- If `record_field` returns invalid, use the reprompt text it gives you. After 3 failed attempts on the same field, the server will tell you to escalate — call `escalate_to_human` immediately when told to.",
        "- Never ask for or accept credit card / payment card numbers by voice. If the customer starts giving card digits, stop them, say the card-data-redirect line, and call `flag_capture_problem` with type='card_data'.",
        "- Never give personal advice on which connection option, tariff, or provider is best. If asked, say the no-advice line and call `escalate_to_human` with reason='advice'.",
        "- If the customer mentions life support, medical dependency on the connection, financial hardship, or vulnerability, say the life-support/sensitive line and immediately call `escalate_to_human` with reason='sensitive'.",
        "- If the customer sounds angry, confused after a reprompt, goes off-script repeatedly, or explicitly asks for a person/manager, call `escalate_to_human` with the matching reason.",
        "- If the customer says no / not interested / asks to stop being called at any point, call `log_outcome` with outcome='declined' and end the call — do not push back.",
        "- When escalating, give a short natural-sounding line letting the customer know you're connecting them to a colleague, then call `escalate_to_human` (which prepares a briefing) followed by the transferCall tool.",
        "- When all required fields for the application are captured, read back a short summary and get final consent (the consent_declaration field), then call `complete_journey`.",
        "- Keep turns short and conversational. Do not read out field ids or internal jargon.",
        "",
        f"When you hand off, the human colleague's name is {human_agent_name}; you can tell the customer you're connecting them to a colleague.",
        "",
        "Application sections in order: " + ", ".join(s.title for s in journey.sections) + ".",
    ]
    return "\n".join(lines)


def tool_definitions(server_url: str) -> list[dict[str, Any]]:
    common_server = {"url": server_url}
    return [
        {
            "type": "function",
            "function": {
                "name": "record_field",
                "description": "Record the customer's raw answer for the current field. The server validates/normalises it and returns what to say next.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "description": "The id of the field being answered."},
                        "raw_answer": {"type": "string", "description": "The customer's answer, as heard, verbatim."},
                    },
                    "required": ["field_id", "raw_answer"],
                },
            },
            "server": common_server,
        },
        {
            "type": "function",
            "function": {
                "name": "flag_capture_problem",
                "description": "Flag a data-capture problem such as card data being spoken, so the server can redact/handle it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["card_data", "other"]},
                        "note": {"type": "string"},
                    },
                    "required": ["type"],
                },
            },
            "server": common_server,
        },
        {
            "type": "function",
            "function": {
                "name": "log_outcome",
                "description": "Log a terminal outcome for the call, e.g. the customer declined or said no.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "outcome": {"type": "string", "enum": ["declined", "no_consent", "completed", "voicemail", "other"]},
                        "note": {"type": "string"},
                    },
                    "required": ["outcome"],
                },
            },
            "server": common_server,
        },
        {
            "type": "function",
            "function": {
                "name": "escalate_to_human",
                "description": "Escalate the call to a human. Prepares a briefing for the warm transfer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "enum": ["anger", "confusion", "human_request", "advice", "sensitive", "repeated_failure", "other"],
                        },
                        "note": {"type": "string"},
                    },
                    "required": ["reason"],
                },
            },
            "server": common_server,
        },
        {
            "type": "function",
            "function": {
                "name": "complete_journey",
                "description": "All required fields are captured and the customer confirmed. Submits the journey to the sandbox and returns a reference number.",
                "parameters": {"type": "object", "properties": {}},
            },
            "server": common_server,
        },
    ]


def build_assistant_payload(server_base_url: str, human_agent_name: str, human_handoff_number: str, webhook_secret: str = "") -> dict[str, Any]:
    webhook_url = server_base_url.rstrip("/") + "/api/vapi/webhook"
    payload: dict[str, Any] = {
        "name": "Nova - CIMET Dropout Recovery",
        "model": {
            "provider": MODEL_PROVIDER,
            "model": MODEL_NAME,
            "temperature": 0.3,
            "messages": [{"role": "system", "content": build_system_prompt(human_agent_name)}],
            "tools": tool_definitions(webhook_url),
        },
        "voice": {"provider": VOICE_PROVIDER, "voiceId": VOICE_ID},
        "firstMessageMode": "assistant-speaks-first",
        "serverUrl": webhook_url,
        "serverMessages": ["status-update", "transcript", "end-of-call-report", "tool-calls"],
        "endCallFunctionEnabled": True,
    }
    if webhook_secret:
        payload["serverUrlSecret"] = webhook_secret
    if human_handoff_number:
        payload["forwardingPhoneNumber"] = human_handoff_number
    return payload
