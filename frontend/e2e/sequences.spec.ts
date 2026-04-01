import { test, expect, Page } from "@playwright/test";

/**
 * Sequences Page E2E Tests — FortressFlow Phase 6
 *
 * Tests the /sequences route: list rendering, status display,
 * create dialog, pagination, empty state, and error state.
 */

// ── Mock Data ─────────────────────────────────────────────────────────────

const MOCK_SEQUENCES_PAGE_1 = {
  items: [
    {
      id: "seq-001",
      name: "Q4 Enterprise Outreach",
      description: "Automated follow-up for enterprise prospects",
      status: "active",
      steps: [{ id: "s1" }, { id: "s2" }, { id: "s3" }],
      enrolled_count: 87,
      ai_generated: false,
      created_at: "2026-01-15T10:00:00Z",
      updated_at: "2026-03-01T08:00:00Z",
    },
    {
      id: "seq-002",
      name: "SMB Cold Outreach",
      description: "Targeting small and medium businesses",
      status: "draft",
      steps: [{ id: "s4" }, { id: "s5" }],
      enrolled_count: 0,
      ai_generated: true,
      created_at: "2026-02-10T14:00:00Z",
      updated_at: "2026-02-10T14:00:00Z",
    },
    {
      id: "seq-003",
      name: "Re-Engagement Flow",
      description: null,
      status: "paused",
      steps: [],
      enrolled_count: 23,
      ai_generated: false,
      created_at: "2026-01-20T09:00:00Z",
      updated_at: "2026-03-10T12:00:00Z",
    },
    {
      id: "seq-004",
      name: "Dental Practice Outreach",
      description: "Targeting dental practices in the southeast",
      status: "archived",
      steps: [{ id: "s6" }],
      enrolled_count: 150,
      ai_generated: false,
      created_at: "2025-10-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ],
  total: 4,
  page: 1,
  page_size: 12,
};

const MOCK_SEQUENCES_MULTI_PAGE = {
  items: Array.from({ length: 12 }, (_, i) => ({
    id: `seq-p1-${i}`,
    name: `Sequence ${i + 1}`,
    description: `Description for sequence ${i + 1}`,
    status: "active",
    steps: [],
    enrolled_count: i * 10,
    ai_generated: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  })),
  total: 25,
  page: 1,
  page_size: 12,
};

const MOCK_SEQUENCES_EMPTY = {
  items: [],
  total: 0,
  page: 1,
  page_size: 12,
};

// ── Helpers ───────────────────────────────────────────────────────────────

async function mockSequencesAPI(page: Page, payload = MOCK_SEQUENCES_PAGE_1) {
  await page.route("**/api/v1/sequences**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    })
  );
}

async function mockSequencesAPIError(page: Page) {
  await page.route("**/api/v1/sequences**", (route) =>
    route.fulfill({ status: 500, body: "Internal Server Error" })
  );
}

async function mockSequenceCreate(page: Page) {
  await page.route("**/api/v1/sequences", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "seq-new-001",
          name: "My New Sequence",
          description: "",
          status: "draft",
          steps: [],
          enrolled_count: 0,
          ai_generated: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_SEQUENCES_PAGE_1),
    });
  });
}

// ── Test Suite ────────────────────────────────────────────────────────────

