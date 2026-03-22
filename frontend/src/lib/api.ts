import axios from "axios";
import { getSession } from "next-auth/react";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach the JWT access token to every outgoing request
api.interceptors.request.use(async (config) => {
  const session = await getSession();
  if ((session as any)?.accessToken) {
    config.headers.Authorization = `Bearer ${(session as any).accessToken}`;
  }
  return config;
});

// ── Types ──────────────────────────────────────────────

export interface Lead {
  id: string;
  email: string;
  phone?: string;
  first_name: string;
  last_name: string;
  company: string;
  title: string;
  source: string;
  meeting_verified: boolean;
  proof_data?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComplianceCheck {
  can_send: boolean;
  reason: string;
}

export interface SequenceStep {
  id: string;
  sequence_id: string;
  step_type: string;
  position: number;
  config: Record<string, unknown> | null;
  delay_hours: number;
  condition: Record<string, unknown> | null;
  true_next_position: number | null;
  false_next_position: number | null;
  ab_variants: Record<string, unknown> | null;
  is_ab_test: boolean;
  node_id: string | null;
  created_at: string;
}

export interface VisualNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface VisualEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  label?: string;
  style?: Record<string, unknown>;
}

export interface VisualConfig {
  nodes: VisualNode[];
  edges: VisualEdge[];
  viewport: { x: number; y: number; zoom: number };
}

export interface SequenceGenerateRequest {
  prompt: string;
  target_industry?: string;
  num_steps?: number;
  channels?: string[];
  include_ab_test?: boolean;
  include_conditionals?: boolean;
}

export interface SequenceGenerateResponse {
  success: boolean;
  sequence_id: string | null;
  sequence_name: string | null;
  steps_generated: number;
  channels_used: string[];
  ai_platforms_consulted: string[];
  visual_config: VisualConfig | null;
  error: string | null;
}

export interface ABVariantAnalytics {
  step_position: number;
  variant: string;
  sent: number;
  opened: number;
  replied: number;
  bounced: number;
  open_rate: number;
  reply_rate: number;
}

export interface Sequence {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  steps: SequenceStep[];
  enrolled_count: number;
  visual_config: VisualConfig | null;
  ai_generated: boolean;
  ai_generation_prompt: string | null;
  ai_generation_metadata: Record<string, unknown> | null;
}

