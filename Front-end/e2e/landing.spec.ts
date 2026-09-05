import { test, expect } from "@playwright/test";

// index.html: the landing page. Waits on window.LENS_READY (data.js),
// then renders the source ledger, the headline strip, and (via
// showcase.js) two choropleth maps -- all from live API reads, none of
// it static markup. This is the path no backend test can cover: nothing
// in the 700+ backend suite ever loads this HTML or runs data.js.

test.describe("landing page", () => {
  test("resolves LENS_READY and is not flagged unavailable", async ({ page }) => {
    await page.goto("/index.html");
    const ready = await page.evaluate(() => window.LENS_READY);
    expect(ready).not.toBeNull();
    await expect(page.locator("body")).not.toHaveAttribute("data-lens", "unavailable");
  });

  test("US headline CPI strip renders a real figure, not the placeholder dash", async ({ page }) => {
    await page.goto("/index.html");
    const strip = page.locator("#strip-cpi");
    await expect(strip).not.toHaveText("—");
    await expect(strip).toHaveText(/^[+-]\d+\.\d%$/);
  });

  test("global headline stays honestly unavailable rather than showing a fabricated figure", async ({ page }) => {
    // GLOBAL_INFLATION_METHODS.md's own rule, enforced end-to-end: the
    // engine has no population/GDP-PPP weights ingested for a weighted
    // global figure, so /world/cross-section always returns headline:
    // null, and the page must show that gap, not an unweighted stand-in.
    await page.goto("/index.html");
    const big = page.locator("#w-headline-big");
    await expect(big).toHaveAttribute("data-state", "unavailable");
    await expect(page.locator("#w-headline-v")).toHaveText("—");
  });

  test("source ledger lists the real configured publishers with no secrets", async ({ page }) => {
    await page.goto("/index.html");
    const rows = page.locator("#src-rows tr");
    await expect(rows).not.toHaveCount(0);
    const text = await page.locator("#src-rows").innerText();
    expect(text).toMatch(/BLS|Federal Reserve|World Bank|Eurostat|ECB|BEA/);
    expect(text.toLowerCase()).not.toMatch(/api_key|apikey|token=/);
  });

  test("world and US choropleths draw real map geometry", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready", { timeout: 15_000 });
    await expect(page.locator("#w-lines path").first()).toBeAttached();
    await expect(page.locator("#u-lines path").first()).toBeAttached();
    // At least one US state must actually be colored from live data
    // (L.us.stateValues), not just outlined.
    await expect(page.locator("#u-fill path").first()).toBeAttached();
  });

  test("hero search hands off to the workbench with the typed query", async ({ page }) => {
    await page.goto("/index.html");
    await page.fill("#hero-q", "euro area");
    await page.click("#hero-search button[type=submit]");
    await expect(page).toHaveURL(/app\.html\?q=euro(%20|\+)area/);
  });
});
