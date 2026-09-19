import type { CallRecord } from "../types";

interface Props {
  call?: CallRecord;
}

export function SidePanel({ call }: Props) {
  return (
    <div className="panel side-panel">
      <h2>Handoff</h2>
      {!call?.escalation && <p className="muted">No escalation on the selected call.</p>}
      {call?.escalation && (
        <div className="handoff-card">
          <div className="handoff-reason">Reason: {call.escalation.reason}</div>
          <div className="handoff-summary">{call.escalation.summary}</div>
          <div className="handoff-opening">
            <div className="script-label">Opening line for the human</div>
            <div className="script-text">{call.escalation.opening_line}</div>
          </div>
        </div>
      )}

      <h2>Captured answers</h2>
      <div className="answers-list">
        {call && Object.entries(call.answers).map(([k, v]) => (
          <div key={k} className="answer-row">
            <span className="answer-key">{k}</span>
            <span className="answer-value">{v}</span>
          </div>
        ))}
        {!call && <p className="muted">—</p>}
      </div>
    </div>
  );
}
