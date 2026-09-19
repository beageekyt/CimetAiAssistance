import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { CallRecord, Lead, Metrics, ProcessedConnection, SseEvent } from "./types";

export function useConsole() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [calls, setCalls] = useState<Record<string, CallRecord>>({});
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [connections, setConnections] = useState<ProcessedConnection[]>([]);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const refreshLeads = useCallback(async () => {
    const data = await api.listLeads();
    setLeads(data);
  }, []);

  const refreshCalls = useCallback(async () => {
    const data = await api.listCalls();
    const map: Record<string, CallRecord> = {};
    for (const c of data) map[c.call_id] = c;
    setCalls(map);
  }, []);

  const refreshMetrics = useCallback(async () => {
    const data = await api.metrics();
    setMetrics(data);
  }, []);

  const refreshConnections = useCallback(async () => {
    const data = await api.listConnections();
    setConnections(data);
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshLeads(), refreshCalls(), refreshMetrics(), refreshConnections()]);
  }, [refreshLeads, refreshCalls, refreshMetrics, refreshConnections]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    const es = new EventSource(api.streamUrl());
    esRef.current = es;
    es.onopen = () => {
      setConnected(true);
      // Re-sync in case the backend restarted and lost in-memory state we still hold client-side.
      refreshAll();
    };
    es.onerror = () => setConnected(false);

    const handler = (evtName: string) => (evt: MessageEvent) => {
      let payload: any = {};
      try {
        payload = JSON.parse(evt.data);
      } catch {
        /* ignore */
      }
      const event: SseEvent = { type: evtName, payload };
      onEvent(event);
    };

    const eventNames = [
      "call_dialing",
      "call_in_progress",
      "call_blocked",
      "call_ended",
      "call_declined",
      "call_completed",
      "call_error",
      "call_note",
      "transcript",
      "field_recorded",
      "field_attempt",
      "escalation",
      "capture_problem",
      "outcome_logged",
    ];
    for (const name of eventNames) {
      es.addEventListener(name, handler(name));
    }

    function onEvent(event: SseEvent) {
      const callId: string | undefined = event.payload?.call_id ?? event.payload?.call_id;
      if (event.type.startsWith("call_") && event.payload?.call_id !== undefined && event.payload?.status !== undefined) {
        setCalls((prev) => ({ ...prev, [event.payload.call_id]: event.payload }));
      } else if (["call_dialing", "call_in_progress", "call_blocked", "escalation", "call_declined", "call_completed"].includes(event.type) && event.payload?.call_id) {
        setCalls((prev) => ({ ...prev, [event.payload.call_id]: { ...prev[event.payload.call_id], ...event.payload } }));
      }

      if (event.type === "transcript" && callId) {
        setCalls((prev) => {
          const existing = prev[callId];
          if (!existing) return prev;
          return {
            ...prev,
            [callId]: {
              ...existing,
              transcript: [...existing.transcript, { role: event.payload.role, text: event.payload.text, ts: Date.now() / 1000 }],
            },
          };
        });
      }

      if (["call_completed", "call_declined", "call_ended", "call_blocked"].includes(event.type)) {
        refreshLeads();
        refreshMetrics();
      }
      if (event.type === "call_completed") {
        refreshConnections();
      }
      if (event.type === "field_recorded" || event.type === "outcome_logged" || event.type === "escalation") {
        refreshMetrics();
      }
      if (callId) setSelectedCallId((cur) => cur ?? callId);
    }

    return () => {
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const callLead = useCallback(
    async (leadId: string) => {
      const res = await api.callLead(leadId);
      if (res.call_id) setSelectedCallId(res.call_id);
      await refreshCalls();
      await refreshLeads();
      return res;
    },
    [refreshCalls, refreshLeads]
  );

  const runNext = useCallback(async () => {
    const res = await api.runNext();
    if (res.call_id) setSelectedCallId(res.call_id);
    await refreshCalls();
    await refreshLeads();
    return res;
  }, [refreshCalls, refreshLeads]);

  const simulateLead = useCallback(
    async (leadId: string) => {
      const res = await api.chatStart(leadId);
      if (res.call_id) setSelectedCallId(res.call_id);
      await refreshCalls();
      await refreshLeads();
      return res;
    },
    [refreshCalls, refreshLeads]
  );

  const selectedCall = selectedCallId ? calls[selectedCallId] : undefined;
  const callList = Object.values(calls).sort((a, b) => b.created_at - a.created_at);

  return {
    leads,
    calls: callList,
    metrics,
    connections,
    connected,
    selectedCall,
    selectedCallId,
    setSelectedCallId,
    callLead,
    simulateLead,
    runNext,
    refreshAll,
  };
}
