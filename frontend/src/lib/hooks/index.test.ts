import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock the API module
vi.mock("@/lib/api", () => ({
  analyticsApi: {
    dashboard: vi.fn(),
    deliverability: vi.fn(),
    sequences: vi.fn(),
    outreachDaily: vi.fn(),
    recentActivity: vi.fn(),
    sequencePerformance: vi.fn(),
    responseTrends: vi.fn(),
    channelBreakdown: vi.fn(),
    bounceDaily: vi.fn(),
  },
  leadsApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
  sequencesApi: {
    list: vi.fn(),
    get: vi.fn(),
    analytics: vi.fn(),
  },
  deliverabilityApi: {
    listDomains: vi.fn(),
    warmupStatus: vi.fn(),
  },
  complianceApi: {
    audit: vi.fn(),
  },
  templatesApi: {
    list: vi.fn(),
    get: vi.fn(),
  },
  presetsApi: {
    list: vi.fn(),
  },
}));

import {
  analyticsApi,
  leadsApi,
  sequencesApi,
  presetsApi,
} from "@/lib/api";

import {
  useDashboardStats,
  useDeliverabilityStats,
  useOutreachDaily,
  useRecentActivity,
  useSequencePerformance,
  useResponseTrends,
  useChannelBreakdown,
  useBounceDaily,
  useLeads,
  useSequences,
  usePresets,
  useSettings,
} from "./index";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe("Analytics hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useDashboardStats fetches dashboard data", async () => {
    const mockData = {
      total_leads: 100,
      active_consents: 50,
      touches_sent: 200,
      response_rate: 0.15,
    };
    vi.mocked(analyticsApi.dashboard).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useDashboardStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useDeliverabilityStats fetches deliverability data", async () => {
    const mockData = {
      total_sent: 1000,
      total_bounced: 10,
      bounce_rate: 0.01,
      spam_complaints: 1,
      spam_rate: 0.001,
      warmup_active: 2,
      warmup_completed: 5,
    };
    vi.mocked(analyticsApi.deliverability).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useDeliverabilityStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useOutreachDaily fetches daily outreach data", async () => {
    const mockData = [
      { day: "Mon", email: 10, sms: 5, linkedin: 3 },
    ];
    vi.mocked(analyticsApi.outreachDaily).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useOutreachDaily(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useRecentActivity fetches recent activity", async () => {
    const mockData = [
      { id: 1, text: "Sent email", time: "2m ago", type: "lead" },
    ];
    vi.mocked(analyticsApi.recentActivity).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useRecentActivity(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useSequencePerformance fetches performance data", async () => {
    const mockData = [
      { sequence_id: "1", total_sends: 100, opens: 50, replies: 10, bounces: 2 },
    ];
    vi.mocked(analyticsApi.sequencePerformance).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useSequencePerformance(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useResponseTrends fetches response trends", async () => {
    const mockData = [{ week: "2024-W01", rate: 12.5 }];
    vi.mocked(analyticsApi.responseTrends).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useResponseTrends(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useChannelBreakdown fetches channel breakdown", async () => {
    const mockData = [
      { name: "email", value: 100 },
      { name: "sms", value: 20 },
    ];
    vi.mocked(analyticsApi.channelBreakdown).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useChannelBreakdown(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("useBounceDaily fetches bounce data", async () => {
    const mockData = [{ date: "2024-01-01", bounced: 5, sent: 100 }];
    vi.mocked(analyticsApi.bounceDaily).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useBounceDaily(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("handles API error in useDashboardStats", async () => {
    vi.mocked(analyticsApi.dashboard).mockRejectedValue(
      new Error("Network error")
    );

    const { result } = renderHook(() => useDashboardStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
  });
});

describe("Resource hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useLeads fetches paginated leads", async () => {
    const mockData = { items: [], total: 0, page: 1, page_size: 20 };
    vi.mocked(leadsApi.list).mockResolvedValue({ data: mockData } as never);

    const { result } = renderHook(() => useLeads(1, 20), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(leadsApi.list).toHaveBeenCalledWith(1, 20);
  });

  it("useSequences fetches paginated sequences", async () => {
    const mockData = { items: [], total: 0, page: 1, page_size: 20 };
    vi.mocked(sequencesApi.list).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => useSequences(1, 20), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it("usePresets fetches presets list", async () => {
    const mockData = [{ name: "Cold Outreach", description: "test", category: "cold", steps: [] }];
    vi.mocked(presetsApi.list).mockResolvedValue({
      data: mockData,
    } as never);

    const { result } = renderHook(() => usePresets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });
});

describe("useSettings", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns empty settings initially", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.settings).toEqual({});
  });

  it("updates settings", async () => {
    const { result } = renderHook(() => useSettings());

    result.current.updateSettings({
      warmup: {
        volumeCap: 100,
        rampMultiplier: 1.15,
        initialDailyVolume: 5,
        durationWeeks: 6,
      },
    });

    await waitFor(() => {
      expect(result.current.settings.warmup?.volumeCap).toBe(100);
    });
  });

  it("resets settings", async () => {
    const { result } = renderHook(() => useSettings());

    result.current.updateSettings({
      warmup: {
        volumeCap: 100,
        rampMultiplier: 1.15,
        initialDailyVolume: 5,
        durationWeeks: 6,
      },
    });

    result.current.resetSettings();

    await waitFor(() => {
      expect(result.current.settings).toEqual({});
    });
  });

  it("persists settings to localStorage", async () => {
    const { result } = renderHook(() => useSettings());

    result.current.updateSettings({
      alertThresholds: {
        bounceRatePause: 0.05,
        spamRatePause: 0.001,
        openRateMinimum: 0.15,
      },
    });

    await waitFor(() => {
      const stored = localStorage.getItem("fortressflow-settings");
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored!);
      expect(parsed.alertThresholds.bounceRatePause).toBe(0.05);
    });
  });

  it("deep merges apiKeys", async () => {
    const { result } = renderHook(() => useSettings());

    result.current.updateSettings({ apiKeys: { apollo: "key1" } });
    await waitFor(() => {
      expect(result.current.settings.apiKeys?.apollo).toBe("key1");
    });

    result.current.updateSettings({ apiKeys: { zoominfo: "key2" } });
    await waitFor(() => {
      expect(result.current.settings.apiKeys?.apollo).toBe("key1");
      expect(result.current.settings.apiKeys?.zoominfo).toBe("key2");
    });
  });
});
