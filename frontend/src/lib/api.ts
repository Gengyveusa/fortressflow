import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
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
  created_at: string;
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
}

export interface AuditTrail {
  lead_id: string;
  consents: Record<string, unknown>[];
  touch_logs: Record<string, unknown>[];
  dnc_records: Record<string, unknown>[];
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
};

export const sequencesApi = {
  list: (page = 1, pageSize = 20) =>
    api.get<SequenceListResponse>(`/sequences/?page=${page}&page_size=${pageSize}`),
  get: (id: string) => api.get<Sequence>(`/sequences/${id}`),
  create: (data: { name: string; description?: string; status?: string }) =>
    api.post<Sequence>("/sequences/", data),
  update: (id: string, data: { name?: string; description?: string; status?: string }) =>
    api.put<Sequence>(`/sequences/${id}`, data),
  delete: (id: string) => api.delete(`/sequences/${id}`),
  addStep: (id: string, data: { step_type: string; position: number; config?: object; delay_hours?: number }) =>
    api.post<SequenceStep>(`/sequences/${id}/steps`, data),
  enroll: (id: string, lead_ids: string[]) =>
    api.post(`/sequences/${id}/enroll`, { lead_ids }),
  analytics: (id: string) =>
    api.get<SequenceAnalytics>(`/sequences/${id}/analytics`),
};

export const analyticsApi = {
  dashboard: () => api.get<DashboardStats>("/analytics/dashboard"),
  deliverability: () => api.get<DeliverabilityStats>("/analytics/deliverability"),
  sequences: () =>
    api.get<{ sequences: SequencePerformance[] }>("/analytics/sequences"),
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

export default api;
