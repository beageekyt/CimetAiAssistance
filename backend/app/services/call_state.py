"""In-memory + JSON-persisted store of call state, plus a simple pub/sub
broadcaster the SSE endpoint reads from. This is the single source of truth
for what the console renders live.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).parent.parent / "data" / "calls.json"


@dataclass
class TranscriptEntry:
    role: str  # "assistant" | "customer" | "system"
    text: str
    ts: float = field(default_factory=time.time)


@dataclass
class CallRecord:
    call_id: str
    lead_id: str
    phone: str
    first_name: str
    status: str = "queued"  # queued|dialing|in_progress|escalated|completed|declined|blocked|ended
    current_section_id: Optional[str] = None
    current_field_id: Optional[str] = None
    answers: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    transcript: list[TranscriptEntry] = field(default_factory=list)
    escalation: Optional[dict[str, Any]] = None
    blocked_reason: Optional[str] = None
    reference: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    vapi_call_id: Optional[str] = None
    awaiting_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CallRecord":
        d = dict(d)
        transcript = [TranscriptEntry(**t) for t in d.pop("transcript", [])]
        return cls(transcript=transcript, **d)


class CallStore:
    def __init__(self) -> None:
        self._calls: dict[str, CallRecord] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not DATA_PATH.exists():
            return
        try:
            data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            for d in data:
                record = CallRecord.from_dict(d)
                self._calls[record.call_id] = record
        except Exception:
            pass

    # --- lifecycle ---------------------------------------------------
    def create_call(self, lead_id: str, phone: str, first_name: str) -> CallRecord:
        call_id = str(uuid.uuid4())
        record = CallRecord(call_id=call_id, lead_id=lead_id, phone=phone, first_name=first_name)
        self._calls[call_id] = record
        self._persist()
        return record

    def get(self, call_id: str) -> Optional[CallRecord]:
        return self._calls.get(call_id)

    def get_by_vapi_id(self, vapi_call_id: str) -> Optional[CallRecord]:
        for c in self._calls.values():
            if c.vapi_call_id == vapi_call_id:
                return c
        return None

    def all_calls(self) -> list[CallRecord]:
        return sorted(self._calls.values(), key=lambda c: c.created_at, reverse=True)

    def update(self, call_id: str, **kwargs: Any) -> Optional[CallRecord]:
        record = self._calls.get(call_id)
        if not record:
            return None
        for k, v in kwargs.items():
            setattr(record, k, v)
        self._persist()
        return record

    def add_transcript(self, call_id: str, role: str, text: str) -> None:
        record = self._calls.get(call_id)
        if not record:
            return
        record.transcript.append(TranscriptEntry(role=role, text=text))
        self._persist()

    # --- pub/sub for SSE ----------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "ts": time.time()}
        for q in list(self._subscribers):
            await q.put(event)

    def publish_nowait(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "ts": time.time()}
        for q in list(self._subscribers):
            q.put_nowait(event)

    # --- persistence (best-effort, non-blocking) -----------------------
    def _persist(self) -> None:
        try:
            data = [c.to_dict() for c in self._calls.values()]
            DATA_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass


_store: Optional[CallStore] = None


def get_store() -> CallStore:
    global _store
    if _store is None:
        _store = CallStore()
    return _store
