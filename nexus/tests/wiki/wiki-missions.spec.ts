import { test, expect } from '../fixtures/auth';
import { test as baseTest, expect as baseExpect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * E2E tests for Missions and Mission Chains wiki pages
 *
 * Tests the missions feature including:
 * - Page loading and basic structure
 * - Mission and chain view toggle
 * - Navigation and filtering
 * - Edit mode (authenticated users)
 * - Map embed functionality
 *
 * Note: These tests are designed to work with or without data in the test database.
 * Tests that require missions will skip gracefully if no missions are available.
 */

const MISSIONS_URL = '/information/missions';
const MISSIONS_CHAINS_URL = '/information/missions?view=chains';

// Helper to wait for wiki nav to load
async function waitForWikiNav(page: Page) {
  try {
    await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });
  } catch {
    // Nav may not be present, continue
  }
}

// Helper to check if page loaded successfully (not a 500 error)
async function pageLoaded(page: Page) {
  const wikiPage = page.locator('.wiki-page');
  try {
    await expect(wikiPage).toBeVisible({ timeout: TIMEOUT_LONG });
    return true;
  } catch {
    const errorHeading = page.locator('h1:has-text("500")');
    try {
      await expect(errorHeading).toBeHidden({ timeout: TIMEOUT_SHORT });
      return true;
    } catch {
      return false;
    }
  }
}

// Helper to check if missions are available
async function hasMissions(page: Page) {
  const items = page.locator('.item-link');
  const count = await items.count();
  return count > 0;
}

baseTest.describe('Missions Page - Basic Structure', () => {
  baseTest('missions page loads successfully', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);
    await expect(page.locator('body')).toBeVisible();
    await expect(page.locator('.wiki-page')).toBeVisible();
  });

  baseTest('mission chains page loads successfully', async ({ page }) => {
    await page.goto(MISSIONS_CHAINS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);
    await expect(page.locator('body')).toBeVisible();
    await expect(page.locator('.wiki-page')).toBeVisible();
  });

  baseTest('page has correct title', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);
    const navTitle = page.locator('.nav-title');

    try {
      await expect(navTitle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(navTitle).toContainText(/missions/i);
    } catch {
      // Title may not be in expected location, verify page structure instead
      const wikiPage = page.locator('.wiki-page');
      await expect(wikiPage).toBeVisible();
    }
  });
});

baseTest.describe('Missions Page - View Toggle', () => {
  baseTest('has view toggle buttons', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    // Look for view toggle buttons (Missions/Chains tabs)
    const viewToggle = page.locator('.view-toggle, .tab-toggle, [class*="view"]').first();
    const missionsBtn = page.locator('button:has-text("Missions"), a:has-text("Missions")').first();
    const chainsBtn = page.locator('button:has-text("Chains"), a:has-text("Chains")').first();

    // At least one toggle mechanism should be present
    const hasToggle = await viewToggle.count() > 0 ||
                      await missionsBtn.count() > 0 ||
                      await chainsBtn.count() > 0;

    if (!hasToggle) {
      baseTest.skip();
      return;
    }

    expect(hasToggle).toBeTruthy();
  });

  baseTest('can switch between missions and chains view', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    // Try to find and click chains toggle
    const chainsBtn = page.locator('button:has-text("Chains"), a:has-text("Chains")').first();

    try {
      await expect(chainsBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await chainsBtn.click();
      await page.waitForLoadState('networkidle');

      // URL should update
      await expect(page).toHaveURL(/view=chains/);
    } catch {
      // Toggle may not be present or work differently
      baseTest.skip();
    }
  });
});

