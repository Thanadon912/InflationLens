import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the static Inflation Lens frontend against the real
 * Flask API (Back-end/) -- the layer no test in the backend's own 700+
 * test suite can exercise, since that suite never renders data.js or the
 * HTML that consumes it.
 *
 * Two webServers:
 *  - the Flask API on :5000 (data.js's default LENS_API_BASE), started
 *    against a small deterministic seeded SQLite DB (see
 *    ../Back-end/scripts/seed_e2e_db.py) rather than a live `data sync` --
 *    E2E must not depend on live provider network calls or API keys.
 *  - a plain static file server on :3000 for index.html/app.html. Port
 *    3000 is already in Flask's default CORS_ALLOWED_ORIGINS
 *    (app/factory.py), so no CORS override is needed.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command:
        ".venv/bin/python scripts/seed_e2e_db.py instance/e2e-seed.sqlite3 && " +
        "INFLATION_DB_PATH=instance/e2e-seed.sqlite3 .venv/bin/flask --app app run --port 5000",
      cwd: "../Back-end",
      url: "http://localhost:5000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "python3 -m http.server 3000",
      cwd: ".",
      url: "http://localhost:3000/index.html",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
