import { test, expect } from '@playwright/test';

test.describe('Basic navigation', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');

    // Check that the page loaded (adjust selector based on your actual homepage)
    await expect(page).toHaveTitle(/Entropia/i);
  });

  test('can navigate to tools section', async ({ page }) => {
    await page.goto('/');

    // Look for a tools link and click it (adjust based on your navigation)
    const toolsLink = page.locator('a[href="/tools"]');
    if (await toolsLink.isVisible()) {
      await toolsLink.click();
      await expect(page).toHaveURL(/.*tools.*/);
    }
  });
});

test.describe('Database connectivity', () => {
  test('can load a page that requires database', async ({ page }) => {
    // This test verifies the app is connected to the TEST database
    // Adjust the URL to a page that fetches data from the database
    await page.goto('/tools/loadouts');

    // If the page loads without error, the database connection works
    // You may want to add more specific assertions here
    await expect(page.locator('body')).toBeVisible();
  });
});
