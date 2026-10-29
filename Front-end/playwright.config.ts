import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the React + TypeScript Inflation Lens frontend against the
 * real Flask API (Back-end/).
 *
 * Two webServers:
 *  - the Flask API on :5000 (lensClient.ts's default LENS_API_BASE), started
 *    against a small deterministic seeded SQLite DB (see
 *    ../Back-end/scripts/seed_e2e_db.py) rather than a live `data sync` --
 *    E2E must not depend on live provider network calls or API keys.
 *  - the Vite dev server on :3000 for index.html / app.html. Port 3000 is in
 *    Flask's default CORS_ALLOWED_ORIGINS (app/factory.py).
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
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.CI ? undefined : "chrome",
      },
    },
  ],
  webServer: [
    {
      command:
        ".venv/bin/python scripts/seed_e2e_db.py instance/e2e-seed.sqlite3 && " +
        "INFLATION_DB_PATH=instance/e2e-seed.sqlite3 .venv/bin/python -m flask --app app run --port 5000",
      cwd: "../Back-end",
      url: "http://localhost:5000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run preview",
      cwd: ".",
      url: "http://localhost:3000/index.html",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
