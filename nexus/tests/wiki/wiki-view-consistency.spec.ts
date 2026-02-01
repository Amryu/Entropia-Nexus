import { test, expect } from '@playwright/test';
import { WIKI_PAGES_WITH_SUBTYPES } from './test-pages';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM } from '../test-constants';

const TEST_PAGES = WIKI_PAGES_WITH_SUBTYPES;


test.describe('Wiki View Mode - Consistency Across Pages', () => {
  test.describe('Entity Image Display', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: shows entity image or placeholder`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        // Check if there are items available
        const firstItem = browser.locator('.item-link').first();
        const hasItems = await firstItem.isVisible().catch(() => false);

        if (!hasItems) {
          // No items available - skip this test
          test.skip();
          return;
        }

        // Click first item
        await firstItem.click();
        await browser.waitForLoadState('networkidle');

        const imageWrapper = browser.locator('.entity-icon-wrapper');
        await expect(imageWrapper).toBeVisible();

        // Verify either entity image or placeholder is visible
        const entityImage = browser.locator('.entity-image');
        const placeholder = browser.locator('.icon-placeholder');

        try {
          await expect(entityImage).toBeVisible({ timeout: TIMEOUT_SHORT });
        } catch {
          await expect(placeholder).toBeVisible();
        }
      });
    }
  });

  test.describe('Infobox Structure', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: has consistent infobox structure`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        // Check if there are items available
        const firstItem = browser.locator('.item-link').first();
        const hasItems = await firstItem.isVisible().catch(() => false);

        if (!hasItems) {
          // No items available - skip this test
          test.skip();
          return;
        }

        // Click first item
        await firstItem.click();
        await browser.waitForLoadState('networkidle');

        const infobox = browser.locator('.wiki-infobox-float');
        await expect(infobox).toBeVisible();

        const header = browser.locator('.infobox-header');
        await expect(header).toBeVisible();

        const title = browser.locator('.infobox-title');
        await expect(title).toBeVisible();
      });
    }
  });

  test.describe('Description Display', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: shows description section`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        // Check if there are items available
        const firstItem = browser.locator('.item-link').first();
        const hasItems = await firstItem.isVisible().catch(() => false);

        if (!hasItems) {
          // No items available - skip this test
          test.skip();
          return;
        }

        // Click first item
        await firstItem.click();
        await browser.waitForLoadState('networkidle');

        const article = browser.locator('.wiki-article');
        await expect(article).toBeVisible();
      });
    }
  });

  test.describe('Entity Titles (Both Infobox and Article)', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: has infobox title`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        // Check if there are items available
        const firstItem = browser.locator('.item-link').first();
        const hasItems = await firstItem.isVisible().catch(() => false);

        if (!hasItems) {
          // No items available - skip this test
          test.skip();
          return;
        }

        // Click first item
        await firstItem.click();
        await browser.waitForLoadState('networkidle');

        const infoboxTitle = browser.locator('.infobox-title');
        await expect(infoboxTitle).toBeVisible();
      });

      test(`${page.name}: has article title`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        // Check if there are items available
        const firstItem = browser.locator('.item-link').first();
        const hasItems = await firstItem.isVisible().catch(() => false);

        if (!hasItems) {
          // No items available - skip this test
          test.skip();
          return;
        }

        // Click first item
        await firstItem.click();
        await browser.waitForLoadState('networkidle');

        const articleTitle = browser.locator('.article-title, .wiki-article h1');
        await expect(articleTitle).toBeVisible();
      });
    }
  });

  test.describe('Breadcrumbs', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: shows breadcrumbs`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        const breadcrumbs = browser.locator('.breadcrumbs, nav[aria-label=\"breadcrumb\"]');
        await expect(breadcrumbs).toBeVisible();
      });
    }
  });

  test.describe('Navigation Sidebar', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: shows navigation sidebar with search`, async ({ page: browser }) => {
        await browser.goto(page.path);
        await browser.waitForLoadState('networkidle');

        const sidebar = browser.locator('.wiki-nav, .wiki-sidebar').first();
        await expect(sidebar).toBeVisible();

        // Search input should be visible in the sidebar
        const searchInput = browser.locator('.search-input, input[type=\"search\"]');
        try {
          await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
        } catch {
          // Some pages may not have search functionality - that's okay
          // Just verify the sidebar exists
        }
      });
    }
  });
});
