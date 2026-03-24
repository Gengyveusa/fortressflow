"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useCallback } from "react";
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

// ── Analytics (real endpoints) ─────────────────────────

export function useOutreachDaily() {
  return useQuery({
    queryKey: ["outreach-daily"],
    queryFn: async () => {
      const raw = (await analyticsApi.outreachDaily().then((r) => r.data)) as any[];
      // Backend returns [{date, channel, count}] — pivot to [{day, email, sms, linkedin}]
      const byDay: Record<string, { day: string; email: number; sms: number; linkedin: number }> = {};
      for (const row of raw) {
        const day = row.date ?? row.day;
        if (!byDay[day]) byDay[day] = { day, email: 0, sms: 0, linkedin: 0 };
        const ch = (row.channel ?? "").toLowerCase();
        if (ch === "email") byDay[day].email += row.count ?? 0;
        else if (ch === "sms") byDay[day].sms += row.count ?? 0;
        else if (ch === "linkedin") byDay[day].linkedin += row.count ?? 0;
      }
      return Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day));
    },
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ["recent-activity"],
    queryFn: async () => {
      const raw = (await analyticsApi.recentActivity().then((r) => r.data)) as any[];
      // Backend returns [{id, lead_name, action, channel, created_at}]
      // Dashboard expects [{id, text, time, type}]
      const actionTypeMap: Record<string, string> = {
        sent: "sequence",
        opened: "sequence",
        replied: "lead",
        bounced: "bounce",
        complained: "bounce",
      };
      return raw.map((r) => {
        const action = r.action ?? "unknown";
        const ago = r.created_at ? formatTimeAgo(r.created_at) : "";
        return {
          id: r.id ?? Math.random(),
          text: `${r.lead_name ?? r.lead_email ?? "Unknown"} — ${action} via ${r.channel ?? "email"}`,
          time: ago,
          type: actionTypeMap[action] ?? "lead",
        };
      });
    },
  });
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function useSequencePerformance() {
  return useQuery({
    queryKey: ["sequence-performance"],
    queryFn: () => analyticsApi.sequencePerformance().then((r) => r.data),
  });
}

export function useResponseTrends() {
  return useQuery({
    queryKey: ["response-trends"],
    queryFn: async () => {
      const raw = (await analyticsApi.responseTrends().then((r) => r.data)) as any[];
      // Backend returns [{week, sent, replied, response_rate}] — page expects [{week, rate}]
      return raw.map((r) => ({ week: r.week, rate: r.response_rate ?? 0 }));
    },
  });
}

export function useChannelBreakdown() {
  return useQuery({
    queryKey: ["channel-breakdown"],
    queryFn: async () => {
      const raw = (await analyticsApi.channelBreakdown().then((r) => r.data)) as any[];
      // Backend returns [{channel, count}] — page expects [{name, value}]
      return raw.map((r) => ({ name: r.channel ?? "unknown", value: r.count ?? 0 }));
    },
  });
}

export function useBounceDaily() {
  return useQuery({
    queryKey: ["bounce-daily"],
    queryFn: async () => {
      const raw = (await analyticsApi.bounceDaily().then((r) => r.data)) as any[];
      // Backend returns [{date, count}] — page expects [{date, bounced, sent}]
      return raw.map((r) => ({ date: r.date, bounced: r.count ?? 0, sent: 0 }));
    },
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

// ── Settings ───────────────────────────────────────────────

export interface AppSettings {
  apiKeys?: Record<string, string>;
  warmup?: {
    volumeCap: number;
    rampMultiplier: number;
    initialDailyVolume: number;
    durationWeeks: number;
  };
  alertThresholds?: {
    bounceRatePause: number;
    spamRatePause: number;
    openRateMinimum: number;
  };
}

const SETTINGS_KEY = "fortressflow-settings";

function loadSettings(): AppSettings {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? (JSON.parse(raw) as AppSettings) : {};
  } catch {
    return {};
  }
}

function saveSettings(s: AppSettings): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings>({});

  useEffect(() => {
    setSettings(loadSettings());
  }, []);

  const updateSettings = useCallback((patch: Partial<AppSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      // Deep merge apiKeys
      if (patch.apiKeys) {
        next.apiKeys = { ...(prev.apiKeys ?? {}), ...patch.apiKeys };
      }
      saveSettings(next);
      return next;
    });
  }, []);

  const resetSettings = useCallback(() => {
    saveSettings({});
    setSettings({});
  }, []);

  return { settings, updateSettings, resetSettings };
}
