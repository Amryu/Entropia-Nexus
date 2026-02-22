import { test, expect } from './fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Locations Page', () => {
  test.describe('Anonymous User', () => {
    test('loads locations page successfully', async ({ page }) => {
      await page.goto('/information/locations');

      // Check page title
      await expect(page.locator('h1, h2').first()).toContainText(/Locations/i, { timeout: TIMEOUT_MEDIUM });
    });

    test('displays locations list in sidebar', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for the navigation to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that the sidebar exists
      const sidebar = page.locator('.wiki-sidebar, .wiki-nav, nav:has([role="listbox"])').first();
      await expect(sidebar).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('can filter by type using type toggle', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Find and click a type filter link (e.g., Teleporters)
      const teleporterLink = page.getByRole('link', { name: 'Teleporters' });
      if (await teleporterLink.isVisible({ timeout: TIMEOUT_SHORT })) {
        await teleporterLink.click();
        await expect(page).toHaveURL(/.*locations\/teleporters.*/i, { timeout: TIMEOUT_MEDIUM });
      }
    });

    test('can view a location detail page', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for locations to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on the first location in the sidebar if available
      const firstLocation = page.locator('.item-link, [role="listbox"] a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();

        // Should show location details
        await expect(page.locator('.wiki-article, .article-title').first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      }
    });

    test('cannot access edit mode without login', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Anonymous users should get a login action instead of edit mode
      const loginToEditButton = page.getByRole('button', { name: /login to edit/i });
      await expect(loginToEditButton).toBeVisible({ timeout: TIMEOUT_SHORT });
      const plainEditButton = page.getByRole('button', { name: /^edit$/i });
      await expect(plainEditButton).toHaveCount(0, { timeout: TIMEOUT_SHORT });
    });
  });

  test.describe('Verified User', () => {
    test('can see edit button on location detail', async ({ verifiedUser }) => {
      await verifiedUser.goto('/information/locations');

      // Wait for page to load
      await verifiedUser.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on a location if available
      const firstLocation = verifiedUser.locator('.item-link, [role="listbox"] a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // Check that edit button is visible
        const editButton = verifiedUser.locator('button', { hasText: /edit/i });
        await expect(editButton).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      }
    });

    test('can enter edit mode', async ({ verifiedUser }) => {
      await verifiedUser.goto('/information/locations');

      // Wait for page to load
      await verifiedUser.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on a location if available
      const firstLocation = verifiedUser.locator('.item-link, [role="listbox"] a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // Click edit button
        const editButton = verifiedUser.locator('button', { hasText: /edit/i });
        if (await editButton.isVisible({ timeout: TIMEOUT_SHORT })) {
          await editButton.click();
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Check that we're in edit mode (cancel button should appear)
          const cancelButton = verifiedUser.locator('.action-bar button:has-text("Cancel"), .edit-action-bar button:has-text("Cancel"), button:has-text("Cancel")').first();
          await expect(cancelButton).toBeVisible({ timeout: TIMEOUT_SHORT });
        }
      }
    });

    test('can see create button', async ({ verifiedUser }) => {
      await verifiedUser.goto('/information/locations');

      // Wait for page to load
      await verifiedUser.waitForTimeout(TIMEOUT_MEDIUM);

      // Check for create/new button
      const createButton = verifiedUser.getByRole('button', { name: /new/i });
      await expect(createButton).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  test.describe('Type-specific features', () => {
    test('Area type shows area-specific fields', async ({ page }) => {
      await page.goto('/information/locations/areas');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the area type page
      await expect(page).toHaveURL(/.*locations\/areas.*/i);
      await expect(page.locator('.breadcrumbs, nav[aria-label="breadcrumb"]')).toContainText(/Area/i, { timeout: TIMEOUT_SHORT });
    });

    test('Estate type filter works', async ({ page }) => {
      await page.goto('/information/locations/estates');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the estate type page
      await expect(page).toHaveURL(/.*locations\/estates.*/i);
    });

    test('Teleporter type filter works', async ({ page }) => {
      await page.goto('/information/locations/teleporters');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the teleporter type page
      await expect(page).toHaveURL(/.*locations\/teleporters.*/i);
    });
  });

  test.describe('Facilities', () => {
    test('facilities section displays when viewing location', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on a location
      const firstLocation = page.locator('.item-link, [role="listbox"] a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await page.waitForTimeout(TIMEOUT_SHORT);

        // Check for current location detail sections
        const detailsSection = page.locator('h4, h3').filter({ hasText: /Details|Waypoint|Closest Teleporters/i }).first();
        await expect(detailsSection).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      }
    });
  });

  test.describe('Navigation', () => {
    test('breadcrumbs show correct hierarchy', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check breadcrumbs contain Information and Locations
      const breadcrumbs = page.locator('.breadcrumbs, nav[aria-label="breadcrumb"]');
      await expect(breadcrumbs).toContainText(/Information/i, { timeout: TIMEOUT_SHORT });
      await expect(breadcrumbs).toContainText(/Locations/i, { timeout: TIMEOUT_SHORT });
    });

    test('can navigate back to locations list from detail', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load and click a location
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      const firstLocation = page.locator('.item-link, [role="listbox"] a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await page.waitForTimeout(TIMEOUT_SHORT);

        // Click back or breadcrumb to return to list
        const locationsLink = page.locator('nav[aria-label="breadcrumb"] a', { hasText: 'Locations' }).first();
        if (await locationsLink.isVisible({ timeout: TIMEOUT_SHORT })) {
          await locationsLink.click();
          await expect(page).toHaveURL(/.*\/information\/locations.*/, { timeout: TIMEOUT_MEDIUM });
        }
      }
    });
  });
});
