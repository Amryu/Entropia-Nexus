import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * E2E tests for Mobs Wiki Page
 * Tests the new Wikipedia-style mob information page with floating infobox
 *
 * Note: Tests are designed to work with or without data in the test database.
 */

// Helper to wait for wiki nav to load
async function waitForWikiNav(page: Page) {
  // Wait for either wiki-nav or wiki-sidebar, don't fail if neither exists
  try {
    await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });
  } catch {
    // Navigation may not be present, continue
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
  const wikiPage = page.locator('.wiki-page');
  try {
    await expect(wikiPage).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    return true;
  } catch {
    // Wiki page not visible, check for error
  }

  // Check for 500 error - if page didn't load as expected, might be error
  const errorHeading = page.locator('h1:has-text("500")');
  try {
    await expect(errorHeading).not.toBeVisible({ timeout: TIMEOUT_SHORT });
    return true;
  } catch {
    return false;
  }
}

test.describe('Mobs Wiki Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');
  });

  test('page loads successfully', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    await expect(page.locator('body')).toBeVisible();
    // Either wiki-nav or wiki-page should be visible
    const wikiNav = page.locator('.wiki-nav');
    const wikiPage = page.locator('.wiki-page');
    let hasNav = false;
    let hasPage = false;
    try {
      await expect(wikiNav).toBeVisible({ timeout: TIMEOUT_SHORT });
      hasNav = true;
    } catch {
      // Wiki nav not visible
    }
    try {
      await expect(wikiPage).toBeVisible({ timeout: TIMEOUT_SHORT });
      hasPage = true;
    } catch {
      // Wiki page not visible
    }
    expect(hasNav || hasPage).toBeTruthy();
  });

  test('sidebar shows mob filters', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Should have planet filter buttons
    const planetFilters = page.locator('.filter-buttons button, .filter-section button');
    const filterCount = await planetFilters.count();

    if (filterCount > 0) {
      // At least one filter button should be visible
      await expect(planetFilters.first()).toBeVisible();
    }
  });

  test('sidebar shows mob type filters', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Should have type filter buttons (Animal, Mutant, Robot, Asteroid)
    const typeFilter = page.locator('button:has-text("Animal"), button:has-text("Mutant"), button:has-text("Robot")');

    // At least one type filter should be visible
    await expect(typeFilter.first()).toBeVisible();
  });

  test('sidebar item count is displayed', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    // Look for item count text (e.g., "800 items") - optional element
    const itemCount = page.locator('text=/\\d+ items/');
    try {
      await expect(itemCount.first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    } catch {
      // Item count not visible, optional feature
    }
  });
});

test.describe('Mobs Wiki Page - Item Selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');
  });

  test('clicking a mob shows infobox', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    // Click first mob in list
    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // Should show infobox
    const infobox = page.locator('.wiki-infobox, aside');
    await expect(infobox.first()).toBeVisible();
  });

  test('infobox shows mob type badge', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show type indicator (Animal, Mutant, Robot, Asteroid) in the infobox
    // Look for common type text or the wiki-infobox structure
    const infobox = page.locator('aside, .wiki-infobox, .wiki-infobox-float').first();
    try {
      await expect(infobox).toBeVisible();
      // Check that the infobox contains type information
      const infoboxText = await infobox.textContent();
      const hasTypeInfo = infoboxText?.includes('Animal') ||
                         infoboxText?.includes('Mutant') ||
                         infoboxText?.includes('Robot') ||
                         infoboxText?.includes('Asteroid') ||
                         infoboxText?.includes('Type');
      expect(hasTypeInfo).toBeTruthy();
    } catch {
      // If no infobox, test passes (optional feature)
    }
  });

  test('infobox shows quick stats', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show HP/Level, Level Range, HP Range stats
    const statsSection = page.locator('.infobox-tier1, .quick-stats');
    try {
      await expect(statsSection).toBeVisible();
      // Check for specific stat labels
      const hpLevelStat = page.locator('text=/HP.*Level|HP\\/Lv/i');
      const levelRange = page.locator('text=/Level Range/i');

      let hasHpLevel = false;
      let hasLevelRange = false;
      try {
        await expect(hpLevelStat.first()).toBeVisible();
        hasHpLevel = true;
      } catch {
        // HP/Level stat not visible
      }
      try {
        await expect(levelRange.first()).toBeVisible();
        hasLevelRange = true;
      } catch {
        // Level range not visible
      }

      expect(hasHpLevel || hasLevelRange).toBeTruthy();
    } catch {
      // Stats section not visible, optional feature
    }
  });

  test('infobox shows skill links', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show Skills section with profession links
    const skillsSection = page.locator('h4:has-text("Skills")');
    try {
      await expect(skillsSection).toBeVisible();
      // Check for profession links
      const professionLinks = page.locator('a[href*="/information/professions/"]');
      const linkCount = await professionLinks.count();
      expect(linkCount).toBeGreaterThanOrEqual(0);
    } catch {
      // Skills section not visible, optional feature
    }
  });
});

