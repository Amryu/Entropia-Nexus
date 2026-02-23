import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E testing.
 * Uses .env.test to connect to test databases (nexus-test, nexus-users-test)
 * to avoid affecting development data.
 *
 * Test ports (offset +100 from dev):
 * - API: 3100 (dev: 3000)
 * - Frontend: 3101 (dev: 3001)
 *
 * Uses dev.entropianexus.com (mapped to localhost in hosts file) to avoid cookie issues.
 *
 * To skip database recreation when test servers are already running:
 *   SKIP_GLOBAL_SETUP=1 npx playwright test
 */
export default defineConfig({
  testDir: './tests',

  /* Global setup - clones database schema and creates test data (skip with SKIP_GLOBAL_SETUP=1) */
  globalSetup: process.env.SKIP_GLOBAL_SETUP ? undefined : './tests/global-setup.ts',

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : 4,

  /* Reporter to use */
  reporter: 'html',

  /* Shared settings for all the projects below */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: 'http://dev.entropianexus.com:3101',

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',

    /* Take screenshot on failure */
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'setup',
      testMatch: /cache-warmup\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
    // Uncomment to add more browsers:
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  /* Run local dev servers before starting the tests */
  webServer: [
    {
      // API server on port 3100 using test databases (offset +100 from dev port 3000)
      command: 'cd ../api && npx dotenv-cli -e .env.test -- node app.js',
      url: 'http://dev.entropianexus.com:3100/weapons', // Check a valid endpoint that returns data
      reuseExistingServer: true, // Always start fresh to avoid stale server issues
      timeout: 60 * 1000, // 1 minute to start
    },
    {
      // Frontend dev server on port 3101 (offset +100 from dev port 3001)
      command: 'npx cross-env NODE_ENV=test npx dotenv-cli -e .env.test -- vite dev --host 0.0.0.0 --port 3101',
      url: 'http://dev.entropianexus.com:3101',
      reuseExistingServer: true, // Always start fresh to avoid stale server issues
      timeout: 120 * 1000, // 2 minutes to start
    },
  ],
});
