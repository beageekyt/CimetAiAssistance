import type { Lead } from "../types";

interface Props {
  leads: Lead[];
  onCall: (leadId: string) => void;
  onSimulate: (leadId: string) => void;
  onRunNext: () => void;
  busyLeadId?: string | null;
}

export function LeadQueue({ leads, onCall, onSimulate, onRunNext, busyLeadId }: Props) {
  return (
    <div className="panel lead-queue">
      <div className="panel-header">
        <h2>Lead queue</h2>
        <button className="btn btn-primary" onClick={onRunNext}>
          Run next (cron)
        </button>
      </div>
      <div className="lead-list">
        {leads.map((lead) => {
          const status = lead.last_call?.status;
          return (
            <div key={lead.id} className={`lead-card ${lead.dnc_blocked ? "lead-blocked" : ""}`}>
              <div className="lead-main">
                <div className="lead-name">
                  {lead.first_name} {lead.last_name}{" "}
                  <span className="lead-id">{lead.id}</span>
                </div>
                <div className="lead-meta">
                  Dropped at: <strong>{lead.dropped_section}</strong> · {lead.phone}
                </div>
                {lead.dnc_blocked && <div className="lead-dnc">Blocked: {lead.dnc_reason}</div>}
                {status && <div className={`lead-status status-${status}`}>{status}</div>}
              </div>
              <div className="lead-actions">
                <button
                  className="btn"
                  disabled={lead.dnc_blocked || busyLeadId === lead.id}
                  onClick={() => onCall(lead.id)}
                  title={lead.dnc_blocked ? lead.dnc_reason ?? "Blocked" : "Place a real Vapi call (needs Vapi/Vobiz configured + a public webhook URL)"}
                >
                  Call
                </button>
                <button
                  className="btn"
                  disabled={lead.dnc_blocked || busyLeadId === lead.id}
                  onClick={() => onSimulate(lead.id)}
                  title="Test the journey locally by typing replies — no phone/Vapi required"
                >
                  Simulate
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
