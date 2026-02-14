import { test, expect } from '@playwright/test';
import { TIMEOUT_LONG, TIMEOUT_MEDIUM } from '../test-constants';

const API_BASE = 'http://dev.entropianexus.com:3100';

test.describe('Wiki Enumerations', () => {
  test('page loads and sidebar lists enumerations', async ({ page }) => {
    await page.goto('/information/enumerations');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.wiki-page')).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    const itemCount = page.locator('.wiki-nav .item-count');
    await expect(itemCount).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('built-in entry shows populated table and no infobox', async ({ page }) => {
    await page.goto('/information/enumerations/MobSpecies');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.wiki-infobox-float')).toHaveCount(0);
    await expect(page.locator('.fancy-table-container')).toBeVisible({ timeout: TIMEOUT_LONG });

    const visibleRows = page.locator('.fancy-table-container .table-row');
    await expect(visibleRows.first()).toBeVisible({ timeout: TIMEOUT_LONG });
  });

  test('custom entry (if present) shows Name + data columns without Value/metadata blocks', async ({ page, request }) => {
    const res = await request.get(`${API_BASE}/enumerations`);
    expect(res.ok()).toBeTruthy();

    const list = await res.json();
    const custom = (list || []).find((x) => x?.Properties?.Source === 'custom');
    if (!custom) {
      test.skip();
      return;
    }

    await page.goto(`/information/enumerations/${encodeURIComponent(custom.Name)}`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.article-title')).toContainText(custom.Name);
    await expect(page.locator('.table-section h2')).toContainText('Values');

    const nameHeader = page.locator('.fancy-table-container .header-cell:has-text("Name")').first();
    const valueHeader = page.locator('.fancy-table-container .header-cell:has-text("Value")');
    const headers = page.locator('.fancy-table-container .header-cell');
    await expect(nameHeader).toBeVisible();
    await expect(headers.first()).toBeVisible();
    expect(await headers.count()).toBeGreaterThan(0);
    await expect(valueHeader).toHaveCount(0);
    await expect(page.locator('.metadata-block')).toHaveCount(0);
  });

  test('linkable cells navigate to entity pages when refs exist', async ({ page }) => {
    await page.goto('/information/enumerations/Planets');
    await page.waitForLoadState('networkidle');

    const firstLink = page.locator('.fancy-table-container a.enum-link').first();
    if (await firstLink.count() === 0) {
      test.skip();
      return;
    }

    await firstLink.click();
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveURL(/\/maps\//);
  });

  test('non-linkable Effects cells render as plain text', async ({ page }) => {
    await page.goto('/information/enumerations/Effects');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('.fancy-table-container .table-row');
    if (await rows.count() === 0) {
      test.skip();
      return;
    }

    await expect(page.locator('.fancy-table-container a.enum-link')).toHaveCount(0);
  });

  test('API: list includes built-ins, detail resolves, unknown returns 404', async ({ request }) => {
    const listRes = await request.get(`${API_BASE}/enumerations`);
    expect(listRes.ok()).toBeTruthy();
    const list = await listRes.json();

    const names = new Set((list || []).map((x) => x?.Name));
    expect(names.has('MobLoots')).toBeTruthy();
    expect(names.has('Planets')).toBeTruthy();

    const detailRes = await request.get(`${API_BASE}/enumerations/MobLoots`);
    expect(detailRes.ok()).toBeTruthy();
    const detail = await detailRes.json();
    expect(detail?.Name).toBe('MobLoots');
    expect(Array.isArray(detail?.Table?.Rows)).toBeTruthy();

    const notFoundRes = await request.get(`${API_BASE}/enumerations/DoesNotExist`);
    expect(notFoundRes.status()).toBe(404);
  });
});
