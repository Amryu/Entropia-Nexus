import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_LONG } from '../test-constants';

// ─── EquipmentEditor (Create Page, Verified User) ───────────────

test.describe('EquipmentEditor - Healing Type', () => {
  test('equipment section appears for healing type', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('healing');
    await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

    const equipmentSection = verifiedUser.locator('[class*="equipment"]').or(
      verifiedUser.locator('text=Equipment')
    );
    await expect(equipmentSection.first()).toBeVisible({ timeout: TIMEOUT_LONG });
  });
});

test.describe('EquipmentEditor - DPS Type', () => {
  test('equipment section appears for DPS type', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('dps');
    await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

    const equipmentSection = verifiedUser.locator('[class*="equipment"]').or(
      verifiedUser.locator('text=Equipment')
    );
    await expect(equipmentSection.first()).toBeVisible({ timeout: TIMEOUT_LONG });
  });
});

test.describe('EquipmentEditor - Transportation Type', () => {
  test('transportation shows transport details instead of equipment', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('transportation');
    await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

    // Transportation has specific fields, not generic equipment editor
    const transportTypeSelect = verifiedUser.locator('select#transportationType').or(
      verifiedUser.getByLabel(/transportation type/i)
    );
    await expect(transportTypeSelect).toBeVisible({ timeout: TIMEOUT_LONG });
  });
});

// ─── FancyTable Structure (Public List View) ────────────────────

test.describe('FancyTable Structure', () => {
  test('table has header row with header-cell elements', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    const headerRow = page.locator('.header-row');
    await expect(headerRow).toBeVisible();

    const headerCells = page.locator('.header-cell');
    const count = await headerCells.count();
    expect(count).toBeGreaterThan(0);
  });

  test('table has body section for data', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    const tableBody = page.locator('.table-body');
    await expect(tableBody).toBeVisible();
  });

  test('sortable headers show sort indicator on click', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    const sortableHeader = page.locator('.header-cell.sortable').first();
    if (await sortableHeader.isVisible().catch(() => false)) {
      await sortableHeader.click();

      const sortIndicator = page.locator('.sort-indicator');
      await expect(sortIndicator).toBeVisible();
    }
  });

  test('fancy-table-container wraps the table', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.fancy-table-container')).toBeVisible();
  });
});

// ─── CSS Theming (Public) ───────────────────────────────────────

test.describe('CSS Theming - List View', () => {
  test('active tab button has visible background', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    const activeTab = page.locator('.tab-btn.active');
    await expect(activeTab).toBeVisible();

    const bgColor = await activeTab.evaluate(el =>
      getComputedStyle(el).backgroundColor
    );
    expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
  });
});

test.describe('CSS Theming - Create Form', () => {
  test('form inputs have proper contrast', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const input = verifiedUser.locator('input#title');
    await expect(input).toBeVisible();

    const bgColor = await input.evaluate(el => getComputedStyle(el).backgroundColor);
    const color = await input.evaluate(el => getComputedStyle(el).color);

    expect(color).not.toBe(bgColor);
  });

  test('select dropdowns have proper contrast', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const select = verifiedUser.locator('select#serviceType');
    await expect(select).toBeVisible();

    const bgColor = await select.evaluate(el => getComputedStyle(el).backgroundColor);
    const color = await select.evaluate(el => getComputedStyle(el).color);

    expect(color).not.toBe(bgColor);
  });
});

// ─── My Services Dashboard (Verified User) ──────────────────────

test.describe('My Services Dashboard', () => {
  test('verified user can access my services page', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/my');
    await verifiedUser.waitForLoadState('networkidle');

    const currentUrl = verifiedUser.url();
    expect(currentUrl).not.toContain('discord');
    expect(currentUrl).toContain('/market/services/my');
  });

  test('my services page has heading', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/my');
    await verifiedUser.waitForLoadState('networkidle');

    const heading = verifiedUser.locator('h1');
    await expect(heading).toBeVisible();
  });

  test('my services page redirects unauthenticated users', async ({ page }) => {
    await page.goto('/market/services/my');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize') ||
      currentUrl.includes('discord.com/login');
    expect(inAuthFlow).toBeTruthy();
  });
});
