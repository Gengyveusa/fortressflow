import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

export interface Lead {
  id: string;
  email: string;
  phone?: string;
  first_name?: string;
  last_name?: string;
  company?: string;
  title?: string;
  source: string;
  meeting_verified: boolean;
  created_at: string;
}

export interface ComplianceCheck {
  can_send: boolean;
  reason: string;
}

export const leadsApi = {
  list: (page = 1, limit = 20) =>
    api.get<{ items: Lead[]; total: number; page: number; pages: number }>(
      `/leads/?page=${page}&limit=${limit}`
    ),
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
  audit: (lead_id: string) => api.get(`/compliance/audit/${lead_id}`),
};

export default api;
