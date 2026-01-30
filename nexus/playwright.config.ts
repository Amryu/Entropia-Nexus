import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E testing.
 * Uses .env.test to connect to test databases (nexus-test, nexus-users-test)
 * to avoid affecting development data.
 */
export default defineConfig({
  testDir: './tests',

  /* Global setup - clones database schema from nexus-users and creates test users */
  globalSetup: './tests/global-setup.ts',

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter to use */
  reporter: 'html',

  /* Shared settings for all the projects below */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: 'http://localhost:3002',

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',

    /* Take screenshot on failure */
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
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
      // API server on port 3001 using test databases
      command: 'cd ../api && npx dotenv-cli -e .env.test -- node app.js',
      url: 'http://localhost:3001',
      reuseExistingServer: !process.env.CI,
      timeout: 60 * 1000, // 1 minute to start
    },
    {
      // Frontend dev server on port 3002
      command: 'npx cross-env NODE_ENV=test npx dotenv-cli -e .env.test -- vite dev --host 127.0.0.1 --port 3002',
      url: 'http://localhost:3002',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000, // 2 minutes to start
    },
  ],
});