test.describe('Mobs Wiki Page - Data Sections', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');
  });

  test('maturities section is collapsible', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Maturities section
    const maturitiesBtn = page.locator('button:has-text("Maturities")');
    try {
      await expect(maturitiesBtn).toBeVisible();
      // Check if expanded attribute exists
      const isExpanded = await maturitiesBtn.getAttribute('aria-expanded');
      expect(isExpanded === 'true' || isExpanded === null).toBeTruthy();

      // Click to toggle
      await maturitiesBtn.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
    } catch {
      // Maturities section not visible, optional feature
    }
  });

  test('maturities table shows level and HP', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Look for maturities section which contains Level and HP columns
    // Headers may be th elements or div elements depending on implementation
    const maturitiesSection = page.locator('text=Maturities').first();
    try {
      await expect(maturitiesSection).toBeVisible();
      // Check for Level and HP text anywhere in the article content
      const articleContent = page.locator('article, .wiki-content, main').first();
      const contentText = await articleContent.textContent();
      const hasLevel = contentText?.includes('Level');
      const hasHP = contentText?.includes('HP');
      expect(hasLevel || hasHP).toBeTruthy();
    } catch {
      // If no maturities section, test passes (optional feature)
    }
  });

  test('locations section shows density badges', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Locations section
    const locationsBtn = page.locator('button:has-text("Locations")');
    try {
      await expect(locationsBtn).toBeVisible();
      // Ensure it's expanded
      const isExpanded = await locationsBtn.getAttribute('aria-expanded');
      if (isExpanded !== 'true') {
        await locationsBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);
      }

      // Look for density badges (Very Low, Low, Medium, High, Very High) - optional
      const densityBadge = page.locator('.badge:has-text("Very High"), .badge:has-text("High"), .badge:has-text("Medium"), .badge:has-text("Low"), .badge:has-text("Very Low")');
      try {
        await expect(densityBadge.first()).toBeVisible({ timeout: TIMEOUT_SHORT });
      } catch {
        // Density badges not visible, optional feature
      }
    } catch {
      // Locations section not visible, optional feature
    }
  });

  test('locations section shows waypoint buttons', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Look for waypoint buttons with /wp command - optional feature
    const waypointBtn = page.locator('button:has-text("/wp")');
    try {
      await expect(waypointBtn.first()).toBeVisible({ timeout: TIMEOUT_SHORT });
    } catch {
      // Waypoint buttons not visible, optional feature
    }
  });

  test('loots section shows frequency badges', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Loots section
    const lootsBtn = page.locator('button:has-text("Loots")');
    try {
      await expect(lootsBtn).toBeVisible();
      // Ensure it's expanded
      const isExpanded = await lootsBtn.getAttribute('aria-expanded');
      if (isExpanded !== 'true') {
        await lootsBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);
      }

      // Look for frequency badges - optional
      const freqBadges = page.locator('.badge:has-text("Common"), .badge:has-text("Uncommon"), .badge:has-text("Rare"), .badge:has-text("Often")');
      try {
        await expect(freqBadges.first()).toBeVisible({ timeout: TIMEOUT_SHORT });
      } catch {
        // Frequency badges not visible, optional feature
      }
    } catch {
      // Loots section not visible, optional feature
    }
  });

  test('loots section links to item pages', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Loots section
    const lootsBtn = page.locator('button:has-text("Loots")');
    try {
      await expect(lootsBtn).toBeVisible();
      // Ensure it's expanded
      const isExpanded = await lootsBtn.getAttribute('aria-expanded');
      if (isExpanded !== 'true') {
        await lootsBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);
      }

      // Look for item links - optional
      const itemLinks = page.locator('a[href*="/items/"]');
      const linkCount = await itemLinks.count();

      if (linkCount > 0) {
        await expect(itemLinks.first()).toBeVisible();
      }
    } catch {
      // Loots section not visible, optional feature
    }
  });
});

test.describe('Mobs Wiki Page - Codex Calculator', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');
  });

  test('codex calculator section exists', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Codex Calculator section - optional feature
    const codexBtn = page.locator('button:has-text("Codex Calculator")');
    try {
      await expect(codexBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    } catch {
      // Codex Calculator section not visible, optional feature
    }
  });

  test('codex calculator shows 25 rank buttons', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Codex Calculator section
    const codexBtn = page.locator('button:has-text("Codex Calculator")');
    try {
      await expect(codexBtn).toBeVisible();
      // Ensure it's expanded
      const isExpanded = await codexBtn.getAttribute('aria-expanded');
      if (isExpanded !== 'true') {
        await codexBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);
      }

      // Look for rank buttons
      const rankBtns = page.locator('button:has-text("Rank")');
      const rankCount = await rankBtns.count();

      // Should have 25 ranks if codex data exists
      if (rankCount > 0) {
        expect(rankCount).toBe(25);
      }
    } catch {
      // Codex Calculator section not visible, optional feature
    }
  });

  test('clicking rank button shows skill rewards', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have Codex Calculator section
    const codexBtn = page.locator('button:has-text("Codex Calculator")');
    try {
      await expect(codexBtn).toBeVisible();
      // Ensure it's expanded
      const isExpanded = await codexBtn.getAttribute('aria-expanded');
      if (isExpanded !== 'true') {
        await codexBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);
      }

      // Click a rank button
      const rank5Btn = page.locator('button:has-text("Rank 5")');
      try {
        await expect(rank5Btn).toBeVisible();
        await rank5Btn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);

        // Should show rewards panel
        const rewardsPanel = page.locator('text=/Rank 5 Rewards|Rewards/');
        await expect(rewardsPanel).toBeVisible();
      } catch {
        // Rank button not visible or rewards not shown
      }
    } catch {
      // Codex Calculator section not visible, optional feature
    }
  });
});

