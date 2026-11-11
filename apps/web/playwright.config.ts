// End-to-end tests in web mode (plan: "Playwright, web modunda E2E"): a real backend on a
// fresh temporary library, and the web app served by Vite. `pnpm e2e` runs them.
import { defineConfig, devices } from "@playwright/test";

export const WEB_PORT = 1431;

export default defineConfig({
  testDir: "e2e",
  // One backend and one library for the run: tests that share it go one at a time.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://localhost:${String(WEB_PORT)}`,
    locale: "en-US",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `pnpm exec vite --port ${String(WEB_PORT)} --strictPort`,
    url: `http://localhost:${String(WEB_PORT)}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
