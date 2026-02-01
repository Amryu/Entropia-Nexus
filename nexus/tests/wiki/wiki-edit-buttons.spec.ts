import { test, expect } from '../fixtures/auth';
import type { Page } from '@playwright/test';
import { WIKI_PAGE_PATHS } from './test-pages';
import { TIMEOUT_LONG } from '../test-constants';

async function waitForWikiNav(page: Page) {
  try {
    await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });
  } catch {
    // Wiki nav may not be present on all pages
  }
}

async function hasItems(page: Page) {
  const items = page.locator('.item-link');
  const count = await items.count();
  return count > 0;
}

const WIKI_PAGES = WIKI_PAGE_PATHS;

test.describe('Wiki Edit Buttons - User State Dependent', () => {
  test.describe('Logged Out User', () => {
    for (const pagePath of WIKI_PAGES) {
      test(`shows "Login to Edit" on ${pagePath}`, async ({ page }) => {
        await page.goto(pagePath);
        await page.waitForLoadState('networkidle');
        await waitForWikiNav(page);

        if (!await hasItems(page)) {
          test.skip();
          return;
        }

        const firstItem = page.locator('.item-link').first();
        await firstItem.click();
        await page.waitForLoadState('networkidle');

        // Wait for the header actions to be present
        try {
          await page.waitForSelector('.header-actions', { timeout: TIMEOUT_LONG });
        } catch {
          // Header actions may not be present immediately
        }

        const loginButton = page.locator('button:has-text(\"Login to Edit\"), a:has-text(\"Login to Edit\")');
        await expect(loginButton).toBeVisible({ timeout: TIMEOUT_LONG });
      });
    }
  });

  test.describe('Unverified User', () => {
    for (const pagePath of WIKI_PAGES) {
      test(`shows "Verify to Edit" on ${pagePath}`, async ({ unverifiedUser }) => {
        await unverifiedUser.goto(pagePath);
        await unverifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(unverifiedUser);

        if (!await hasItems(unverifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = unverifiedUser.locator('.item-link').first();
        await firstItem.click();
        await unverifiedUser.waitForLoadState('networkidle');

        // Wait for the header actions to be present
        try {
          await unverifiedUser.waitForSelector('.header-actions', { timeout: TIMEOUT_LONG });
        } catch {
          // Header actions may not be present immediately
        }

        const verifyButton = unverifiedUser.locator('button:has-text(\"Verify to Edit\"), a:has-text(\"Verify to Edit\")');
        await expect(verifyButton).toBeVisible({ timeout: TIMEOUT_LONG });
      });
    }
  });

  test.describe('Verified User', () => {
    for (const pagePath of WIKI_PAGES) {
      test(`shows "Edit" button on ${pagePath}`, async ({ verifiedUser }) => {
        await verifiedUser.goto(pagePath);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        // Wait for the header actions to be present
        try {
          await verifiedUser.waitForSelector('.header-actions', { timeout: TIMEOUT_LONG });
        } catch {
          // Header actions may not be present immediately
        }

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await expect(editButton).toBeVisible({ timeout: TIMEOUT_LONG });
      });
    }

    test('does NOT show "Edit" button for enhancers (database-generated)', async ({ verifiedUser }) => {
      await verifiedUser.goto('/items/attachments/enhancers');
      await verifiedUser.waitForLoadState('networkidle');
      await waitForWikiNav(verifiedUser);

      if (!await hasItems(verifiedUser)) {
        test.skip();
        return;
      }

      const firstItem = verifiedUser.locator('.item-link').first();
      await firstItem.click();
      await verifiedUser.waitForLoadState('networkidle');

      // Wait for the header actions to be present
      try {
        await verifiedUser.waitForSelector('.header-actions', { timeout: TIMEOUT_LONG });
      } catch {
        // Header actions may not be present immediately
      }

      const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
      // For enhancers, the button should not exist at all
      await expect(editButton).not.toBeVisible();
    });
  });
});
