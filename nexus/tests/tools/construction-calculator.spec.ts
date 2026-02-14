import { test, expect } from '@playwright/test';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

async function createNewPlan(page) {
  // Wait for page to fully load (blueprints, local data, etc.)
  await page.waitForLoadState('networkidle');

  // Wait for the empty state or plan editor to appear (confirms loading finished)
  await page.locator('.empty-state, .mobile-empty-state, .plan-editor').first()
    .waitFor({ state: 'visible', timeout: TIMEOUT_LONG });

  // Click the "New" button - use role selector for reliability
  const newBtn = page.getByRole('button', { name: 'New', exact: true });
  const newPlanBtn = page.getByRole('button', { name: 'New Plan', exact: true });

  if (await newBtn.isVisible()) {
    await newBtn.click();
  } else {
    await newPlanBtn.click();
  }

  // Wait for the plan editor to appear with the name input
  await expect(page.locator('.plan-name-input')).toBeVisible({ timeout: TIMEOUT_LONG });
}

async function addBlueprintToPlan(page, query = 'Basic') {
  const searchInput = page.getByPlaceholder('Add blueprint...');
  await searchInput.fill(query);

  const firstResult = page.locator('.search-dropdown .search-result').first();
  await firstResult.waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
  await firstResult.click();

  await expect(page.locator('.targets-list .target-item-expanded')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
}

test.describe('Construction Calculator', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/tools/construction');
  });

  test('page loads successfully', async ({ page }) => {
    await expect(page).toHaveTitle(/Construction Calculator|Entropia/i);
    await expect(page.getByRole('link', { name: 'Construction Calculator' })).toBeVisible();
  });

  test('can create a new plan', async ({ page }) => {
    await createNewPlan(page);

    // The new plan should have default name
    await expect(page.locator('.plan-name-input')).toHaveValue('New Plan');
  });

  test('can add a blueprint to plan', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);
  });

  test('shows crafting steps with material refund info', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    // Switch to Steps view
    await page.getByRole('button', { name: 'Steps' }).click();

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
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    // Switch to Shopping view
    await page.getByRole('button', { name: 'Shopping' }).click();

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
    // Wait for page to fully load before interacting
    await page.waitForLoadState('networkidle');
    await page.locator('.empty-state, .mobile-empty-state, .plan-editor').first()
      .waitFor({ state: 'visible', timeout: TIMEOUT_LONG });

    // Click Settings button
    await page.getByRole('button', { name: 'Settings' }).click();

    // Verify the config panel opens
    const configPanel = page.locator('.config-panel');
    await expect(configPanel).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.getByRole('heading', { name: 'Calculator Settings' })).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Check for expected settings
    await expect(page.locator('text=Certainty level')).toBeVisible();
    await expect(page.locator('text=Material roll chance')).toBeVisible();
    await expect(page.locator('text=Success Rates')).toBeVisible();

    // Verify the certainty level input has default value of 50%
    const certaintyInput = configPanel.locator('input.config-input').nth(0);
    await expect(certaintyInput).toHaveValue('50');

    // Verify the material roll chance input has default value of 80%
    const rollChanceInput = configPanel.locator('input.config-input').nth(1);
    await expect(rollChanceInput).toHaveValue('80');

    // Close the panel
    await page.click('.config-panel .btn-close');
    await expect(configPanel).not.toBeVisible();
  });

  test('tree view shows ownership toggles', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    // Switch to Tree view
    await page.getByRole('button', { name: 'Tree' }).click();

    // Verify tree view appears
    const treeView = page.locator('.tree-view');
    await expect(treeView).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Tree should contain a node with the blueprint
    await expect(page.locator('.tree-node')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});