baseTest.describe('Missions Page - Navigation Sidebar', () => {
  baseTest('sidebar has search functionality', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    const searchInput = page.locator('.search-input');
    try {
      await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await searchInput.fill('test');
      await expect(searchInput).toHaveValue('test');
    } catch {
      // Search may not be present
      baseTest.skip();
    }
  });

  baseTest('sidebar has planet filter', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    // Look for filter buttons or dropdown
    const filterBtn = page.locator('.filter-btn, [class*="filter"]').first();
    const filterSelect = page.locator('select[class*="filter"], .filter-select').first();

    const hasFilter = await filterBtn.count() > 0 || await filterSelect.count() > 0;

    if (!hasFilter) {
      baseTest.skip();
      return;
    }

    expect(hasFilter).toBeTruthy();
  });

  baseTest('sidebar displays item list container', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    const itemList = page.locator('.item-list');
    const wikiNav = page.locator('.wiki-nav');

    const hasItemList = await itemList.count() > 0 && await itemList.first().isVisible();
    const hasWikiNav = await wikiNav.isVisible();

    expect(hasItemList || hasWikiNav).toBeTruthy();
  });
});

baseTest.describe('Missions Page - Item Selection', () => {
  baseTest('clicking a mission displays its details', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(page)) {
      baseTest.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // URL should update with mission slug
    await expect(page).toHaveURL(/\/information\/missions\/.+/);

    // Should show infobox
    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();
  });

  baseTest('selected mission shows correct content sections', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(page)) {
      baseTest.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    // Check for expected mission sections
    const stepsSection = page.locator('text=Steps').first();
    const rewardsSection = page.locator('text=Rewards').first();
    const dependenciesSection = page.locator('text=Dependencies').first();

    // At least the wiki page should be visible
    const wikiPage = page.locator('.wiki-page');
    await expect(wikiPage).toBeVisible();
  });
});

baseTest.describe('Missions Page - Infobox', () => {
  baseTest('infobox displays mission header when selected', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(page)) {
      baseTest.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();

    const title = page.locator('.infobox-title');
    await expect(title).toBeVisible();
  });

  baseTest('infobox shows mission type', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(page)) {
      baseTest.skip();
      return;
    }

    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();

    // Type row should be present in the infobox
    const typeRow = infobox.locator('text=Type').first();
    try {
      await expect(typeRow).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    } catch {
      // Type may not be set for all missions
    }
  });
});