export interface SequenceListResponse {
  items: Sequence[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStats {
  total_leads: number;
  active_consents: number;
  touches_sent: number;
  response_rate: number;
}

export interface DeliverabilityStats {
  total_sent: number;
  total_bounced: number;
  bounce_rate: number;
  spam_complaints: number;
  spam_rate: number;
  warmup_active: number;
  warmup_completed: number;
}

export interface SequencePerformance {
  sequence_id: string;
  sequence_name: string;
  enrolled: number;
  active: number;
  completed: number;
  open_rate: number;
  reply_rate: number;
  bounce_rate: number;
}

export interface Domain {
  id: string;
  domain: string;
  health_score: number;
  warmup_progress: number;
  total_sent: number;
  total_bounced: number;
  created_at: string;
}

export interface WarmupStatus {
  inbox_id: string;
  date: string;
  emails_sent: number;
  emails_target: number;
  bounce_rate: number;
  spam_rate: number;
  open_rate: number;
  status: string;
}

export interface StepAnalytics {
  step_position: number;
  step_type: string;
  sent: number;
  opened: number;
  replied: number;
  bounced: number;
}

export interface SequenceAnalytics {
  sequence_id: string;
  total_enrolled: number;
  active: number;
  completed: number;
  steps: StepAnalytics[];
  ab_results: ABVariantAnalytics[];
}

export interface AuditTrail {
  lead_id: string;
  consents: Record<string, unknown>[];
  touch_logs: Record<string, unknown>[];
  dnc_records: Record<string, unknown>[];
}

// ── Phase 5: Reply + Monitor Types ────────────────────

export interface ReplyLog {
  id: string;
  enrollment_id: string | null;
  sequence_id: string | null;
  lead_id: string | null;
  lead_name: string | null;
  lead_email: string | null;
  channel: string;
  subject: string | null;
  body_snippet: string | null;
  sentiment: string | null;
  sentiment_confidence: number;
  ai_analysis: Record<string, unknown> | null;
  ai_suggested_action: string | null;
  received_at: string;
  processed_at: string | null;
}

export interface ReplyListResponse {
  items: ReplyLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface EnrollmentMonitor {
  id: string;
  lead_id: string;
  lead_name: string;
  lead_email: string;
  lead_company: string;
  current_step: number;
  total_steps: number;
  status: string;
  enrolled_at: string;
  last_touch_at: string | null;
  last_state_change_at: string | null;
  hole_filler_triggered: boolean;
  escalation_channel: string | null;
  touch_history: Record<string, unknown>[];
  reply_snippets: Record<string, unknown>[];
}

export interface SequenceMonitor {
  sequence_id: string;
  sequence_name: string;
  status: string;
  total_enrolled: number;
  active: number;
  completed: number;
  replied: number;
  failed: number;
  enrollments: EnrollmentMonitor[];
  channel_breakdown: Record<string, number>;
  daily_send_count: Record<string, number>;
}

export interface ChannelHealth {
  channel: string;
  sent_today: number;
  limit: number;
  utilization: number;
  bounce_rate: number;
  reply_rate: number;
  last_failure: string | null;
}

// ── Template Types ────────────────────────────────────

export interface MessageTemplate {
  id: string;
  name: string;
  channel: string;
  category: string;
  subject: string | null;
  html_body: string | null;
  plain_body: string;
  linkedin_action: string | null;
  variables: string[] | null;
  variant_group: string | null;
  variant_label: string | null;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  items: MessageTemplate[];
  total: number;
  page: number;
  page_size: number;
}

export interface TemplatePreview {
  rendered_subject: string | null;
  rendered_plain_body: string;
  rendered_html_body: string | null;
  variables_used: string[];
  warnings: string[];
}

export interface SequencePreset {
  name: string;
  description: string;
  category: string;
  steps: {
    step_type: string;
    position: number;
    delay_hours: number;
    has_template: boolean;
    template_name: string | null;
    channel: string | null;
  }[];
}

export interface PresetDeployResult {
  sequence_id: string;
  sequence_name: string;
  templates_created: number;
  steps_created: number;
  templates: { id: string; name: string }[];
  status: string;
}

// ── Analytics Endpoint Types ──────────────────────────

export interface OutreachDailyEntry {
  day: string;
  email: number;
  sms: number;
  linkedin: number;
}

export interface RecentActivityEntry {
  id: number;
  text: string;
  time: string;
  type: string;
}

export interface SequencePerformanceEntry {
  sequence_id: string;
  total_sends: number;
  opens: number;
  replies: number;
  bounces: number;
}

export interface ResponseTrendEntry {
  week: string;
  rate: number;
}

export interface ChannelBreakdownEntry {
  name: string;
  value: number;
}

export interface BounceDailyEntry {
  date: string;
  bounced: number;
  sent: number;
}

// ── API Functions ──────────────────────────────────────

export const leadsApi = {
  list: (page = 1, pageSize = 20) =>
    api.get<LeadListResponse>(`/leads/?page=${page}&page_size=${pageSize}`),
  get: (id: string) => api.get<Lead>(`/leads/${id}`),
  create: (data: Partial<Lead>) => api.post<Lead>("/leads/", data),
  import: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/leads/import/csv", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

export interface DNCEntry {
  id: string;
  identifier: string;
  channel: string;
  reason: string;
  source: string;
  blocked_at: string;
  created_at: string;
}

export interface DNCListResponse {
  items: DNCEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditTrailEntry {
  id: number | string;
  who: string;
  when: string;
  channel: string;
  method: string;
  proof: string;
}

export const complianceApi = {
  check: (lead_id: string, channel: string) =>
    api.post<ComplianceCheck>("/compliance/check", { lead_id, channel }),
  grantConsent: (
    lead_id: string,
    channel: string,
    method: string,
    proof: object
  ) => api.post("/compliance/consent", { lead_id, channel, method, proof }),
  revokeConsent: (lead_id: string, channel: string) =>
    api.post("/compliance/revoke", { lead_id, channel }),
  audit: (lead_id: string) => api.get<AuditTrail>(`/compliance/audit/${lead_id}`),
  listDnc: (page = 1, pageSize = 50, search = "") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set("search", search);
    return api.get<DNCListResponse>(`/compliance/dnc?${params.toString()}`);
  },
  addDnc: (identifier: string, channel: string, reason: string, source: string) =>
    api.post<DNCEntry>("/compliance/dnc", { identifier, channel, reason, source }),
  removeDnc: (id: string) => api.delete(`/compliance/dnc/${id}`),
};

export const sequencesApi = {
  list: (page = 1, pageSize = 20) =>
    api.get<SequenceListResponse>(`/sequences/?page=${page}&page_size=${pageSize}`),
  get: (id: string) => api.get<Sequence>(`/sequences/${id}`),
  create: (data: { name: string; description?: string; status?: string; visual_config?: VisualConfig }) =>
    api.post<Sequence>("/sequences/", data),
  update: (id: string, data: { name?: string; description?: string; status?: string; visual_config?: VisualConfig }) =>
    api.put<Sequence>(`/sequences/${id}`, data),
  delete: (id: string) => api.delete(`/sequences/${id}`),
  addStep: (id: string, data: {
    step_type: string; position: number; config?: object; delay_hours?: number;
    condition?: object; true_next_position?: number; false_next_position?: number;
    ab_variants?: object; is_ab_test?: boolean; node_id?: string;
  }) => api.post<SequenceStep>(`/sequences/${id}/steps`, data),
  deleteStep: (sequenceId: string, stepId: string) =>
    api.delete(`/sequences/${sequenceId}/steps/${stepId}`),
  enroll: (id: string, lead_ids: string[]) =>
    api.post(`/sequences/${id}/enroll`, { lead_ids }),
  analytics: (id: string) =>
    api.get<SequenceAnalytics>(`/sequences/${id}/analytics`),
  // Phase 4: AI generation
  generate: (data: SequenceGenerateRequest) =>
    api.post<SequenceGenerateResponse>("/sequences/generate", data),
  // Phase 4: Visual builder
  getVisualConfig: (id: string) =>
    api.get<{ sequence_id: string; visual_config: VisualConfig | null; steps: SequenceStep[] }>(
      `/sequences/${id}/visual`
    ),
  saveVisualConfig: (id: string, data: { visual_config: VisualConfig; steps?: SequenceStep[] }) =>
    api.put<{ sequence_id: string; visual_config: VisualConfig | null; steps: SequenceStep[] }>(
      `/sequences/${id}/visual`, data
    ),
  // Phase 4: Enrollment management
  pauseEnrollment: (sequenceId: string, enrollmentId: string) =>
    api.post(`/sequences/${sequenceId}/enrollments/${enrollmentId}/pause`),
  resumeEnrollment: (sequenceId: string, enrollmentId: string) =>
    api.post(`/sequences/${sequenceId}/enrollments/${enrollmentId}/resume`),
  // Phase 5: Monitor + Reply
  monitor: (id: string) =>
    api.get<SequenceMonitor>(`/sequences/${id}/monitor`),
  channelHealth: (id: string) =>
    api.get<ChannelHealth[]>(`/sequences/${id}/channel-health`),
  replyInbox: (page = 1, pageSize = 20, sentiment?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (sentiment) params.set("sentiment", sentiment);
    return api.get<ReplyListResponse>(`/sequences/replies/inbox?${params.toString()}`);
  },
};

export const analyticsApi = {
  dashboard: () => api.get<DashboardStats>("/analytics/dashboard"),
  deliverability: () => api.get<DeliverabilityStats>("/analytics/deliverability"),
  sequences: () =>
    api.get<{ sequences: SequencePerformance[] }>("/analytics/sequences"),
  outreachDaily: () =>
    api.get<OutreachDailyEntry[]>("/analytics/outreach-daily"),
  recentActivity: () =>
    api.get<RecentActivityEntry[]>("/analytics/recent-activity"),
  sequencePerformance: () =>
    api.get<SequencePerformanceEntry[]>("/analytics/sequence-performance"),
  responseTrends: () =>
    api.get<ResponseTrendEntry[]>("/analytics/response-trends"),
  channelBreakdown: () =>
    api.get<ChannelBreakdownEntry[]>("/analytics/channel-breakdown"),
  bounceDaily: () =>
    api.get<BounceDailyEntry[]>("/analytics/bounce-daily"),
};

export const deliverabilityApi = {
  listDomains: () => api.get<Domain[]>("/deliverability/domains"),
  addDomain: (domain: string) =>
    api.post<Domain>("/deliverability/domains", { domain }),
  warmupStatus: () => api.get<WarmupStatus[]>("/deliverability/warmup"),
};

export const templatesApi = {
  list: (page = 1, pageSize = 20, channel?: string, category?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (channel) params.set("channel", channel);
    if (category) params.set("category", category);
    return api.get<TemplateListResponse>(`/templates/?${params.toString()}`);
  },
  get: (id: string) => api.get<MessageTemplate>(`/templates/${id}`),
  create: (data: Partial<MessageTemplate>) => api.post<MessageTemplate>("/templates/", data),
  update: (id: string, data: Partial<MessageTemplate>) =>
    api.put<MessageTemplate>(`/templates/${id}`, data),
  delete: (id: string) => api.delete(`/templates/${id}`),
  preview: (data: {
    template_id?: string;
    plain_body?: string;
    html_body?: string;
    subject?: string;
    context?: Record<string, string>;
  }) => api.post<TemplatePreview>("/templates/preview", data),
};

export const presetsApi = {
  list: () => api.get<SequencePreset[]>("/presets/"),
  deploy: (index: number) => api.post<PresetDeployResult>(`/presets/${index}/deploy`),
};

// ── Phase 7: Chat API ────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  sources?: string[];
}

export interface ChatHistoryItem {
  id: string;
  message: string;
  response: string;
  ai_sources: string[];
  created_at: string;
}

export interface ChatHistoryResponse {
  items: ChatHistoryItem[];
  total: number;
  session_id: string;
}

export const chatApi = {
  // Streaming endpoint — use fetch directly for SSE
  sendMessage: async (message: string, session_id?: string) => {
    const session = await getSession();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if ((session as any)?.accessToken) {
      headers["Authorization"] = `Bearer ${(session as any).accessToken}`;
    }
    return fetch("/api/v1/chat/", {
      method: "POST",
      headers,
      body: JSON.stringify({ message, session_id }),
    });
  },
  // Non-streaming endpoint
  sendMessageSync: (message: string, session_id?: string) =>
    api.post("/chat/sync", { message, session_id }),
  // Get history
  getHistory: (session_id: string) =>
    api.get<ChatHistoryResponse>(`/chat/history?session_id=${session_id}`),
};

export default api;
