import { test, expect } from "@playwright/test";
import * as path from "path";

const ARTIFACT_DIR = "/home/thanadon/.gemini/antigravity-cli/brain/c0572d7f-e7e1-4c35-a17e-ebedec0e83d9";

test.describe("visual audit - desktop and mobile", () => {
  test("inspect desktop act2 at 1920x963", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 963 });
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready", { timeout: 15_000 });

    // Scroll to showcase act 2
    // Let's find track height and scroll to different positions
    const track = page.locator("#showcase");
    const trackBox = await track.boundingBox();
    console.log("Track bounding box:", trackBox);

    // Let's click on rail dot 02 or scroll into act2 view
    await page.evaluate(() => {
      const el = document.getElementById("showcase");
      if (el) {
        // Scroll so that p ~ 0.55 where Act 2 is fully displayed
        const run = el.offsetHeight - window.innerHeight;
        window.scrollTo({ top: el.offsetTop + run * 0.55, behavior: "instant" });
      }
    });

    await page.waitForTimeout(500);

    const act2Info = await page.evaluate(() => {
      const mRows = Array.from(document.querySelectorAll("#m-rows .m-row")).map((row, i) => {
        const text = (row as HTMLElement).innerText.replace(/\n/g, " ");
        const style = window.getComputedStyle(row);
        const rect = row.getBoundingClientRect();
        return {
          index: i,
          text,
          opacity: style.opacity,
          display: style.display,
          visibility: style.visibility,
          top: rect.top,
          bottom: rect.bottom,
          height: rect.height,
        };
      });

      const flag = document.querySelector(".flag");
      const flagRect = flag?.getBoundingClientRect();

      const cats = document.querySelector(".cats");
      const catsRect = cats?.getBoundingClientRect();

      const catBars = Array.from(document.querySelectorAll("#cat-bars .cat")).map((c) => ({
        text: (c as HTMLElement).innerText.replace(/\n/g, " "),
        rect: c.getBoundingClientRect(),
      }));

      const stageStyle = document.getElementById("stage")?.style;
      const rev = stageStyle?.getPropertyValue("--rev");
      const a2 = stageStyle?.getPropertyValue("--a2");

      return {
        rev,
        a2,
        mRows,
        flagRect: flagRect ? { top: flagRect.top, bottom: flagRect.bottom, height: flagRect.height } : null,
        catsRect: catsRect ? { top: catsRect.top, bottom: catsRect.bottom, height: catsRect.height } : null,
        catBarsCount: catBars.length,
        viewportHeight: window.innerHeight,
      };
    });

    console.log("ACT2 INFO AT p=0.55:", JSON.stringify(act2Info, null, 2));

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "desktop_act2_p55.png"),
      fullPage: false,
    });

    // Also test p=0.48 (just when act2 arrives)
    await page.evaluate(() => {
      const el = document.getElementById("showcase");
      if (el) {
        const run = el.offsetHeight - window.innerHeight;
        window.scrollTo({ top: el.offsetTop + run * 0.48, behavior: "instant" });
      }
    });
    await page.waitForTimeout(300);
    const act2Info48 = await page.evaluate(() => {
      return Array.from(document.querySelectorAll("#m-rows .m-row")).map((row, i) => ({
        index: i,
        text: (row as HTMLElement).innerText.replace(/\n/g, " "),
        opacity: window.getComputedStyle(row).opacity,
      }));
    });
    console.log("ACT2 INFO AT p=0.48:", JSON.stringify(act2Info48, null, 2));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "desktop_act2_p48.png"),
      fullPage: false,
    });

    // Also test p=0.70
    await page.evaluate(() => {
      const el = document.getElementById("showcase");
      if (el) {
        const run = el.offsetHeight - window.innerHeight;
        window.scrollTo({ top: el.offsetTop + run * 0.70, behavior: "instant" });
      }
    });
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "desktop_act2_p70.png"),
      fullPage: false,
    });
  });

  test("inspect mobile viewports at 390x844", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/index.html");
    await expect(page.locator("body")).toHaveAttribute("data-maps", "ready", { timeout: 15_000 });

    // Check body[data-flat]
    const isFlat = await page.evaluate(() => document.body.hasAttribute("data-flat"));
    console.log("Mobile isFlat:", isFlat);

    // Check horizontal scroll / overflow
    const overflow = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth;
      const viewW = window.innerWidth;
      return { docW, viewW, hasHorizontalScroll: docW > viewW };
    });
    console.log("Mobile horizontal overflow:", overflow);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_hero.png"),
      fullPage: false,
    });

    // Scroll down to showcase
    await page.locator("#showcase").scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_showcase.png"),
      fullPage: false,
    });

    // Scroll to act2 in mobile
    await page.locator("#act2").scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_act2.png"),
      fullPage: false,
    });

    // Full page mobile screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_landing_fullpage.png"),
      fullPage: true,
    });

    // Now inspect workbench on mobile
    await page.goto("/app.html");
    await page.waitForTimeout(500);

    const barMetrics = await page.evaluate(() => {
      const bar = document.querySelector(".top .bar");
      const brand = document.querySelector(".brand");
      const sbox = document.querySelector(".sbox");
      const who = document.querySelector(".who");
      const cs = (el: Element | null) => el ? {
        order: window.getComputedStyle(el).order,
        width: window.getComputedStyle(el).width,
        flex: window.getComputedStyle(el).flex,
        rect: el.getBoundingClientRect(),
      } : null;
      return {
        barWrap: bar ? window.getComputedStyle(bar).flexWrap : null,
        brand: cs(brand),
        sbox: cs(sbox),
        who: cs(who),
      };
    });
    console.log("BAR METRICS ON MOBILE:", JSON.stringify(barMetrics, null, 2));
    const workbenchOverflow = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth;
      const viewW = window.innerWidth;
      return { docW, viewW, hasHorizontalScroll: docW > viewW };
    });
    console.log("Mobile workbench horizontal overflow:", workbenchOverflow);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_workbench_top.png"),
      fullPage: false,
    });

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "mobile_workbench_fullpage.png"),
      fullPage: true,
    });
  });
});
