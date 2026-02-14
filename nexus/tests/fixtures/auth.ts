import { test as base, Page, Browser, StorageState } from '@playwright/test';

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
  verifiedStorageState: StorageState;
  unverifiedStorageState: StorageState;
  adminStorageState: StorageState;
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

async function buildStorageState(browser: Browser, userId: TestUser): Promise<StorageState> {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto('/');
  await loginAs(page, userId);

  const state = await context.storageState();
  await context.close();
  return state;
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

  verifiedStorageState: [async ({ browser }, use) => {
    await use(await buildStorageState(browser, 'verified1'));
  }, { scope: 'worker' }],

  unverifiedStorageState: [async ({ browser }, use) => {
    await use(await buildStorageState(browser, 'unverified1'));
  }, { scope: 'worker' }],

  adminStorageState: [async ({ browser }, use) => {
    await use(await buildStorageState(browser, 'admin'));
  }, { scope: 'worker' }],

  // Pre-authenticated as a verified user
  verifiedUser: async ({ browser, verifiedStorageState }, use) => {
    const context = await browser.newContext({ storageState: verifiedStorageState });
    const page = await context.newPage();

    await use(page);
    await context.close();
  },

  // Pre-authenticated as an unverified user
  unverifiedUser: async ({ browser, unverifiedStorageState }, use) => {
    const context = await browser.newContext({ storageState: unverifiedStorageState });
    const page = await context.newPage();

    await use(page);
    await context.close();
  },

  // Pre-authenticated as an admin user
  adminUser: async ({ browser, adminStorageState }, use) => {
    const context = await browser.newContext({ storageState: adminStorageState });
    const page = await context.newPage();

    await use(page);
    await context.close();
  }
});

export { expect } from '@playwright/test';