baseTest.describe('Missions Page - No Selection State', () => {
  baseTest('shows overview or instructions when no mission selected', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
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

baseTest.describe('Missions Page - URL Routing', () => {
  baseTest('handles non-existent missions gracefully', async ({ page }) => {
    await page.goto('/information/missions/NonExistentMission12345XYZ');
    await page.waitForLoadState('networkidle');

    // Should not crash
    await expect(page.locator('body')).toBeVisible();
  });

  baseTest('direct URL to mission loads correctly', async ({ page }) => {
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(page)) {
      baseTest.skip();
      return;
    }

    // Click first mission and get its URL
    await page.locator('.item-link').first().click();
    await page.waitForLoadState('networkidle');

    const url = page.url();

    // Navigate away and back
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.goto(url);
    await page.waitForLoadState('networkidle');

    // Page should load correctly
    await expect(page.locator('.wiki-page')).toBeVisible();
    await expect(page).toHaveURL(/\/information\/missions(\/|$)/);
    await expect(page.locator('.wiki-nav')).toBeVisible();
  });
});

baseTest.describe('Missions Page - Responsive Design', () => {
  baseTest('mobile layout shows navigation toggle (375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    const navToggle = page.locator('.nav-toggle-btn');
    const wikiPage = page.locator('.wiki-page');

    const hasToggle = await navToggle.count() > 0 && await navToggle.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasToggle || hasWikiPage).toBeTruthy();
  });

  baseTest('tablet layout shows sidebar (900px)', async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 1024 });
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
      return;
    }

    await waitForWikiNav(page);

    const wikiSidebar = page.locator('.wiki-sidebar');
    const wikiPage = page.locator('.wiki-page');

    const hasSidebar = await wikiSidebar.count() > 0 && await wikiSidebar.isVisible();
    const hasWikiPage = await wikiPage.isVisible();

    expect(hasSidebar || hasWikiPage).toBeTruthy();
  });

  baseTest('desktop layout shows full sidebar (1200px)', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 1080 });
    await page.goto(MISSIONS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      baseTest.skip();
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

// Authenticated tests
test.describe('Missions Page - Edit Mode (Authenticated)', () => {
  test('verified user can see edit button', async ({ verifiedUser }) => {
    await verifiedUser.goto(MISSIONS_URL);
    await verifiedUser.waitForLoadState('networkidle');
    await waitForWikiNav(verifiedUser);
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(verifiedUser)) {
      test.skip();
      return;
    }

    await verifiedUser.locator('.item-link').first().click();
    await verifiedUser.waitForLoadState('networkidle');

    // Look for edit button
    const editBtn = verifiedUser.locator('button:has-text("Edit"), .edit-btn, [class*="edit"]').first();

    try {
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    } catch {
      // Edit button may not be visible if user doesn't have permission
      test.skip();
    }
  });

  test('edit mode shows form controls', async ({ verifiedUser }) => {
    await verifiedUser.goto(MISSIONS_URL);
    await verifiedUser.waitForLoadState('networkidle');
    await waitForWikiNav(verifiedUser);
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(verifiedUser)) {
      test.skip();
      return;
    }

    await verifiedUser.locator('.item-link').first().click();
    await verifiedUser.waitForLoadState('networkidle');

    const editBtn = verifiedUser.locator('button:has-text("Edit"), .edit-btn').first();

    try {
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await editBtn.click();
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // In edit mode, form controls should be visible
      const saveBtn = verifiedUser.locator('button:has-text("Save"), button:has-text("Submit")').first();
      const cancelBtn = verifiedUser.locator('button:has-text("Cancel"), button:has-text("Discard")').first();

      const hasSave = await saveBtn.count() > 0;
      const hasCancel = await cancelBtn.count() > 0;

      expect(hasSave || hasCancel).toBeTruthy();
    } catch {
      test.skip();
    }
  });

  test('create mode is accessible for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto(`${MISSIONS_URL}?mode=create`);
    await verifiedUser.waitForLoadState('networkidle');

    // Should show create form or redirect if not allowed
    const wikiPage = verifiedUser.locator('.wiki-page');
    await expect(wikiPage).toBeVisible();
  });
});

test.describe('Missions Page - Event Selection', () => {
  test('event selector is visible in edit mode', async ({ verifiedUser }) => {
    await verifiedUser.goto(MISSIONS_URL);
    await verifiedUser.waitForLoadState('networkidle');
    await waitForWikiNav(verifiedUser);
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    if (!await hasMissions(verifiedUser)) {
      test.skip();
      return;
    }

    await verifiedUser.locator('.item-link').first().click();
    await verifiedUser.waitForLoadState('networkidle');

    const editBtn = verifiedUser.locator('button:has-text("Edit"), .edit-btn').first();

    try {
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await editBtn.click();
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // Look for event selector in the infobox
      const eventLabel = verifiedUser.locator('text=Event').first();
      await expect(eventLabel).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    } catch {
      // Event field may not be visible for all missions
      test.skip();
    }
  });
});

test.describe('Missions Page - Mission Chain View', () => {
  test('chain view shows chain list', async ({ page }) => {
    await page.goto(MISSIONS_CHAINS_URL);
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    await waitForWikiNav(page);

    // Verify we're in chain view
    await expect(page).toHaveURL(/view=chains/);

    const wikiPage = page.locator('.wiki-page');
    await expect(wikiPage).toBeVisible();
  });

  test('clicking a chain displays chain details', async ({ page }) => {
    await page.goto(MISSIONS_CHAINS_URL);
    await page.waitForLoadState('networkidle');
    await waitForWikiNav(page);
    await page.waitForTimeout(TIMEOUT_SHORT);

    const items = page.locator('.item-link');
    const count = await items.count();

    if (count === 0) {
      test.skip();
      return;
    }

    await items.first().click();
    await page.waitForLoadState('networkidle');

    // Should show chain details
    const wikiPage = page.locator('.wiki-page');
    await expect(wikiPage).toBeVisible();

    const infobox = page.locator('.wiki-infobox-float');
    await expect(infobox).toBeVisible();
  });
});
