import { test, expect } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

test.describe('Loadout Amplifier Picker', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/tools/loadouts');
    await page.waitForLoadState('networkidle');

    // Wait for entities to load (weapon button becomes enabled once data is ready)
    const weaponBtn = page.locator('.form-label:has-text("Weapon") + .control-row .select-button');
    await weaponBtn.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
  });

  async function selectWeapon(page, query: string) {
    const weaponBtn = page.locator('.form-label:has-text("Weapon") + .control-row .select-button');
    await weaponBtn.click();

    const dialog = page.locator('.picker-dialog');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Search for the weapon via FancyTable's filter row
    const searchInput = dialog.locator('.filter-input').first();
    await searchInput.fill(query);
    await page.waitForTimeout(TIMEOUT_SHORT);

    // Click the first matching row (FancyTable uses div.table-row)
    const firstRow = dialog.locator('.table-row').first();
    await firstRow.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
  }

  async function openAmplifierPicker(page) {
    const ampBtn = page.locator('.form-label:has-text("Amplifier") + .control-row .select-button');
    await ampBtn.click();

    const dialog = page.locator('.picker-dialog');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    return dialog;
  }

  test('amplifier picker has Overamp column', async ({ page }) => {
    await selectWeapon(page, 'Arsonistic');

    const dialog = await openAmplifierPicker(page);

    // FancyTable uses div.header-cell, not th. Header text is "Over %" or "Over Δ"
    const overampHeader = dialog.locator('.header-cell:has-text("Over")');
    await expect(overampHeader).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('amplifier picker has Hide overcapped checkbox in header', async ({ page }) => {
    await selectWeapon(page, 'Arsonistic');

    const dialog = await openAmplifierPicker(page);

    const checkbox = dialog.locator('.picker-header-checkbox input[type="checkbox"]');
    await expect(checkbox).toBeVisible({ timeout: TIMEOUT_SHORT });
    await expect(checkbox).toBeChecked();
  });

  test('Hide overcapped checkbox filters amplifiers', async ({ page }) => {
    await selectWeapon(page, 'Arsonistic');

    const dialog = await openAmplifierPicker(page);

    // Count rows with filter on
    const rowsFiltered = await dialog.locator('.table-row:not(.empty)').count();

    // Uncheck "Hide overcapped"
    const checkbox = dialog.locator('.picker-header-checkbox input[type="checkbox"]');
    await checkbox.uncheck();
    await page.waitForTimeout(TIMEOUT_SHORT);

    // Should show more (or equal) rows with the filter off
    const rowsUnfiltered = await dialog.locator('.table-row:not(.empty)').count();
    expect(rowsUnfiltered).toBeGreaterThanOrEqual(rowsFiltered);
  });

  test('overcapped amplifiers show warning/danger colors', async ({ page }) => {
    await selectWeapon(page, 'Arsonistic');

    const dialog = await openAmplifierPicker(page);

    // Uncheck to show overcapped amps
    const checkbox = dialog.locator('.picker-header-checkbox input[type="checkbox"]');
    await checkbox.uncheck();
    await page.waitForTimeout(TIMEOUT_SHORT);

    // Check that at least one row has the overamp-warn or overamp-danger class
    const warnRows = dialog.locator('.table-row.overamp-warn');
    const dangerRows = dialog.locator('.table-row.overamp-danger');
    const totalHighlighted = await warnRows.count() + await dangerRows.count();
    expect(totalHighlighted).toBeGreaterThan(0);
  });

  test('overamp settings removed from settings panel', async ({ page }) => {
    // The old "Include overcapped amplifiers up to" checkbox should not exist
    const oldCheckboxLabel = page.locator('text=Include overcapped amplifiers up to');
    await expect(oldCheckboxLabel).not.toBeVisible({ timeout: TIMEOUT_SHORT });
  });
});
