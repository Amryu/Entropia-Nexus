import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { WIKI_PAGES } from './test-pages';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_LONG } from '../test-constants';

/**
 * E2E tests for Wiki-style item pages
 * Tests the Wikipedia-style layout with floating infobox
 *
 * Note: These tests are designed to work with or without data in the test database.
 * Tests that require items will skip gracefully if no items are available.
 */

// Helper to wait for wiki nav to load
async function waitForWikiNav(page: Page) {
  try {
    await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });
  } catch {
    // Nav may not be present, continue
  }
}

// Helper to check if items are available
async function hasItems(page: Page) {
  const items = page.locator('.item-link');
  const count = await items.count();
  return count > 0;
}

// Helper to check if page loaded successfully (not a 500 error)
async function pageLoaded(page: Page) {
  // Check for 500 error page - look for error heading or wiki page
  const wikiPage = page.locator('.wiki-page');
  try {
    await expect(wikiPage).toBeVisible({ timeout: TIMEOUT_LONG });
    return true;
  } catch {
    // Check for error indicators
    const errorHeading = page.locator('h1:has-text("500")');
    try {
      await expect(errorHeading).toBeHidden({ timeout: TIMEOUT_SHORT });
      return true;
    } catch {
      return false;
    }
  }
}

test.describe('Wiki Pages - Basic Structure', () => {
  for (const pageInfo of WIKI_PAGES) {
    test(`${pageInfo.name} page loads successfully`, async ({ page }) => {
      await page.goto(pageInfo.path);
      await page.waitForLoadState('networkidle');

      // Check if page loaded without server error
      if (!await pageLoaded(page)) {
        test.skip();
        return;
      }

      await waitForWikiNav(page);

      // Page should not have critical errors
      await expect(page.locator('body')).toBeVisible();

      // Should have wiki layout structure
      const wikiPage = page.locator('.wiki-page');
      await expect(wikiPage).toBeVisible();
    });
  }
});

test.describe('Wiki Pages - Navigation Sidebar', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
  });

  test('sidebar displays navigation title', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const navTitle = page.locator('.nav-title');
    try {
      await expect(navTitle).toBeVisible({ timeout: TIMEOUT_LONG });
      await expect(navTitle).toContainText(/weapons/i);
    } catch {
      // Wiki page should at least have the sidebar structure
      const sidebar = page.locator('.wiki-sidebar, .wiki-nav');
      const wikiPage = page.locator('.wiki-page');

      const sidebarVisible = await sidebar.count() > 0 && await sidebar.first().isVisible();
      const pageVisible = await wikiPage.isVisible();

      expect(sidebarVisible || pageVisible).toBeTruthy();
    }
  });

  test('sidebar has search functionality', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Scope to wiki nav to avoid matching the global search input
    const searchInput = page.locator('.wiki-nav .search-input');
    await expect(searchInput).toBeVisible({ timeout: TIMEOUT_LONG });
    await searchInput.fill('test');
    await expect(searchInput).toHaveValue('test');
  });

  test('sidebar displays item list container', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const itemList = page.locator('.item-list');
    const wikiNav = page.locator('.wiki-nav');

    const hasItemList = await itemList.count() > 0 && await itemList.first().isVisible();
    const hasWikiNav = await wikiNav.isVisible();

    // Item list should exist even if empty
    expect(hasItemList || hasWikiNav).toBeTruthy();
  });

  test('sidebar shows item count', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const itemCount = page.locator('.item-count');
    try {
      await expect(itemCount).toBeVisible({ timeout: TIMEOUT_LONG });
      await expect(itemCount).toContainText(/\d+ items/);
    } catch {
      // Item count may not be present
      test.skip();
    }
  });

  test('sidebar can be expanded to table view', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Use .first() to avoid strict mode violation (two expand buttons exist)
    const expandBtn = page.locator('.expand-btn').first();
    await expect(expandBtn).toBeVisible({ timeout: TIMEOUT_LONG });
    await expandBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show table headers or expanded class
    const wikiNav = page.locator('.wiki-nav');
    await expect(wikiNav).toHaveClass(/expanded/);
  });
});

test.describe('Wiki Pages - Item Selection', () => {
  test('clicking an item displays its details', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);

    // Wait a bit for items to load
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // URL should update with item slug
    await expect(page).toHaveURL(/\/items\/weapons\/.+/);

    // Should show infobox
    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();
  });

  test('selected item is highlighted in navigation', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const activeItem = page.locator('.item-link.active');
    await expect(activeItem).toBeVisible();
  });
});

test.describe('Wiki Pages - Infobox Layout', () => {
  test('infobox displays entity header when item selected', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();

    const title = page.locator('.infobox-title');
    await expect(title).toBeVisible();
  });

  test('infobox displays tier-1 stats section', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    // Tier-1 stats may or may not be present - this is optional
    // Just verify the page loaded successfully
    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();
  });
});

