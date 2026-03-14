import { test, expect } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

test.describe('Loadout Healing - Medical Chips', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/tools/loadouts');
    await page.waitForLoadState('networkidle');

    // Wait for entities to load
    const weaponBtn = page.locator('.form-label:has-text("Weapon") + .control-row .select-button');
    await weaponBtn.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
  });

  /** Click the healing tab to make it active. */
  async function openHealingTab(page: import('@playwright/test').Page) {
    const tab = page.locator('.tab-item:has-text("Healing")');
    await tab.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
  }

  /** Open the healing item picker dialog. */
  async function openHealingPicker(page: import('@playwright/test').Page) {
    const btn = page.locator('.form-label:has-text("Healing Tool / Chip") + .control-row .select-button');
    await btn.click();
    const dialog = page.locator('.picker-dialog');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    return dialog;
  }

  /** Select a healing item by searching and clicking first match. */
  async function selectHealingItem(page: import('@playwright/test').Page, query: string) {
    const dialog = await openHealingPicker(page);
    const searchInput = dialog.locator('.filter-input').first();
    await searchInput.fill(query);
    await page.waitForTimeout(TIMEOUT_SHORT);
    const firstRow = dialog.locator('.table-row').first();
    await firstRow.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
  }

  test('healing picker shows both tools and chips with Type column', async ({ page }) => {
    await openHealingTab(page);
    const dialog = await openHealingPicker(page);

    // Should have a "Type" column header
    const typeHeader = dialog.locator('.header-cell:has-text("Type")');
    await expect(typeHeader).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should have rows with "Tool" and "Chip" type values
    const toolRows = dialog.locator('.table-row:has-text("Tool")');
    const chipRows = dialog.locator('.table-row:has-text("Chip")');
    expect(await toolRows.count()).toBeGreaterThan(0);
    expect(await chipRows.count()).toBeGreaterThan(0);

    // Close dialog
    await page.keyboard.press('Escape');
  });

  test('enhancers are disabled when a medical chip is selected', async ({ page }) => {
    await openHealingTab(page);

    // Select a medical chip (search for "Heal" to find chips — they typically have (Chip) in context)
    const dialog = await openHealingPicker(page);

    // Filter for chips using the Type column
    const typeFilter = dialog.locator('.filter-input').nth(1); // Type column filter
    await typeFilter.fill('Chip');
    await page.waitForTimeout(TIMEOUT_SHORT);

    // Select the first chip
    const firstChip = dialog.locator('.table-row').first();
    await firstChip.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Check that enhancer inputs are disabled
    const enhancerInputs = page.locator('.disabled-panel .enhancer-grid input');
    const count = await enhancerInputs.count();
    expect(count).toBeGreaterThan(0);
  });

  test('enhancers re-enable when switching from chip to tool', async ({ page }) => {
    await openHealingTab(page);

    // First select a chip
    let dialog = await openHealingPicker(page);
    const typeFilter = dialog.locator('.filter-input').nth(1);
    await typeFilter.fill('Chip');
    await page.waitForTimeout(TIMEOUT_SHORT);
    await dialog.locator('.table-row').first().click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Verify disabled
    let disabledPanel = page.locator('.disabled-panel .enhancer-grid');
    await expect(disabledPanel).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Now select a tool
    dialog = await openHealingPicker(page);
    const typeFilter2 = dialog.locator('.filter-input').nth(1);
    await typeFilter2.fill('Tool');
    await page.waitForTimeout(TIMEOUT_SHORT);
    await dialog.locator('.table-row').first().click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Enhancers should not be in disabled panel anymore
    disabledPanel = page.locator('.disabled-panel .enhancer-grid');
    await expect(disabledPanel).not.toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('picker title says Select Healing Item', async ({ page }) => {
    await openHealingTab(page);
    const dialog = await openHealingPicker(page);

    const title = dialog.locator('.picker-title, h2, h3').first();
    await expect(title).toContainText('Healing Item', { timeout: TIMEOUT_SHORT });

    await page.keyboard.press('Escape');
  });

  test('chip with cooldown shows cooldown as reload time', async ({ page }) => {
    await openHealingTab(page);

    // Select a chip with a known cooldown (e.g., "Divine Intervention Chip" has 5s cooldown)
    await selectHealingItem(page, 'Divine Intervention');

    // Check that Reload stat shows the cooldown value
    const reloadStat = page.locator('.stat-row:has-text("Reload")').filter({ hasText: /\ds/ }).first();
    await expect(reloadStat).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(reloadStat).toContainText('5.00s');
  });

  test('chip with HoT effect shows instant and HoT heal breakdown', async ({ page }) => {
    await openHealingTab(page);

    // Select a HoT chip (e.g., "Restoration Chip 9" has 95% HoT)
    await selectHealingItem(page, 'Restoration Chip 9');

    // Should show Instant Heal and HoT Heal rows
    const instantHeal = page.locator('.stat-row:has-text("Instant Heal")');
    await expect(instantHeal).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const hotHeal = page.locator('.stat-row:has-text("HoT Heal")');
    await expect(hotHeal).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should show HoT HPS
    const hotHPS = page.locator('.stat-row:has-text("HoT HPS")');
    await expect(hotHPS).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('regular medical tool does not show HoT breakdown', async ({ page }) => {
    await openHealingTab(page);

    // Select a regular tool (filter for "Tool" type)
    const dialog = await openHealingPicker(page);
    const typeFilter = dialog.locator('.filter-input').nth(1);
    await typeFilter.fill('Tool');
    await page.waitForTimeout(TIMEOUT_SHORT);
    await dialog.locator('.table-row').first().click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should NOT show Instant Heal or HoT Heal rows
    const instantHeal = page.locator('.stat-row:has-text("Instant Heal")');
    await expect(instantHeal).not.toBeVisible({ timeout: TIMEOUT_SHORT });

    const hotHPS = page.locator('.stat-row:has-text("HoT HPS")');
    await expect(hotHPS).not.toBeVisible({ timeout: TIMEOUT_SHORT });
  });
});
