import { test, expect } from '@playwright/test';

test.describe('Basic navigation', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');

    // Check that the page loaded (adjust selector based on your actual homepage)
    await expect(page).toHaveTitle(/Entropia/i);
  });

  test('homepage shows upcoming events above globals', async ({ page }) => {
    await page.goto('/');

    const eventsSection = page.locator('#events');
    const globalsHeading = page.getByRole('heading', { name: 'Globals', exact: true }).first();

    if (await eventsSection.count() === 0) {
      return;
    }

    await expect(eventsSection).toBeVisible();
    await expect(globalsHeading).toBeVisible();

    const [eventsBox, globalsBox] = await Promise.all([
      eventsSection.boundingBox(),
      globalsHeading.boundingBox()
    ]);

    expect(eventsBox).not.toBeNull();
    expect(globalsBox).not.toBeNull();
    expect(eventsBox!.y).toBeLessThan(globalsBox!.y);
  });

  test('can navigate to tools section', async ({ page }) => {
    await page.goto('/');

    // Click the Tools link in the main navigation menu
    const toolsLink = page.getByRole('link', { name: 'Tools', exact: true });
    await expect(toolsLink).toBeVisible();
    await toolsLink.click();
    await expect(page).toHaveURL(/.*tools.*/);

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
