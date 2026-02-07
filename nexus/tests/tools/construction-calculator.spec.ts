import { test, expect } from '@playwright/test';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

test.describe('Construction Calculator', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/tools/construction');
  });

  test('page loads successfully', async ({ page }) => {
    await expect(page).toHaveTitle(/Construction Calculator|Entropia/i);
    await expect(page.locator('text=Construction Calculator')).toBeVisible();
  });

  test('can create a new plan', async ({ page }) => {
    // Click the New button
    await page.click('button.sidebar-btn.create:has-text("New")');

    // Verify plan input appears
    await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // The new plan should have default name
    await expect(page.locator('.plan-name-input')).toHaveValue('New Plan');
  });

  test('can add a blueprint to plan', async ({ page }) => {
    // Create new plan
    await page.click('button.sidebar-btn.create:has-text("New")');
    await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Search for a blueprint (use a common one)
    const searchInput = page.locator('.target-search input[type="text"]');
    await searchInput.fill('Basic');

    // Wait for search results and click the first one
    const searchResult = page.locator('.search-results .search-result-item').first();
    await searchResult.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
    await searchResult.click();

    // Verify the target was added
    await expect(page.locator('.targets-list .target-item-expanded')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('shows crafting steps with material refund info', async ({ page }) => {
    // Create new plan
    await page.click('button.sidebar-btn.create:has-text("New")');
    await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Search for a blueprint with multiple materials
    const searchInput = page.locator('.target-search input[type="text"]');
    await searchInput.fill('Basic');

    const searchResult = page.locator('.search-results .search-result-item').first();
    await searchResult.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
    await searchResult.click();

    // Wait for target to be added
    await expect(page.locator('.targets-list .target-item-expanded')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Switch to Steps view
    await page.click('button:has-text("Steps")');

    // Wait for steps to render
    await page.waitForTimeout(500); // Allow recalculation

    // Verify the steps view shows materials with refund information
    const stepsView = page.locator('.steps-view');
    await expect(stepsView).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Look for the materials table which shows refund info
    const materialsTable = page.locator('.materials-table');
    if (await materialsTable.isVisible()) {
      // Check that the "Exp. Refund" column exists
      await expect(page.locator('th:has-text("Exp. Refund")')).toBeVisible();

      // Check that refund percentages are displayed (should contain % somewhere)
      const refundCell = page.locator('.refund-cell').first();
      if (await refundCell.isVisible()) {
        const refundText = await refundCell.textContent();
        expect(refundText).toContain('%');
      }
    }
  });

  test('shows shopping list with estimated totals', async ({ page }) => {
    // Create new plan and add a blueprint
    await page.click('button.sidebar-btn.create:has-text("New")');
    await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const searchInput = page.locator('.target-search input[type="text"]');
    await searchInput.fill('Basic');

    const searchResult = page.locator('.search-results .search-result-item').first();
    await searchResult.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
    await searchResult.click();

    await expect(page.locator('.targets-list .target-item-expanded')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Switch to Shopping view
    await page.click('button:has-text("Shopping")');

    // Verify shopping list appears
    const shoppingView = page.locator('.shopping-view');
    await expect(shoppingView).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // The shopping list should show material entries or "No items needed" message
    const shoppingTable = page.locator('.shopping-table');
    const emptyMessage = page.locator('.shopping-view .empty');

    // One of these should be visible
    const hasContent = await shoppingTable.isVisible() || await emptyMessage.isVisible();
    expect(hasContent).toBeTruthy();
  });

  test('calculator settings panel opens and contains expected options', async ({ page }) => {
    // Click Settings button
    await page.click('button[title="Calculator Settings"]');

    // Verify the config panel opens
    const configPanel = page.locator('.config-panel');
    await expect(configPanel).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Check for expected settings
    await expect(page.locator('text=Certainty level')).toBeVisible();
    await expect(page.locator('text=Material roll chance')).toBeVisible();
    await expect(page.locator('text=Success Rates')).toBeVisible();

    // Verify the roll chance input exists and has default value
    const rollChanceInput = configPanel.locator('input.config-input').nth(1);
    await expect(rollChanceInput).toHaveValue('50');

    // Close the panel
    await page.click('.config-panel .btn-close');
    await expect(configPanel).not.toBeVisible();
  });

  test('tree view shows ownership toggles', async ({ page }) => {
    // Create new plan and add a blueprint
    await page.click('button.sidebar-btn.create:has-text("New")');
    await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const searchInput = page.locator('.target-search input[type="text"]');
    await searchInput.fill('Basic');

    const searchResult = page.locator('.search-results .search-result-item').first();
    await searchResult.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
    await searchResult.click();

    await expect(page.locator('.targets-list .target-item-expanded')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Switch to Tree view
    await page.click('button:has-text("Tree")');

    // Verify tree view appears
    const treeView = page.locator('.tree-view');
    await expect(treeView).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Tree should contain a node with the blueprint
    await expect(page.locator('.tree-node')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});