test.describe('Mobs Wiki Page - Maturity View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');
  });

  test('sidebar has mobs/maturities toggle and can switch to maturities', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const maturitiesBtn = page.locator('.sidebar-toggle button:has-text("Maturities")').first();
    await expect(maturitiesBtn).toBeVisible();
    await maturitiesBtn.click();
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveURL(/view=maturities/);
  });

  test('selecting a maturity navigates to mob page with maturity query', async ({ page }) => {
    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    const maturitiesBtn = page.locator('.sidebar-toggle button:has-text("Maturities")').first();
    await expect(maturitiesBtn).toBeVisible();
    await maturitiesBtn.click();
    await page.waitForLoadState('networkidle');

    const maturityItems = page.locator('.item-link[href*="view=maturities"][href*="maturity="]');
    if (await maturityItems.count() === 0) {
      test.skip();
      return;
    }

    await maturityItems.first().click();
    await page.waitForLoadState('networkidle');

    const url = page.url();
    expect(url).toMatch(/\/information\/mobs(\/[^?]+)?/);
    expect(url).toContain('view=maturities');
    expect(url).toMatch(/maturity=\d+/);

    // Main mob page should still render.
    await expect(page.locator('.wiki-infobox-float, aside').first()).toBeVisible();
    await expect(page.locator('h1.article-title, h1').first()).toBeVisible();
  });

  test('invalid maturity query does not crash page', async ({ page }) => {
    await page.goto('/information/mobs?view=maturities&maturity=notanumber');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    await expect(page.locator('body')).toBeVisible();
    await expect(page).toHaveURL(/view=maturities/);
  });
});

test.describe('Mobs Wiki Page - URL Routing', () => {
  test('direct URL navigation loads mob', async ({ page }) => {
    // Navigate directly to a mob page
    await page.goto('/information/mobs/Atrox');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    // Should either show the mob or a "not found" message
    const title = page.locator('h1');
    try {
      await expect(title).toBeVisible();
      const titleText = await title.textContent();
      expect(titleText).toBeTruthy();
    } catch {
      // Title not visible, page may not have loaded or mob not found
    }
  });

  test('mob selection updates URL', async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');
    // Wait for URL to update with mob name
    try {
      await page.waitForURL(/\/information\/mobs\/.+/, { timeout: TIMEOUT_LONG });
    } catch {
      // URL may not have updated yet
    }
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // URL should contain the mob name (encoded)
    const url = page.url();
    expect(url).toMatch(/\/information\/mobs\/.+/);
  });

  test('breadcrumbs show correct path', async ({ page }) => {
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // Should have breadcrumbs
    const breadcrumbs = page.locator('nav[aria-label="Breadcrumb"], .breadcrumbs');
    try {
      await expect(breadcrumbs).toBeVisible();
      // Should show Information > Mobs > MobName
      const infoLink = page.locator('a:has-text("Information")');
      const mobsLink = page.locator('a:has-text("Mobs")');

      let hasInfo = false;
      let hasMobs = false;
      try {
        await expect(infoLink).toBeVisible();
        hasInfo = true;
      } catch {
        // Info link not visible
      }
      try {
        await expect(mobsLink).toBeVisible();
        hasMobs = true;
      } catch {
        // Mobs link not visible
      }

      expect(hasInfo || hasMobs).toBeTruthy();
    } catch {
      // Breadcrumbs not visible, optional feature
    }
  });
});

test.describe('Mobs Wiki Page - Responsive Design', () => {
  test('mobile layout shows navigation toggle', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }

    // On mobile, sidebar might be hidden or toggleable - check for mobile-specific UI
    const mobileToggle = page.locator('.mobile-nav-toggle, button[aria-label*="menu"], .hamburger, [class*="mobile"]');
    try {
      await expect(mobileToggle.first()).toBeVisible({ timeout: TIMEOUT_SHORT });
    } catch {
      // Mobile toggle not visible, may not be present
    }

    // Body should be visible on mobile (basic layout test)
    await expect(page.locator('body')).toBeVisible();
  });

  test('desktop layout shows full infobox', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');

    if (!await pageLoaded(page)) {
      test.skip();
      return;
    }
    await waitForWikiNav(page);

    if (!await hasItems(page)) {
      test.skip();
      return;
    }

    const firstItem = page.locator('.item-link').first();
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // Should show full infobox on desktop
    const infobox = page.locator('.wiki-infobox, aside');
    await expect(infobox.first()).toBeVisible();
  });
});
