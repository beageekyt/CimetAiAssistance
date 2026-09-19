import type { ProcessedConnection } from "../types";

interface Props {
  connections: ProcessedConnection[];
}

export function ConvertedLeads({ connections }: Props) {
  return (
    <div className="panel converted-leads">
      <div className="panel-header">
        <h2>Converted by AI agent</h2>
        <span className="muted">{connections.length}</span>
      </div>
      {connections.length === 0 && <p className="muted">No connection applications completed yet.</p>}
      <div className="converted-list">
        {connections.map((c) => (
          <details key={c.call_id} className="converted-card">
            <summary>
              <span className="converted-name">{c.form.customer_name || c.first_name}</span>
              <span className="converted-provider">{c.connection_provider}</span>
              <span className="converted-reference">{c.reference}</span>
            </summary>
            <div className="converted-form">
              {Object.entries(c.form).map(([k, v]) => (
                <div key={k} className="answer-row">
                  <span className="answer-key">{k}</span>
                  <span className="answer-value">{v}</span>
                </div>
              ))}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
