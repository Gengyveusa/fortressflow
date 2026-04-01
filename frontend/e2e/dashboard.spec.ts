import { test, expect, Page } from "@playwright/test";

const MOCK_HEATMAP = {
  agents: [
    {
      agent_name: "groq",
      success_rate: 97.2,
      total_executions: 14832,
      avg_latency_ms: 89,
      status: "healthy",
      errors_24h: 3,
    },
    {
      agent_name: "twilio",
      success_rate: 82.4,
      total_executions: 3200,
      avg_latency_ms: 1200,
      status: "degraded",
      errors_24h: 12,
    },
  ],
};

const MOCK_LIVE_FEED = {
  items: [
    {
      id: "feed-1",
      agent: "groq",
      action: "generate_email",
      status: "success",
      latency_ms: 87,
      timestamp: "2026-03-31T10:00:00Z",
      params_preview: '{"lead_id":"L-4821"}',
    },
    {
      id: "feed-2",
      agent: "twilio",
      action: "send_sms",
      status: "error",
      latency_ms: 3100,
      timestamp: "2026-03-31T09:59:00Z",
      params_preview: '{"phone":"+15551234567"}',
    },
  ],
};

const MOCK_PROVENANCE = {
  source_breakdown: {
    csv_import: 4200,
    apollo: 3100,
    zoominfo: 2800,
    hubspot: 1900,
    manual: 600,
  },
  enrichment_coverage: {
    total_leads: 12600,
    enriched: 9880,
    verified_phone: 7824,
    verified_email: 11554,
    crm_synced: 10748,
  },
};

const MOCK_JOURNEY = {
  stages: [
    { stage: "Discovered", count: 12600, conversion_pct: 100 },
    { stage: "Enriched", count: 9880, conversion_pct: 78.4 },
    { stage: "Contacted", count: 7210, conversion_pct: 73.0 },
    { stage: "Engaged", count: 3840, conversion_pct: 53.3 },
    { stage: "Replied", count: 1920, conversion_pct: 50.0 },
    { stage: "Meeting", count: 640, conversion_pct: 33.3 },
    { stage: "Won", count: 185, conversion_pct: 28.9 },
  ],
};

const MOCK_TIMELINE = {
  timeline: [
    {
      timestamp: "2026-03-29T10:00:00Z",
      event: "Lead Created",
      source: "CSV Import",
      details: "Imported from Q1 prospect list",
    },
    {
      timestamp: "2026-03-29T10:12:00Z",
      event: "Enriched",
      source: "Apollo",
      details: "Added title, company size, LinkedIn URL",
    },
  ],
};

async function mockMissionControlAPIs(page: Page) {
  await page.route("**/api/v1/monitor/agent-heatmap", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_HEATMAP),
    })
  );

  await page.route("**/api/v1/monitor/agent-live-feed", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_LIVE_FEED),
    })
  );

  await page.route("**/api/v1/monitor/provenance/timeline?email=**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_TIMELINE),
    })
  );

  await page.route("**/api/v1/monitor/provenance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PROVENANCE),
    })
  );

  await page.route("**/api/v1/monitor/journey-funnel", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_JOURNEY),
    })
  );
}

async function mockMissionControlEmpty(page: Page) {
  await page.route("**/api/v1/monitor/agent-heatmap", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ agents: [] }),
    })
  );

  await page.route("**/api/v1/monitor/agent-live-feed", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    })
  );

  await page.route("**/api/v1/monitor/provenance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source_breakdown: {},
        enrichment_coverage: { total_leads: 0 },
      }),
    })
  );

  await page.route("**/api/v1/monitor/journey-funnel", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ stages: [] }),
    })
  );
}

test.describe("Mission Control Dashboard", () => {
  test("loads the dashboard and shows the page title", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.goto("/");

    await expect(page).toHaveTitle(/FortressFlow/i);
    await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  });

  test("shows live operations data from monitor APIs", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.goto("/");

    await expect(page.getByRole("tab", { name: /Live Operations/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Agent Heatmap" })).toBeVisible();
    await expect(page.getByLabel(/Agent Groq LLM:/)).toBeVisible();
    await expect(page.getByLabel(/Agent Twilio:/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Live Activity Feed" })).toBeVisible();
    await expect(page.getByText("generate_email")).toBeVisible();
    await expect(page.getByText("send_sms")).toBeVisible();
  });

  test("shows loading skeletons while monitor data is fetching", async ({ page }) => {
    await page.route("**/api/v1/monitor/agent-heatmap", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_HEATMAP),
      });
    });
    await page.route("**/api/v1/monitor/agent-live-feed", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_LIVE_FEED),
      })
    );
    await page.route("**/api/v1/monitor/provenance", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PROVENANCE),
      })
    );
    await page.route("**/api/v1/monitor/journey-funnel", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_JOURNEY),
      })
    );

    await page.goto("/");

    await expect(page.locator(".animate-pulse").first()).toBeVisible();
  });

  test("shows empty live activity state gracefully", async ({ page }) => {
    await mockMissionControlEmpty(page);
    await page.goto("/");

    await expect(page.getByText("0 agents monitored")).toBeVisible();
    await expect(page.getByText("No recent activity")).toBeVisible();
  });

  test("data provenance tab shows source breakdown and coverage metrics", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.goto("/");

    await page.getByRole("tab", { name: /Data Provenance/i }).click();

    await expect(page.getByRole("heading", { name: "Source Breakdown" })).toBeVisible();
    await expect(page.getByText("Enrichment Coverage")).toBeVisible();
    await expect(page.getByText("Data Enrichment")).toBeVisible();
    await expect(page.getByText("Phone Verification")).toBeVisible();
    await expect(page.getByText("12.6K", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("CSV Import")).toBeVisible();
  });

  test("provenance search loads a lead timeline", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.goto("/");

    await page.getByRole("tab", { name: /Data Provenance/i }).click();
    await page.getByLabel("Search lead by email").fill("jane@acme.com");
    await page.getByRole("button", { name: /Search provenance/i }).click();

    await expect(page.getByText(/Provenance Timeline for/i)).toBeVisible();
    const timeline = page.getByLabel("Lead provenance timeline");
    await expect(timeline.getByText("Lead Created")).toBeVisible();
    await expect(timeline.getByText("Enriched")).toBeVisible();
  });

  test("lead journey tab shows funnel and summary stats", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.goto("/");

    await page.getByRole("tab", { name: /Lead Journey/i }).click();

    await expect(page.getByRole("heading", { name: "Lead Journey Funnel" })).toBeVisible();
    await expect(page.getByText("Active Sequences")).toBeVisible();
    await expect(page.getByText("Recent Positive Signals")).toBeVisible();
    await expect(page.getByText("Total Discovered")).toBeVisible();
    await expect(page.getByText("12.6K", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("No positive signals yet")).toBeVisible();
  });

  test("sidebar navigation is visible on desktop", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");

    await expect(page.locator("aside, nav").first()).toBeVisible();
  });

  test("navigation links exist in sidebar", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");

    await expect(page.getByRole("link", { name: /Sequences/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Leads/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Settings/i }).first()).toBeVisible();
  });

  test("page renders correctly at mobile viewport", async ({ page }) => {
    await mockMissionControlAPIs(page);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");

    await expect(page).toHaveTitle(/FortressFlow/i);
    await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  });
});
