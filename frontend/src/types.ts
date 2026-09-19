export interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  dropped_section: string;
  connectionForm: Record<string, string | null>;
  notes?: string;
  suppressed?: boolean;
  status?: string;
  dnc_blocked: boolean;
  dnc_reason?: string | null;
  last_call?: CallRecord | null;
}

export interface ProcessedConnection {
  lead_id: string;
  call_id: string;
  first_name: string;
  connection_provider: string | null;
  form: Record<string, string>;
  reference: string;
  submitted_at: number;
}

export interface TranscriptEntry {
  role: string;
  text: string;
  ts: number;
}

export interface Escalation {
  reason: string;
  note: string;
  summary: string;
  opening_line: string;
}

export type CallStatus =
  | "queued"
  | "dialing"
  | "in_progress"
  | "escalated"
  | "completed"
  | "declined"
  | "blocked"
  | "ended";

export interface CallRecord {
  call_id: string;
  lead_id: string;
  phone: string;
  first_name: string;
  status: CallStatus;
  current_section_id?: string | null;
  current_field_id?: string | null;
  answers: Record<string, string>;
  attempts: Record<string, number>;
  transcript: TranscriptEntry[];
  escalation?: Escalation | null;
  blocked_reason?: string | null;
  reference?: string | null;
  created_at: number;
  ended_at?: number | null;
  vapi_call_id?: string | null;
}

export interface Metrics {
  total_calls: number;
  completed: number;
  escalated: number;
  declined: number;
  blocked: number;
  fields_captured: number;
  ava_seconds: number;
  manual_seconds_estimate: number;
  time_saved_seconds: number;
  baseline_assumption: {
    seconds_per_field: number;
    overhead_seconds: number;
    note: string;
  };
}

export interface SseEvent {
  type: string;
  payload: any;
}
