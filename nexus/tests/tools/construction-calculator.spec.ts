import { test, expect } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

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

  test('shopping list table has rounded borders', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();

    const shoppingTable = page.locator('.shopping-table.unified');
    await expect(shoppingTable).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Verify the table uses border-collapse: separate (required for border-radius)
    const borderCollapse = await shoppingTable.evaluate(el => getComputedStyle(el).borderCollapse);
    expect(borderCollapse).toBe('separate');
  });

  test('shopping list shows Order and Buy buttons on desktop', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();

    const shoppingTable = page.locator('.shopping-table');
    await expect(shoppingTable).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Check that action buttons exist (Buy button should always show, Order only for logged-in)
    const buyBtn = page.locator('.btn-shop-action.btn-buy').first();
    await expect(buyBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(buyBtn).toHaveText(/^Buy/);

    // Verify the Buy button links to exchange listings
    const href = await buyBtn.getAttribute('href');
    expect(href).toContain('/market/exchange/listings/');
  });

  test('shopping list action buttons hidden on mobile', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();
    await expect(page.locator('.shopping-table')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Resize to mobile viewport
    await page.setViewportSize({ width: 600, height: 800 });
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Action columns should be hidden on mobile
    const actionCols = page.locator('.col-actions.hide-mobile');
    const count = await actionCols.count();
    if (count > 0) {
      const isVisible = await actionCols.first().isVisible();
      expect(isVisible).toBe(false);
    }
  });

  test('shopping list MU% input accepts custom markup', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();
    await expect(page.locator('.shopping-table')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Find a markup input and change its value
    const markupInput = page.locator('.shopping-table .markup-input-inline').first();
    await expect(markupInput).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Set a custom value and dispatch a native change event
    await markupInput.evaluate(el => {
      (el as HTMLInputElement).value = '150';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(TIMEOUT_SHORT);

    // The input should now have the is-custom class
    await expect(markupInput).toHaveClass(/is-custom/);

    // A reset button should appear
    const resetBtn = page.locator('.shopping-table .markup-reset').first();
    await expect(resetBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('markup reset button clears custom value', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();
    await expect(page.locator('.shopping-table')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const markupInput = page.locator('.shopping-table .markup-input-inline').first();
    await expect(markupInput).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Set a custom value and dispatch a native change event
    await markupInput.evaluate(el => {
      (el as HTMLInputElement).value = '200';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(TIMEOUT_SHORT);

    // Click the reset button
    const resetBtn = page.locator('.shopping-table .markup-reset').first();
    await expect(resetBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    await resetBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // The is-custom class should be removed
    await expect(markupInput).not.toHaveClass(/is-custom/);
  });

  test('shopping list checkboxes toggle items', async ({ page }) => {
    await createNewPlan(page);
    await addBlueprintToPlan(page);

    await page.getByRole('button', { name: 'Shopping' }).click();
    await expect(page.locator('.shopping-table')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Find a checkbox in the shopping list
    const checkbox = page.locator('.shopping-table .col-check input[type="checkbox"]').first();
    await expect(checkbox).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Click to check it
    await checkbox.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // The row should get the checked class (strikethrough styling)
    const row = page.locator('.shopping-table tbody tr').first();
    await expect(row).toHaveClass(/checked/);

    // Click again to uncheck
    await checkbox.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await expect(row).not.toHaveClass(/checked/);
  });
});
