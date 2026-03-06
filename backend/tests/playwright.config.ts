/**
 * Playwright Configuration for Payload Library API Tests
 */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:8000",
    trace: "on-first-retry",
    timeout: 30000,
  },

  projects: [
    {
      name: "api-tests",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
    url: "http://localhost:8000",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
