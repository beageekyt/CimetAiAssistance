import type { CallRecord, Lead, Metrics, ProcessedConnection } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  base: API_BASE,
  health: () => request<{ status: string }>("/api/health"),
  listLeads: () => request<Lead[]>("/api/vapi/leads"),
  callLead: (leadId: string) => request<{ call_id: string; status: string }>(`/api/vapi/leads/${leadId}/call`, { method: "POST" }),
  runNext: () => request<{ dialed: boolean; call_id?: string; status?: string; reason?: string }>("/api/vapi/leads/run-next", { method: "POST" }),
  listCalls: () => request<CallRecord[]>("/api/vapi/calls"),
  metrics: () => request<Metrics>("/api/vapi/metrics"),
  listConnections: () => request<ProcessedConnection[]>("/api/vapi/connections"),
  streamUrl: () => `${API_BASE}/api/vapi/stream`,
  chatStart: (leadId: string) => request<{ call_id: string; message: string }>("/api/chat/start", { method: "POST", body: JSON.stringify({ lead_id: leadId }) }),
  chatMessage: (callId: string, text: string) => request<any>("/api/chat/message", { method: "POST", body: JSON.stringify({ call_id: callId, text }) }),
  chatComplete: (callId: string) => request<any>("/api/chat/complete", { method: "POST", body: JSON.stringify({ call_id: callId }) }),
};
