import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

async function waitForMobsPage(page: import('@playwright/test').Page) {
  await page.goto('/information/mobs');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.wiki-page').first()).toBeVisible({ timeout: TIMEOUT_LONG });
}

test.describe('Mobs Wiki Species Dialog', () => {
  test('persists codex values while editing species', async ({ verifiedUser: page }) => {
    await waitForMobsPage(page);

    const items = page.locator('.item-link');
    if (await items.count() === 0) {
      test.skip();
      return;
    }

    await items.first().click();
    await page.waitForLoadState('networkidle');

    const editButton = page.locator('button:has-text("Edit")').first();
    await expect(editButton).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await editButton.click();

    await expect(page.locator('.edit-action-bar')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const newSpeciesButton = page.locator('.species-edit-row .btn-create-inline:has-text("New")');
    await expect(newSpeciesButton).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await newSpeciesButton.click();

    const uniqueName = `E2E Species ${Date.now()}`;
    await page.locator('#species-name').fill(uniqueName);
    await page.locator('#species-codex-cost').fill('123.45');
    await page.locator('#species-codex-type').selectOption('MobLooter');
    await page.locator('.modal .btn-create:has-text("Create")').click();

    const codexSection = page.locator('.stats-section').filter({ has: page.locator('h4.section-title:has-text("Codex")') }).first();
    await expect(codexSection).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(codexSection.locator('.stat-row:has(.stat-label:has-text("Base Cost")) .stat-value')).toContainText('123.45');
    await expect(codexSection.locator('.stat-row:has(.stat-label:has-text("Type")) .stat-value')).toContainText('MobLooter');

    const editSpeciesButton = page.locator('.species-edit-row .btn-create-inline:has-text("Edit")');
    await expect(editSpeciesButton).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await editSpeciesButton.click();

    await expect(page.locator('#species-name')).toHaveValue(uniqueName);
    await expect(page.locator('#species-codex-cost')).toHaveValue('123.45');
    await expect(page.locator('#species-codex-type')).toHaveValue('MobLooter');

    await page.locator('#species-codex-cost').fill('222.5');
    await page.locator('#species-codex-type').selectOption('Asteroid');
    await page.locator('.modal .btn-create:has-text("Save")').click();

    await page.waitForTimeout(TIMEOUT_INSTANT);
    await expect(codexSection.locator('.stat-row:has(.stat-label:has-text("Base Cost")) .stat-value')).toContainText('222.5');
    await expect(codexSection.locator('.stat-row:has(.stat-label:has-text("Type")) .stat-value')).toContainText('Asteroid');
  });
});
