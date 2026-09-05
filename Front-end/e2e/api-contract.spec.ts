import { test, expect } from "@playwright/test";

// The gap that matters most: nothing in the backend's own 700+ test
// suite knows data.js exists, and nothing in data.js is typechecked
// against the backend. A field rename in Back-end/app/api/data.py
// currently breaks the UI with a fully green backend suite -- this file
// pins every key data.js actually destructures (see its assembleUs,
// assembleWorld, assembleSources, and load()) directly against the real
// running API, independent of whether the frontend happens to render a
// dash for a missing field instead of throwing.

const API = "http://localhost:5000/api/v1";

test.describe("frontend/backend response contract", () => {
  test("GET /measures/USA carries every field assembleUs() reads", async ({ request }) => {
    const res = await request.get(`${API}/measures/USA`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();

    expect(Array.isArray(body.measures)).toBe(true);
    expect(body.measures.length).toBeGreaterThan(0);
    for (const m of body.measures) {
      for (const key of [
        "id", "code", "name", "yoy", "mom", "period", "src",
        "coverage", "confidence", "is_estimated", "seasonally_adjusted",
      ]) {
        expect(m).toHaveProperty(key);
      }
    }
    expect(Array.isArray(body.context)).toBe(true);
    for (const c of body.context) {
      expect(c).toHaveProperty("k");
      expect(c).toHaveProperty("v");
    }
    // data_snapshot is read (m.data_snapshot?.as_of) only on the first
    // available measure -- assert it's present on at least the CPI card,
    // which the seeded fixture always makes available.
    const cpi = body.measures.find((m: { id: string }) => m.id === "cpi");
    expect(cpi.data_snapshot).toHaveProperty("as_of");
  });

  test("GET /categories/USA carries every field assembleUs() reads", async ({ request }) => {
    const res = await request.get(`${API}/categories/USA`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.categories)).toBe(true);
    expect(body.categories.length).toBeGreaterThan(0);
    for (const c of body.categories) {
      expect(c).toHaveProperty("name");
      expect(c).toHaveProperty("v");
    }
  });

  test("GET /regions/us carries every field assembleUs() reads", async ({ request }) => {
    const res = await request.get(`${API}/regions/us`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const key of ["regions", "stateRegion", "stateValues", "stateNames", "regionTails"]) {
      expect(body).toHaveProperty(key);
    }
  });

  test("GET /world/cross-section carries every field assembleWorld() reads", async ({ request }) => {
    const res = await request.get(`${API}/world/cross-section`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const key of ["headline", "median", "g20", "economies", "tails", "byIso"]) {
      expect(body).toHaveProperty(key);
    }
    expect(Array.isArray(body.tails)).toBe(true);
    for (const t of body.tails) {
      expect(t).toHaveProperty("name");
      expect(t).toHaveProperty("v");
    }
  });

  test("GET /meta/data-sources carries every field assembleSources() reads", async ({ request }) => {
    const res = await request.get(`${API}/meta/data-sources`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.publishers)).toBe(true);
    expect(body.publishers.length).toBeGreaterThan(0);
    for (const p of body.publishers) {
      for (const key of ["org", "full", "url", "series", "cov", "latest", "next"]) {
        expect(p).toHaveProperty(key);
      }
    }
  });

  test("GET /resolve returns the `matches` array data.js.resolve() reads", async ({ request }) => {
    const res = await request.get(`${API}/resolve?q=usa`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.matches)).toBe(true);
    expect(body.matches[0]).toHaveProperty("id");
    expect(body.matches[0]).toHaveProperty("kind");
    expect(body.matches[0]).toHaveProperty("label");
  });
});
