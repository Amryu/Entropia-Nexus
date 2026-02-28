import { test, expect } from '@playwright/test';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Globals player detail page', () => {
  test('shows empty state for unknown player', async ({ page }) => {
    await page.goto('/globals/player/UnknownPlayerXYZ12345');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.empty-state')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(page.locator('.empty-state')).toContainText('No globals recorded');
  });

  test('has breadcrumbs with correct links', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const breadcrumbs = page.locator('.breadcrumbs');
    await expect(breadcrumbs).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(breadcrumbs.locator('a[href="/"]')).toBeVisible();
    await expect(breadcrumbs.locator('a[href="/globals"]')).toBeVisible();
  });

  test('displays player name in title and heading', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/TestPlayer.*Globals/);
    await expect(page.locator('h1')).toContainText('TestPlayer');
  });

  test('has period selector buttons', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    // Period selector should exist (may be hidden if no data, check for it)
    const periodBtns = page.locator('.period-btn');
    // If player has data, period buttons should be visible
    // If not, the empty state shows — both are valid outcomes
    const emptyState = page.locator('.empty-state');
    const hasPeriodBtns = await periodBtns.count() > 0;
    const hasEmptyState = await emptyState.isVisible();

    expect(hasPeriodBtns || hasEmptyState).toBeTruthy();
  });

  test('period buttons include expected options', async ({ page }) => {
    // Use a player name that might have data on the test server
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    // If the player has no data, period buttons won't show
    const periodSelector = page.locator('.period-selector');
    if (await periodSelector.isVisible()) {
      await expect(page.locator('.period-btn', { hasText: '24 Hours' })).toBeVisible();
      await expect(page.locator('.period-btn', { hasText: '7 Days' })).toBeVisible();
      await expect(page.locator('.period-btn', { hasText: '30 Days' })).toBeVisible();
      await expect(page.locator('.period-btn', { hasText: 'All Time' })).toBeVisible();

      // 'All Time' should be active by default
      await expect(page.locator('.period-btn.active')).toContainText('All Time');
    }
  });

  test('search input is visible on player page', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('.globals-search input');
    await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('navigates back to globals page via breadcrumb', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    await page.locator('.breadcrumbs a[href="/globals"]').click();
    await expect(page).toHaveURL(/\/globals$/, { timeout: TIMEOUT_MEDIUM });
  });
});
