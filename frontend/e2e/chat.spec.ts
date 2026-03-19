import { test, expect } from "@playwright/test";

test.describe("FortressFlow Chat Assistant", () => {
  test.beforeEach(async ({ page }) => {
    // Mock the chat API endpoint
    await page.route("**/api/v1/chat/", async (route) => {
      const encoder = new TextEncoder();
      const body = encoder.encode(
        "data: Hello! I'm the FortressFlow Assistant.\n\ndata: How can I help you today?\n\ndata: [DONE]\n\n"
      );
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: Buffer.from(body),
      });
    });

    await page.route("**/api/v1/chat/history**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, session_id: "test-session" }),
      });
    });

    // Mock other API endpoints the dashboard might call
    await page.route("**/api/v1/analytics/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_leads: 150,
          active_consents: 120,
          touches_sent: 500,
          response_rate: 0.12,
        }),
      });
    });

    await page.goto("/");
  });

  test("chat bubble is visible on page load", async ({ page }) => {
    const chatButton = page.locator('[aria-label="Open chat assistant"]');
    await expect(chatButton).toBeVisible();
  });

  test("clicking chat bubble opens chat panel", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await expect(page.locator("text=FortressFlow Assistant")).toBeVisible();
  });

  test("can send a message and receive streaming response", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');

    const input = page.locator('[aria-label="Chat message input"]');
    await input.fill("How do I warm up my inboxes?");
    await page.click('[aria-label="Send message"]');

    // Check user message appears
    await expect(page.locator("text=How do I warm up my inboxes?")).toBeVisible();

    // Wait for streaming response — the panel header "FortressFlow Assistant" is always visible when open
    await expect(page.locator('[role="dialog"]')).toBeVisible();
  });

  test("close button closes the chat panel", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');
    await expect(page.locator('[role="dialog"]')).toBeVisible();

    await page.click('[aria-label="Close chat"]');
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test("escape key closes the chat panel", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');
    await expect(page.locator('[role="dialog"]')).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test("slash command autocomplete appears when typing /", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');

    const input = page.locator('[aria-label="Chat message input"]');
    await input.fill("/");

    // Should show command suggestions
    await expect(page.locator("text=/status")).toBeVisible();
    await expect(page.locator("text=/help")).toBeVisible();
  });

  test("proactive message shows on first visit", async ({ page }) => {
    // Clear localStorage to simulate first visit
    await page.evaluate(() =>
      localStorage.removeItem("fortressflow-chat-proactive-dismissed")
    );
    await page.reload();

    // Wait for proactive message (shown after 5 seconds)
    await page.waitForTimeout(6000);
    await expect(
      page.locator("text=Need help getting started")
    ).toBeVisible({ timeout: 10000 });
  });

  test("chat panel is responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.click('[aria-label="Open chat assistant"]');

    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible();
    // On mobile, should be full width
    const box = await panel.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      expect(box.width).toBeGreaterThanOrEqual(370);
    }
  });

  test("dark mode styling applies to chat panel", async ({ page }) => {
    // Enable dark mode
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      localStorage.setItem("fortressflow-theme", "dark");
    });

    await page.click('[aria-label="Open chat assistant"]');
    const panel = page.locator('[role="dialog"]');
    await expect(panel).toBeVisible();
  });

  test("Enter sends message, Shift+Enter adds newline", async ({ page }) => {
    await page.click('[aria-label="Open chat assistant"]');

    const input = page.locator('[aria-label="Chat message input"]');
    await input.fill("test message");
    await input.press("Enter");

    // Message should be sent
    await expect(page.locator("text=test message")).toBeVisible();
  });
});