test.describe("Sequences Page", () => {
  test("loads sequences list with correct heading", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Sequences", { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "Sequences" })).toBeVisible();
  });

  test("shows New Sequence button", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await expect(
      page.getByRole("button", { name: /New Sequence/i })
    ).toBeVisible();
  });

  test("displays sequence cards after data loads", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Q4 Enterprise Outreach", { timeout: 10_000 });

    await expect(page.getByText("Q4 Enterprise Outreach")).toBeVisible();
    await expect(page.getByText("SMB Cold Outreach")).toBeVisible();
    await expect(page.getByText("Re-Engagement Flow")).toBeVisible();
    await expect(page.getByText("Dental Practice Outreach")).toBeVisible();
  });

  test("sequence cards show status badges", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=active", { timeout: 10_000 });

    await expect(page.getByText("active").first()).toBeVisible();
    await expect(page.getByText("draft")).toBeVisible();
    await expect(page.getByText("paused")).toBeVisible();
    await expect(page.getByText("archived")).toBeVisible();
  });

  test("sequence cards show enrolled count", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=87 enrolled", { timeout: 10_000 });
    await expect(page.getByText("87 enrolled")).toBeVisible();
  });

  test("sequence cards show step count", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=3 steps", { timeout: 10_000 });
    await expect(page.getByText("3 steps")).toBeVisible();
  });

  test("AI-generated sequences show AI badge", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=AI", { timeout: 10_000 });
    await expect(page.getByText("AI", { exact: true })).toBeVisible();
  });

  test("Builder button appears on each sequence card", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Builder", { timeout: 10_000 });
    const builderButtons = page.getByRole("button", { name: /Builder/i });
    await expect(builderButtons.first()).toBeVisible();
  });

  test("shows loading skeletons while sequences are fetching", async ({
    page,
  }) => {
    await page.route("**/api/v1/sequences**", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SEQUENCES_PAGE_1),
      });
    });

    await page.goto("/sequences");

    // Skeleton animation should appear immediately
    const skeleton = page.locator(".animate-pulse").first();
    await expect(skeleton).toBeVisible();
  });

  test("shows error state when API fails", async ({ page }) => {
    await mockSequencesAPIError(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Failed to load sequences", {
      timeout: 10_000,
    });
    await expect(
      page.getByText("Failed to load sequences. Please try again.")
    ).toBeVisible();
  });

  test("shows empty state when no sequences exist", async ({ page }) => {
    await mockSequencesAPI(page, MOCK_SEQUENCES_EMPTY);
    await page.goto("/sequences");

    await page.waitForSelector("text=No sequences yet", { timeout: 10_000 });
    await expect(page.getByText("No sequences yet")).toBeVisible();
    await expect(
      page.getByText("Create your first outreach sequence to get started.")
    ).toBeVisible();
  });

  test("create dialog opens when New Sequence is clicked", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Create Sequence")).toBeVisible();
  });

  test("create dialog shows Name and Description fields", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    await expect(page.getByLabel("Name")).toBeVisible();
    await expect(page.getByLabel("Description (optional)")).toBeVisible();
  });

  test("Create button is disabled when name is empty", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    // Create button should be disabled when no name
    const createBtn = page.getByRole("button", { name: /^Create$/ });
    await expect(createBtn).toBeDisabled();
  });

  test("Create button enables when name is filled in", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    await page.getByLabel("Name").fill("My New Sequence");

    const createBtn = page.getByRole("button", { name: /^Create$/ });
    await expect(createBtn).not.toBeDisabled();
  });

  test("cancel button closes the create dialog", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: /Cancel/i }).click();

    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("sequence can be created via dialog", async ({ page }) => {
    await mockSequenceCreate(page);
    await mockSequencesAPI(page);

    await page.goto("/sequences");
    await page.waitForSelector("text=New Sequence", { timeout: 10_000 });
    await page.getByRole("button", { name: /New Sequence/i }).click();

    await page.getByLabel("Name").fill("My New Sequence");
    await page.getByLabel("Description (optional)").fill("A test sequence");

    // Mock the POST
    await page.route("**/api/v1/sequences", (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "seq-created",
            name: "My New Sequence",
            description: "A test sequence",
            status: "draft",
            steps: [],
            enrolled_count: 0,
            ai_generated: false,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
        });
      }
      return route.continue();
    });

    const createBtn = page.getByRole("button", { name: /^Create$/ });
    await createBtn.click();

    // Dialog should close
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
  });

  test("pagination controls appear when there are multiple pages", async ({
    page,
  }) => {
    await mockSequencesAPI(page, MOCK_SEQUENCES_MULTI_PAGE);
    await page.goto("/sequences");

    // 25 total, 12 per page → 3 pages → pagination should appear
    await page.waitForSelector("text=Page 1 of", { timeout: 10_000 });
    await expect(page.getByText(/Page 1 of/i)).toBeVisible();
  });

  test("pagination next button is enabled on first page", async ({ page }) => {
    await mockSequencesAPI(page, MOCK_SEQUENCES_MULTI_PAGE);
    await page.goto("/sequences");

    await page.waitForSelector("text=Page 1 of", { timeout: 10_000 });

    // Previous should be disabled, Next should be enabled
    const prevBtn = page.getByRole("button", { name: "Previous page" });
    await expect(prevBtn).toBeDisabled();
    await expect(page.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  test("pagination not shown for single page of results", async ({ page }) => {
    await mockSequencesAPI(page, MOCK_SEQUENCES_PAGE_1); // 4 items < 12 per page
    await page.goto("/sequences");

    await page.waitForSelector("text=Q4 Enterprise Outreach", { timeout: 10_000 });

    // Should not show pagination
    const paginationText = page.getByText(/Page 1 of 1/i);
    await expect(paginationText).not.toBeVisible();
  });

  test("sequence card links to detail page", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Q4 Enterprise Outreach", { timeout: 10_000 });

    const seqLink = page.getByRole("link", { name: /Q4 Enterprise Outreach/i });
    await expect(seqLink).toHaveAttribute("href", "/sequences/seq-001");
  });

  test("builder link directs to sequence builder page", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Builder", { timeout: 10_000 });

    const sequenceCard = page.getByRole("article", {
      name: "Sequence Q4 Enterprise Outreach",
    });
    const builderLink = sequenceCard.getByRole("link", { name: /Builder/i });
    await expect(builderLink).toHaveAttribute(
      "href",
      "/sequences/builder/seq-001"
    );
  });

  test("sequence description is shown when provided", async ({ page }) => {
    await mockSequencesAPI(page);
    await page.goto("/sequences");

    await page.waitForSelector("text=Automated follow-up for enterprise prospects", {
      timeout: 10_000,
    });

    await expect(
      page.getByText("Automated follow-up for enterprise prospects")
    ).toBeVisible();
  });
});
