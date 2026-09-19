import { useState } from "react";
import { api } from "./api";
import { CallPanel } from "./components/CallPanel";
import { ConvertedLeads } from "./components/ConvertedLeads";
import { LeadQueue } from "./components/LeadQueue";
import { MetricsBar } from "./components/MetricsBar";
import { SidePanel } from "./components/SidePanel";
import { useConsole } from "./useConsole";

export default function App() {
  const { leads, calls, metrics, connections, connected, selectedCall, selectedCallId, setSelectedCallId, callLead, simulateLead, runNext } =
    useConsole();
  const [busyLeadId, setBusyLeadId] = useState<string | null>(null);

  async function handleCall(leadId: string) {
    setBusyLeadId(leadId);
    try {
      await callLead(leadId);
    } finally {
      setBusyLeadId(null);
    }
  }

  async function handleSimulate(leadId: string) {
    setBusyLeadId(leadId);
    try {
      await simulateLead(leadId);
    } finally {
      setBusyLeadId(null);
    }
  }

  async function handleSendMessage(callId: string, text: string) {
    await api.chatMessage(callId, text);
  }

  async function handleCompleteJourney(callId: string) {
    await api.chatComplete(callId);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>CIMET — PowerBridge</h1>
        <div className={`live-badge ${connected ? "live" : "offline"}`}>{connected ? "Live feed" : "Disconnected"}</div>
      </header>

      <div className="app-body">
        <LeadQueue leads={leads} onCall={handleCall} onSimulate={handleSimulate} onRunNext={runNext} busyLeadId={busyLeadId} />

        <div className="center-column">
          <div className="call-tabs">
            {calls.map((c) => (
              <button
                key={c.call_id}
                className={`call-tab ${c.call_id === selectedCallId ? "active" : ""}`}
                onClick={() => setSelectedCallId(c.call_id)}
              >
                {c.first_name} · {c.status}
              </button>
            ))}
          </div>
          <CallPanel call={selectedCall} onSendMessage={handleSendMessage} onCompleteJourney={handleCompleteJourney} />
        </div>

        <div className="side-column">
          <SidePanel call={selectedCall} />
          <ConvertedLeads connections={connections} />
        </div>
      </div>

      <MetricsBar metrics={metrics} />
    </div>
  );
}
