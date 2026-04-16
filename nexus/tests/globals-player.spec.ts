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

  test('has date range picker with period buttons', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    const picker = page.locator('.date-range-picker');
    await expect(picker).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(picker.locator('.period-btn', { hasText: '24 Hours' })).toBeVisible();
    await expect(picker.locator('.period-btn', { hasText: '90 Days' })).toBeVisible();
    await expect(picker.locator('.period-btn', { hasText: 'All Time' })).toBeVisible();
    await expect(picker.locator('.period-btn', { hasText: 'Custom' })).toBeVisible();
    await expect(picker.locator('.period-btn.active')).toContainText('90 Days');
  });

  test('shows category breakdown cards', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    const categoryRow = page.locator('.category-row');
    await expect(categoryRow).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(categoryRow.locator('.stat-label', { hasText: 'Hunting' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Mining' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Crafting' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Fishing' })).toBeVisible();
  });

  test('category cards are clickable and switch to category tab', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Click Hunting category card
    await page.locator('.category-card', { hasText: 'Hunting' }).click();
    await expect(page.locator('.tab-link.active')).toContainText('Hunting');
  });

  test('shows tab navigation with Overview active', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    const tabNav = page.locator('.player-tab-nav');
    await expect(tabNav).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(tabNav.locator('.tab-link', { hasText: 'Overview' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Hunting' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Mining' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Crafting' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'ATHs' })).toBeVisible();
    await expect(tabNav.locator('.tab-link.active')).toContainText('Overview');
  });

  test('shows avg value and highest loot stat cards', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    await expect(page.locator('.stat-label', { hasText: 'Avg Value' })).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(page.locator('.stat-label', { hasText: 'Highest Loot' })).toBeVisible();
  });

  test('ATHs tab shows category toggle with all categories', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Switch to ATHs tab
    await page.locator('.tab-link', { hasText: 'ATHs' }).click();
    await expect(page.locator('.tab-link.active')).toContainText('ATHs');

    // Should have "Top 10 Rankings" heading
    await expect(page.locator('h2', { hasText: 'Top 10 Rankings' })).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Should have category sort toggle with all four categories
    const sortToggle = page.locator('.sort-toggle');
    await expect(sortToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(sortToggle.locator('.sort-btn', { hasText: 'Hunting' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'Mining' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'Crafting' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'PvP' })).toBeVisible();
  });

  test('search input is visible on player page', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('.globals-search input');
    await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('search navigates to player page on Enter', async ({ page }) => {
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('.globals-search input');
    await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await searchInput.fill('SomePlayerName');
    await searchInput.press('Enter');
    await expect(page).toHaveURL(/\/globals\/player\/SomePlayerName/, { timeout: TIMEOUT_MEDIUM });
  });

  test('overview tab shows rare finds and discoveries sections even when empty', async ({ page }) => {
    // Use a player unlikely to have rare finds/discoveries
    await page.goto('/globals/player/UnknownPlayerXYZ12345');
    await page.waitForLoadState('networkidle');

    // For unknown player, the empty state kicks in — so test with a real player instead
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Both section cards should always be visible in overview
    const specials = page.locator('.overview-specials');
    await expect(specials).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(specials.locator('h2', { hasText: 'Recent Rare Finds' })).toBeVisible();
    await expect(specials.locator('h2', { hasText: 'Recent Discoveries' })).toBeVisible();
  });

  test('hunting tab shows side-by-side tables with pagination', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Switch to Hunting tab
    await page.locator('.tab-link', { hasText: 'Hunting' }).click();
    await expect(page.locator('.tab-link.active')).toContainText('Hunting');

    // Should have side-by-side layout
    const sideBySide = page.locator('.tab-side-by-side');
    await expect(sideBySide).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Should have section titles with SVG icons
    await expect(sideBySide.locator('.section-title-icon').first()).toBeVisible();
  });

  test('ATHs tab auto-selects category and shows ranking tables or empty state', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Switch to ATHs tab
    await page.locator('.tab-link', { hasText: 'ATHs' }).click();
    await expect(page.locator('.tab-link.active')).toContainText('ATHs');

    // Should have category toggle with one active button
    const sortToggle = page.locator('.sort-toggle');
    await expect(sortToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(sortToggle.locator('.sort-btn.active')).toHaveCount(1);

    // Should show either ranking tables with rank badges, or empty state
    const sectionCard = page.locator('.section-card').filter({ has: page.locator('h2', { hasText: 'Top 10 Rankings' }) });
    await expect(sectionCard).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    const hasRankings = await page.locator('.rank-badge').count() > 0;
    const hasEmpty = await page.locator('.empty-state-sm').count() > 0;
    expect(hasRankings || hasEmpty).toBeTruthy();
  });

  test('navigates back to globals page via breadcrumb', async ({ page }) => {
    await page.goto('/globals/player/TestPlayer');
    await page.waitForLoadState('networkidle');

    await page.locator('.breadcrumbs a[href="/globals"]').click();
    await expect(page).toHaveURL(/\/globals$/, { timeout: TIMEOUT_MEDIUM });
  });
});
