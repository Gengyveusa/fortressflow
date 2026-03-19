"use client";

import { useQuery } from "@tanstack/react-query";
import {
  analyticsApi,
  complianceApi,
  deliverabilityApi,
  leadsApi,
  presetsApi,
  sequencesApi,
  templatesApi,
} from "@/lib/api";

// ── Leads ──────────────────────────────────────────────

export function useLeads(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["leads", page, pageSize],
    queryFn: () => leadsApi.list(page, pageSize).then((r) => r.data),
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: ["lead", id],
    queryFn: () => leadsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

// ── Sequences ──────────────────────────────────────────

export function useSequences(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["sequences", page, pageSize],
    queryFn: () => sequencesApi.list(page, pageSize).then((r) => r.data),
  });
}

export function useSequence(id: string) {
  return useQuery({
    queryKey: ["sequence", id],
    queryFn: () => sequencesApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useSequenceAnalytics(id: string) {
  return useQuery({
    queryKey: ["sequence-analytics", id],
    queryFn: () => sequencesApi.analytics(id).then((r) => r.data),
    enabled: !!id,
  });
}

// ── Analytics ──────────────────────────────────────────

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => analyticsApi.dashboard().then((r) => r.data),
  });
}

export function useDeliverabilityStats() {
  return useQuery({
    queryKey: ["deliverability-stats"],
    queryFn: () => analyticsApi.deliverability().then((r) => r.data),
  });
}

export function useSequencesAnalytics() {
  return useQuery({
    queryKey: ["sequences-analytics"],
    queryFn: () => analyticsApi.sequences().then((r) => r.data),
  });
}

// ── Deliverability ─────────────────────────────────────

export function useDomains() {
  return useQuery({
    queryKey: ["domains"],
    queryFn: () => deliverabilityApi.listDomains().then((r) => r.data),
  });
}

export function useWarmupStatus() {
  return useQuery({
    queryKey: ["warmup-status"],
    queryFn: () => deliverabilityApi.warmupStatus().then((r) => r.data),
  });
}

// ── Compliance ─────────────────────────────────────────

export function useAuditTrail(leadId: string) {
  return useQuery({
    queryKey: ["audit-trail", leadId],
    queryFn: () => complianceApi.audit(leadId).then((r) => r.data),
    enabled: !!leadId,
  });
}

// ── Templates ─────────────────────────────────────────

export function useTemplates(page = 1, pageSize = 20, channel?: string, category?: string) {
  return useQuery({
    queryKey: ["templates", page, pageSize, channel, category],
    queryFn: () => templatesApi.list(page, pageSize, channel, category).then((r) => r.data),
  });
}

export function useTemplate(id: string) {
  return useQuery({
    queryKey: ["template", id],
    queryFn: () => templatesApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

// ── Presets ───────────────────────────────────────────

export function usePresets() {
  return useQuery({
    queryKey: ["presets"],
    queryFn: () => presetsApi.list().then((r) => r.data),
  });
}
