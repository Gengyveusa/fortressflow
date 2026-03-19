import { test, expect, Page } from "@playwright/test";

/**
 * Dashboard E2E Tests — FortressFlow Phase 6
 *
 * All API calls are intercepted via page.route() so tests run
 * without a live backend. Tests verify UI behaviour in response to
 * happy-path data, error states, and user interactions.
 */

// ── Shared Mock Payloads ──────────────────────────────────────────────────

const MOCK_DASHBOARD_STATS = {
  total_leads: 1_247,
  active_consents: 1_052,
  touches_sent: 8_340,
  response_rate: 12.5,
};

const MOCK_DELIVERABILITY_STATS = {
  total_sent: 8_340,
  total_bounced: 42,
  bounce_rate: 0.50,
  spam_complaints: 3,
  spam_rate: 0.04,
  warmup_active: 3,
  warmup_completed: 7,
};

// ── Helpers ───────────────────────────────────────────────────────────────

async function mockDashboardAPIs(page: Page) {
  await page.route("**/api/v1/analytics/dashboard", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_DASHBOARD_STATS),
    })
  );
  await page.route("**/api/v1/analytics/deliverability", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_DELIVERABILITY_STATS),
    })
  );
}

async function mockDashboardAPIError(page: Page) {
  await page.route("**/api/v1/analytics/dashboard", (route) =>
    route.fulfill({ status: 500, body: "Internal Server Error" })
  );
  await page.route("**/api/v1/analytics/deliverability", (route) =>
    route.fulfill({ status: 500, body: "Internal Server Error" })
  );
}

// ── Test Suite ────────────────────────────────────────────────────────────

test.describe("Dashboard Page", () => {
  test("loads the dashboard and shows the page title", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    // The page title is set in layout metadata
    await expect(page).toHaveTitle(/FortressFlow/i);
  });

  test("shows four stat cards after data loads", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    // Wait for loading skeletons to disappear
    await page.waitForSelector("text=Total Leads", { timeout: 10_000 });

    await expect(page.getByText("Total Leads")).toBeVisible();
    await expect(page.getByText("Active Consents")).toBeVisible();
    await expect(page.getByText("Touches Sent")).toBeVisible();
    await expect(page.getByText("Response Rate")).toBeVisible();
  });

  test("stat cards display correct values from API", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=1,247", { timeout: 10_000 });

    // Total Leads value
    await expect(page.getByText("1,247")).toBeVisible();
    // Active Consents value
    await expect(page.getByText("1,052")).toBeVisible();
    // Touches Sent value
    await expect(page.getByText("8,340")).toBeVisible();
  });

  test("shows loading skeleton while stats are fetching", async ({ page }) => {
    // Delay API response so we can catch the loading state
    await page.route("**/api/v1/analytics/dashboard", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_DASHBOARD_STATS),
      });
    });
    await page.route("**/api/v1/analytics/deliverability", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_DELIVERABILITY_STATS),
      })
    );

    await page.goto("/");

    // Pulse animation skeleton should be present immediately
    const skeleton = page.locator(".animate-pulse").first();
    await expect(skeleton).toBeVisible();
  });

  test("handles API error gracefully — shows dash placeholder", async ({
    page,
  }) => {
    await mockDashboardAPIError(page);
    await page.goto("/");

    // Dashboard should show "—" placeholder for failed values
    await page.waitForSelector("text=Total Leads", { timeout: 10_000 });
    const dashPlaceholders = page.getByText("—");
    await expect(dashPlaceholders.first()).toBeVisible();
  });

  test("deliverability health card shows bounce rate", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=Deliverability Health", { timeout: 10_000 });

    await expect(page.getByText("Deliverability Health")).toBeVisible();
    await expect(page.getByText("Bounce Rate")).toBeVisible();
    await expect(page.getByText("Spam Rate")).toBeVisible();
  });

  test("deliverability health error shows failure message", async ({ page }) => {
    await page.route("**/api/v1/analytics/dashboard", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_DASHBOARD_STATS),
      })
    );
    await page.route("**/api/v1/analytics/deliverability", (route) =>
      route.fulfill({ status: 500, body: "Error" })
    );

    await page.goto("/");

    await page.waitForSelector("text=Failed to load deliverability", {
      timeout: 10_000,
    });
    await expect(
      page.getByText("Failed to load deliverability data.")
    ).toBeVisible();
  });

  test("shows Recent Activity section with entries", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=Recent Activity", { timeout: 10_000 });
    await expect(page.getByText("Recent Activity")).toBeVisible();

    // The hardcoded recent activity list should be visible
    await expect(
      page.getByText("New lead imported: jane@acme.com")
    ).toBeVisible();
  });

  test("Quick Actions section contains Import Leads button", async ({
    page,
  }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=Quick Actions", { timeout: 10_000 });
    await expect(page.getByText("Quick Actions")).toBeVisible();
    await expect(page.getByRole("link", { name: /Import Leads/i })).toBeVisible();
  });

  test("Import Leads quick action navigates to import page", async ({
    page,
  }) => {
    await mockDashboardAPIs(page);
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      })
    );

    await page.goto("/");
    await page.waitForSelector("text=Quick Actions", { timeout: 10_000 });

    const importLink = page.getByRole("link", { name: /Import Leads/i });
    await expect(importLink).toHaveAttribute("href", "/leads/import");
  });

  test("Create Sequence quick action navigates to sequences page", async ({
    page,
  }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=Quick Actions", { timeout: 10_000 });

    const seqLink = page.getByRole("link", { name: /Create Sequence/i });
    await expect(seqLink).toHaveAttribute("href", "/sequences");
  });

  test("Compliance Check quick action navigates to compliance page", async ({
    page,
  }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=Quick Actions", { timeout: 10_000 });

    const complianceLink = page.getByRole("link", { name: /Compliance Check/i });
    await expect(complianceLink).toHaveAttribute("href", "/compliance");
  });

  test("sidebar navigation is visible on desktop", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");

    // Sidebar should be rendered
    const sidebar = page.locator("aside, nav").first();
    await expect(sidebar).toBeVisible();
  });

  test("navigation links exist in sidebar", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");

    // Sidebar should contain key navigation links
    await expect(page.getByRole("link", { name: /Sequences/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Leads/i }).first()).toBeVisible();
  });

  test("FortressFlow brand name is visible in the header", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await expect(page.getByText(/FortressFlow/i).first()).toBeVisible();
  });

  test("warmup badge shows active and completed counts", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.goto("/");

    await page.waitForSelector("text=warming up", { timeout: 10_000 });

    // warmup_active = 3
    await expect(page.getByText("3 warming up")).toBeVisible();
    // warmup_completed = 7
    await expect(page.getByText("7 completed")).toBeVisible();
  });

  test("page renders correctly at tablet viewport", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/");

    await page.waitForSelector("text=Total Leads", { timeout: 10_000 });
    await expect(page.getByText("Total Leads")).toBeVisible();
  });

  test("page renders correctly at mobile viewport", async ({ page }) => {
    await mockDashboardAPIs(page);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");

    // Content should be present even on mobile
    await expect(page).toHaveTitle(/FortressFlow/i);
  });
});
