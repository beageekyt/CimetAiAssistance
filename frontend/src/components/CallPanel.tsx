import { useEffect, useRef, useState } from "react";
import type { CallRecord } from "../types";

interface Props {
  call?: CallRecord;
  onSendMessage?: (callId: string, text: string) => Promise<void>;
  onCompleteJourney?: (callId: string) => Promise<void>;
}

const ACTIVE_STATUSES = new Set(["in_progress"]);

export function CallPanel({ call, onSendMessage, onCompleteJourney }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call?.transcript.length]);

  useEffect(() => {
    setDraft("");
  }, [call?.call_id]);

  if (!call) {
    return (
      <div className="panel call-panel empty">
        <p>Select or start a call to see the live transcript.</p>
      </div>
    );
  }

  const doneFields = Object.keys(call.answers).length;
  const isSimulated = !call.vapi_call_id;
  const canChat = isSimulated && ACTIVE_STATUSES.has(call.status) && !!onSendMessage;

  async function handleSend() {
    const text = draft.trim();
    if (!text || !onSendMessage) return;
    setBusy(true);
    try {
      await onSendMessage(call!.call_id, text);
      setDraft("");
    } finally {
      setBusy(false);
    }
  }

  async function handleComplete() {
    if (!onCompleteJourney) return;
    setBusy(true);
    try {
      await onCompleteJourney(call!.call_id);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel call-panel">
      <div className="panel-header">
        <h2>
          Call: {call.first_name} <span className="muted">({call.call_id.slice(0, 8)})</span>
        </h2>
        <span className={`badge status-${call.status}`}>{call.status}</span>
      </div>

      <div className="script-card">
        <div className="script-label">Current field</div>
        <div className="script-text">{call.current_field_id ?? "—"}</div>
      </div>

      <div className="progress-row">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${doneFields ? Math.min(100, (doneFields / Math.max(doneFields, 1)) * 100) : 0}%` }} />
        </div>
        <span className="muted">{doneFields} fields captured</span>
      </div>

      <div className="transcript">
        {call.transcript.map((t, i) => (
          <div key={i} className={`bubble bubble-${t.role}`}>
            <span className="bubble-role">{t.role}</span>
            <span>{t.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {call.reference && <div className="reference-banner">Submitted — reference {call.reference}</div>}
      {call.blocked_reason && <div className="blocked-banner">Blocked: {call.blocked_reason}</div>}

      {canChat && (
        <div className="chat-input-row">
          <input
            className="chat-input"
            placeholder="Type the customer's reply (no Vapi keys configured — local simulation)…"
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSend();
            }}
          />
          <button className="btn btn-primary" onClick={handleSend} disabled={busy || !draft.trim()}>
            Send
          </button>
          <button className="btn" onClick={handleComplete} disabled={busy}>
            Complete journey
          </button>
        </div>
      )}
    </div>
  );
}
