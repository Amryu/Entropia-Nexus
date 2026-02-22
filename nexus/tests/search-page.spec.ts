import { test, expect } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Search page', () => {
  test('navigates to search page when pressing Enter in menu search bar without arrow keys', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('.search-container input[type="text"]');
    await searchInput.fill('opalo');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    await searchInput.press('Enter');
    await expect(page).toHaveURL(/\/search\?q=opalo/, { timeout: TIMEOUT_MEDIUM });
  });

  test('navigates to item page when using arrow keys then Enter', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('.search-container input[type="text"]');
    await searchInput.fill('opalo');

    // Wait for results to appear
    await expect(page.locator('.search-results-container')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Arrow down to first result, then Enter
    await searchInput.press('ArrowDown');
    await searchInput.press('Enter');

    // Should navigate to an item page, NOT the search page
    await expect(page).not.toHaveURL(/\/search\?q=/, { timeout: TIMEOUT_MEDIUM });
  });

  test('loads search page with query parameter and shows results', async ({ page }) => {
    await page.goto('/search?q=opalo');
    await page.waitForLoadState('networkidle');

    // Should show results summary
    await expect(page.locator('.search-summary')).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.locator('.search-summary')).toContainText('result');

    // Should have at least one group section
    await expect(page.locator('.search-group').first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Group header should be visible
    await expect(page.locator('.group-header').first()).toBeVisible();
  });

  test('shows grouped results with tables', async ({ page }) => {
    await page.goto('/search?q=opalo');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-group').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    // Should have a table with columns
    const table = page.locator('.search-table').first();
    await expect(table).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Table should have header row
    const headerCells = table.locator('thead th');
    const headerCount = await headerCells.count();
    expect(headerCount).toBeGreaterThanOrEqual(2); // Name + at least 1 column

    // First header should be Name
    await expect(headerCells.first()).toContainText('Name');

    // Should have result rows
    const rows = table.locator('tbody tr');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test('updates URL and results when typing in search page input', async ({ page }) => {
    await page.goto('/search?q=opalo');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-group').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    // Change the search query
    const searchInput = page.locator('.search-page .search-input');
    await searchInput.clear();
    await searchInput.fill('herman');

    // Wait for debounce and URL update
    await expect(page).toHaveURL(/\/search\?q=herman/, { timeout: TIMEOUT_MEDIUM });

    // Results should update
    await expect(page.locator('.search-summary')).toContainText('result', { timeout: TIMEOUT_LONG });
  });

  test('collapses and expands group sections', async ({ page }) => {
    await page.goto('/search?q=opalo');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-group').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    const firstGroupHeader = page.locator('.group-header').first();
    const firstGroupContent = page.locator('.group-content').first();

    // Content should be visible initially
    await expect(firstGroupContent).toBeVisible();

    // Click to collapse
    await firstGroupHeader.click();
    await expect(firstGroupContent).not.toBeVisible({ timeout: TIMEOUT_INSTANT });

    // Click to expand
    await firstGroupHeader.click();
    await expect(firstGroupContent).toBeVisible({ timeout: TIMEOUT_INSTANT });
  });

  test('shows prompt message when no query', async ({ page }) => {
    await page.goto('/search');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-empty')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(page.locator('.search-empty')).toContainText('Start typing');
  });

  test('shows no results message for gibberish query', async ({ page }) => {
    await page.goto('/search?q=zzzxxxyyyqqq');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-empty')).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.locator('.search-empty')).toContainText('No results found');
  });

  test('result names are clickable links', async ({ page }) => {
    await page.goto('/search?q=opalo');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.search-table').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    // First result name should be a link
    const firstLink = page.locator('.search-table tbody td.col-name a').first();
    await expect(firstLink).toBeVisible();

    const href = await firstLink.getAttribute('href');
    expect(href).toBeTruthy();
    expect(href).not.toContain('/search');
  });
});
