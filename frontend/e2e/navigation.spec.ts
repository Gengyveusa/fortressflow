import { test, expect } from "@playwright/test";

test.describe("FortressFlow Navigation", () => {
  test("should load the login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("text=FortressFlow")).toBeVisible();
    await expect(page.locator("text=Sign in to your account")).toBeVisible();
  });

  test("should show login form with email and password fields", async ({
    page,
  }) => {
    await page.goto("/login");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });
});
