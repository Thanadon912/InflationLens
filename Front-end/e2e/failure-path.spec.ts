import { test, expect } from "@playwright/test";

// The one path the backend's own 700+ test suite structurally cannot
// cover: what the browser actually does when the API is unreachable.
// data.js's own design intent (see its module docstring) is that a
// missing engine stays visibly missing -- never a blank page, never a
// stale number presented as current. Verified here by intercepting every
// /api/v1/* request and aborting it, rather than stopping the real
// Flask webServer (which every other spec file in this project shares).

test.describe("API unreachable", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/**", (route) => route.abort("connectionrefused"));
  });

  test("landing page flags data-lens=unavailable and surfaces an accessible alert", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-lens", "unavailable");
    const alert = page.locator("#lens-alert");
    await expect(alert).toBeVisible();
    await expect(alert).toHaveAttribute("role", "alert");
    await expect(alert).not.toHaveText("");
  });

  test("workbench flags unavailable, alerts accessibly, and hides the basket estimate rather than showing a stale number", async ({ page }) => {
    await page.goto("/app.html");
    await expect(page.locator("body")).toHaveAttribute("data-lens", "unavailable");

    const alert = page.locator("#lens-alert");
    await expect(alert).toBeVisible();
    await expect(alert).toHaveAttribute("role", "alert");

    // "Your basket" lives outside #results, so the dimmed-results
    // treatment doesn't reach it -- it must be hidden outright rather
    // than keep showing a number computed from data this fetch never
    // confirmed is still current.
    await expect(page.locator("#ownIdxRow")).toBeHidden();
    await expect(page.locator("#stale-tag")).toBeVisible();
    await expect(page.locator("#results")).toHaveAttribute("data-stale", "true");
  });
});

test("a working load followed by an API outage keeps the last-resolved figures on screen, marked stale", async ({ page }) => {
  // Deliberately outside the describe block above (whose beforeEach
  // aborts every /api/v1/* request from the start) -- this test needs
  // its first load to succeed, and only breaks the API afterward.
  await page.goto("/app.html");
  await expect(page.locator("#head-name")).toHaveText("United States");
  const beforeValue = await page.locator("#mgrid .mcard").first().locator(".v").innerText();

  await page.route("**/api/v1/**", (route) => route.abort("connectionrefused"));
  await page.click('#window-rail button[data-window="6m"]');

  await expect(page.locator("body")).toHaveAttribute("data-lens", "unavailable");
  // The figure from the last successful render is retained, not blanked.
  await expect(page.locator("#mgrid .mcard").first().locator(".v")).toHaveText(beforeValue);
  await expect(page.locator("#stale-tag")).toBeVisible();
});
