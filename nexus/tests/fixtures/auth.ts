import { test as base, Page } from '@playwright/test';

// Test user IDs - must match the migration file
export const TEST_USERS = {
  verified1: 'verified1',
  verified2: 'verified2',
  verified3: 'verified3',
  unverified1: 'unverified1',
  unverified2: 'unverified2',
  unverified3: 'unverified3',
  admin: 'admin'
} as const;

export type TestUser = keyof typeof TEST_USERS;

export interface AuthFixtures {
  loginAs: (user: TestUser) => Promise<void>;
  logout: () => Promise<void>;
  verifiedUser: Page;
  unverifiedUser: Page;
  adminUser: Page;
}

/**
 * Login as a test user via the mock login API
 */
async function loginAs(page: Page, userId: TestUser): Promise<void> {
  const response = await page.request.post('/api/test/login', {
    data: { userId }
  });

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(`Mock login failed: ${errorBody.error || response.statusText()}`);
  }

  // Refresh the page to pick up the new session
  await page.reload();
}

/**
 * Logout by calling the mock logout API
 */
async function logout(page: Page): Promise<void> {
  await page.request.delete('/api/test/login');
  await page.reload();
}

/**
 * Extended test with authentication fixtures
 */
export const test = base.extend<AuthFixtures>({
  // Function to login as any test user
  loginAs: async ({ page }, use) => {
    await use(async (user: TestUser) => {
      await loginAs(page, user);
    });
  },

  // Function to logout
  logout: async ({ page }, use) => {
    await use(async () => {
      await logout(page);
    });
  },

  // Pre-authenticated as a verified user
  verifiedUser: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    // Navigate to any page first to initialize the session
    await page.goto('/');
    await loginAs(page, 'verified1');

    await use(page);
    await context.close();
  },

  // Pre-authenticated as an unverified user
  unverifiedUser: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/');
    await loginAs(page, 'unverified1');

    await use(page);
    await context.close();
  },

  // Pre-authenticated as an admin user
  adminUser: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/');
    await loginAs(page, 'admin');

    await use(page);
    await context.close();
  }
});

export { expect } from '@playwright/test';