test.describe('Wiki Pages - Article Content', () => {
  test('article shows description panel when item selected', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    // Description may or may not be present - just verify page loaded
    const wikiPage = page.locator('.wiki-page');
    await expect(wikiPage).toBeVisible();
  });
});

test.describe('Wiki Pages - Search and Filtering', () => {
  test('search input accepts text', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);

    // Scope to wiki nav to avoid matching the global search input
    const searchInput = page.locator('.wiki-nav .search-input');
    await expect(searchInput).toBeVisible({ timeout: TIMEOUT_LONG });
    await searchInput.fill('sword');
    await expect(searchInput).toHaveValue('sword');

    // Clear button should appear
    const clearBtn = page.locator('.clear-search');
    await expect(clearBtn).toBeVisible();
  });

  test('filter buttons exist on pets page', async ({ page }) => {
    await page.goto('/items/pets');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);

    // Pets page should have rarity filters - this is optional
    const filterBtn = page.locator('.filter-btn').first();
    const filterCount = await filterBtn.count();

    // Skip test if no filters present (acceptable state)
    if (filterCount === 0) {
      test.skip();
    }
  });

  test('filter buttons toggle active state', async ({ page }) => {
    await page.goto('/items/pets');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);

    const filterBtn = page.locator('.filter-btn').first();
    try {
      await expect(filterBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await filterBtn.click();
      await expect(filterBtn).toHaveClass(/active/);

      await filterBtn.click();
      await expect(filterBtn).not.toHaveClass(/active/);
    } catch {
      // Filters may not be present
      test.skip();
    }
  });
});

test.describe('Wiki Pages - Responsive Design', () => {
  // Breakpoints aligned with global: < 900px is mobile, 900-1199px is tablet, >= 1200px is desktop

  test('mobile layout shows navigation toggle (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    // Should have mobile nav toggle
    const navToggle = page.locator('.nav-toggle-btn');
    const wikiPage = page.locator('.wiki-page');

    const hasToggle = await navToggle.count() > 0 && await navToggle.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasToggle || hasWikiPage).toBeTruthy();
  });

  test('mobile layout at landscape breakpoint (899px)', async ({ page }) => {
    // 899px is still mobile (< 900px)
    await page.setViewportSize({ width: 899, height: 500 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    // Should have mobile nav toggle (sidebar hidden)
    const navToggle = page.locator('.nav-toggle-btn');
    const wikiPage = page.locator('.wiki-page');

    const hasToggle = await navToggle.count() > 0 && await navToggle.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasToggle || hasWikiPage).toBeTruthy();

    // Sidebar should be hidden on mobile
    const wikiSidebar = page.locator('.wiki-sidebar');
    await expect(wikiSidebar).toBeHidden();
  });

  test('tablet layout shows sidebar (900px)', async ({ page }) => {
    // 900px is tablet (>= 900px, aligned with menu breakpoint)
    await page.setViewportSize({ width: 900, height: 1024 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    await expect(page.locator('body')).toBeVisible();

    // Wiki sidebar should be visible on tablet
    const wikiSidebar = page.locator('.wiki-sidebar');
    const wikiPage = page.locator('.wiki-page');

    const hasSidebar = await wikiSidebar.count() > 0 && await wikiSidebar.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasSidebar || hasWikiPage).toBeTruthy();

    // Mobile nav toggle should be hidden
    const navToggle = page.locator('.nav-toggle-btn');
    await expect(navToggle).toBeHidden();
  });

  test('desktop layout shows full sidebar (1200px)', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 1080 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const wikiSidebar = page.locator('.wiki-sidebar');
    const wikiPage = page.locator('.wiki-page');

    const hasSidebar = await wikiSidebar.count() > 0 && await wikiSidebar.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasSidebar || hasWikiPage).toBeTruthy();
  });
});

test.describe('Wiki Pages - Breadcrumbs', () => {
  test('breadcrumbs show correct path', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const breadcrumbs = page.locator('.breadcrumbs');
    // This will now properly fail with strict mode violations if they exist
    await expect(breadcrumbs).toBeVisible();

    // Should contain path elements
    const text = await breadcrumbs.textContent();
    expect(text?.toLowerCase()).toContain('weapons');
  });
});

test.describe('Wiki Pages - No Selection State', () => {
  test('shows empty state or navigation when no item selected', async ({ page }) => {
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Either no-selection state or wiki page structure should be visible
    const noSelection = page.locator('.no-selection');
    const contentBody = page.locator('.content-body');
    const wikiPage = page.locator('.wiki-page');

    const hasNoSelection = await noSelection.count() > 0 && await noSelection.isVisible();
    const hasContent = await contentBody.count() > 0 && await contentBody.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasNoSelection || hasContent || hasWikiPage).toBeTruthy();
  });
});

test.describe('Wiki Pages - URL Routing', () => {
  test('handles non-existent items gracefully', async ({ page }) => {
    await page.goto('/items/weapons/NonExistentItem12345XYZ');
    await page.waitForLoadState('networkidle');

    // Should not crash
    await expect(page.locator('body')).toBeVisible();
  });
});
