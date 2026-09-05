import { test, expect } from "@playwright/test";

// app.html: the workbench. Geography/Window/Adjustment are query
// parameters that trigger a real refetch (app.html's own comment calls
// this out as "not a cosmetic toggle") -- this is exactly the behavior
// the backend's query-param validation regression tests (Package A) exist
// to protect, verified here from the browser's actual fetch calls rather
// than a direct API request.

test.describe("workbench", () => {
  test("measure grid renders real figures for the default 12-month window", async ({ page }) => {
    await page.goto("/app.html");
    const cards = page.locator("#mgrid .mcard");
    await expect(cards).not.toHaveCount(0);
    // Exact match: "C-CPI-U" (Chained CPI) contains "CPI-U" as a
    // substring, so a plain hasText would match both cards.
    const cpiCard = cards.filter({ has: page.locator(".c", { hasText: /^CPI-U$/ }) });
    await expect(cpiCard.locator(".v")).not.toHaveText("—");
    await expect(cpiCard.locator(".v")).toHaveText(/^[+-]\d+\.\d%$/);
  });

  test("switching Window re-fetches and changes the rendered headline value", async ({ page }) => {
    await page.goto("/app.html");
    const cpiValue = () => page.locator("#mgrid .mcard").first().locator(".v");
    const twelveMonth = await cpiValue().innerText();

    await page.click('#window-rail button[data-window="6m"]');
    await expect(page.locator('#window-rail button[data-window="6m"]')).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => cpiValue().innerText()).not.toBe(twelveMonth);
  });

  test("switching Adjustment re-fetches and narrows the measure set", async ({ page }) => {
    await page.goto("/app.html");
    const initialCount = await page.locator("#mgrid .mcard").count();

    await page.click('#adjustment-rail button[data-adjustment="sa"]');
    await expect(page.locator('#adjustment-rail button[data-adjustment="sa"]')).toHaveAttribute("aria-pressed", "true");
    // Only PCE-family measures are seasonally adjusted in this dataset --
    // switching to "sa" must narrow the grid, not just relabel it.
    await expect.poll(() => page.locator("#mgrid .mcard").count()).toBeLessThan(initialCount);
  });

  test("switching Geography re-fetches for the new country", async ({ page }) => {
    await page.goto("/app.html");
    await expect(page.locator("#head-name")).toHaveText("United States");

    await page.click('#geo-rail button[data-geo="EA"]');
    await expect(page.locator('#geo-rail button[data-geo="EA"]')).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#head-name")).toHaveText("Euro area");
    await expect(page.locator("#who")).toHaveText("Euro area");
  });

  test("category ladder and region table populate for the US", async ({ page }) => {
    await page.goto("/app.html");
    await expect(page.locator("#cats tr")).not.toHaveCount(0);
    await expect(page.locator("#states tr")).not.toHaveCount(0);
    // Every region row discloses it's modelled (BLS publishes no
    // state-level CPI) -- not a silently invented per-state number.
    await expect(page.locator("#states tr").first().locator(".est")).toHaveText("modelled");
  });

  test("search resolves a typed geography and switches the workbench", async ({ page }) => {
    await page.goto("/app.html");
    await page.fill("#q", "euro area");
    await expect(page.locator("#head-name")).toHaveText("Euro area", { timeout: 10_000 });
    await expect(page.locator('#geo-rail button[data-geo="EA"]')).toHaveAttribute("aria-pressed", "true");
  });

  test("?q= from the landing page's hero search pre-resolves the geography", async ({ page }) => {
    await page.goto("/app.html?q=euro%20area");
    await expect(page.locator("#head-name")).toHaveText("Euro area", { timeout: 10_000 });
  });

  test("your-basket estimate recomputes from the live category rates", async ({ page }) => {
    await page.goto("/app.html");
    await expect(page.locator("#ownIdx")).not.toHaveText("—");
    const before = await page.locator("#ownIdx").innerText();

    // Energy's seeded rate (14.7%) is a large outlier against the other
    // categories, so pushing its weight to the slider max produces an
    // unambiguous change in the rendered (rounded to one decimal) figure.
    await page.fill("#w3", "30");
    await page.dispatchEvent("#w3", "input");
    await expect.poll(() => page.locator("#ownIdx").innerText()).not.toBe(before);
  });
});
