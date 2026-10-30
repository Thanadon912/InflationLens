import { test, expect } from "@playwright/test";
import * as path from "path";

const ARTIFACT_DIR = "/home/thanadon/.gemini/antigravity-cli/brain/c0572d7f-e7e1-4c35-a17e-ebedec0e83d9";

test.describe("visual audit - capabilities studio showcase", () => {
  test("page preloader animation renders on initial load and dismisses cleanly", async ({ page }) => {
    let resume: () => void = () => {};
    const wait = new Promise<void>((r) => { resume = r; });
    await page.route("**/api/v1/measures/USA*", async (route) => {
      await wait;
      await route.continue();
    });

    const nav = page.goto("/index.html", { waitUntil: "domcontentloaded" });
    const loader = page.locator("#page-loader");
    await expect(loader).toBeVisible();

    // Capture screenshot of the preloader animation
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "preloader_animation.png"),
      fullPage: false,
    });

    // Release the API response
    resume();
    await nav;

    // Once data arrives and React renders, loader fades out and is removed from DOM
    await expect(loader).toHaveCount(0, { timeout: 10_000 });
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready");
  });

  test("inspect desktop showcase across all capability tabs at 1920x963", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 963 });
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready", { timeout: 15_000 });

    const showcase = page.locator("#showcase");
    await showcase.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    // Tab 1: Measure Spread
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "showcase_tab_spread.png"),
      fullPage: false,
    });

    const mRows = page.locator("#m-rows .m-row");
    await expect(mRows).toHaveCount(7);

    // Tab 2: Category Drivers
    await page.click("#tab-categories");
    await page.waitForTimeout(250);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "showcase_tab_categories.png"),
      fullPage: false,
    });
    const catCards = page.locator("#cat-bars .cat-card");
    await expect(catCards).toHaveCount(6);

    // Tab 3: Sub-National Reality
    await page.click("#tab-regions");
    await page.waitForTimeout(250);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "showcase_tab_regions.png"),
      fullPage: false,
    });
    const regionCards = page.locator(".region-card");
    await expect(regionCards).toHaveCount(4);

    // Tab 4: Personal Basket Simulator
    await page.click("#tab-simulator");
    await page.waitForTimeout(250);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "showcase_tab_simulator.png"),
      fullPage: false,
    });

    // Test slider interaction on Personal Basket
    const initialRateText = await page.locator(".gauge-val").innerText();
    // Click 'Suburban Commuter' preset
    await page.click("button.preset-btn:has-text('Suburban Commuter')");
    await page.waitForTimeout(200);
    const updatedRateText = await page.locator(".gauge-val").innerText();
    console.log("Simulator Rate changed from", initialRateText, "to", updatedRateText);
    expect(updatedRateText).not.toEqual("");

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "showcase_tab_simulator_commuter.png"),
      fullPage: false,
    });
  });

  test("inspect mobile viewports at 390x844", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready", { timeout: 15_000 });

    // Check horizontal scroll / overflow
    const overflow = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth;
      const viewW = window.innerWidth;
      return {
        docW,
        viewW,
        hasHorizontalScroll: docW > viewW,
      };
    });
    console.log("Mobile horizontal overflow:", overflow);
    expect(overflow.hasHorizontalScroll).toBe(false);

    // Scroll down to showcase
    await page.locator("#showcase").scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_showcase.png"),
      fullPage: false,
    });

    // Scroll to console content on tab-spread
    await page.locator(".hub-console").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_showcase_console.png"),
      fullPage: false,
    });

    // Check Simulator on mobile
    await page.click("#tab-simulator");
    await page.waitForTimeout(300);
    await page.locator(".hub-console").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_simulator.png"),
      fullPage: false,
    });

    const mobileOverflowSimulator = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(mobileOverflowSimulator).toBe(false);

    // Check workbench on mobile
    await page.goto("/app.html");
    await page.waitForSelector(".head");
    const wbOverflow = await page.evaluate(() => {
      return {
        docW: document.documentElement.scrollWidth,
        viewW: window.innerWidth,
        hasHorizontalScroll: document.documentElement.scrollWidth > window.innerWidth,
      };
    });
    console.log("Mobile workbench horizontal overflow:", wbOverflow);
    expect(wbOverflow.hasHorizontalScroll).toBe(false);
  });
});
