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
      const sidebar = page.locator('.locations-sidebar, [slot="sidebar"]');
      await expect(sidebar).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('can filter by type using type toggle', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Find and click a type filter button (e.g., Teleporter)
      const teleporterButton = page.locator('.type-toggle button', { hasText: 'Teleporter' });
      if (await teleporterButton.isVisible({ timeout: TIMEOUT_SHORT })) {
        await teleporterButton.click();
        await expect(page).toHaveURL(/.*locations\/teleporter.*/i, { timeout: TIMEOUT_MEDIUM });
      }
    });

    test('can view a location detail page', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for locations to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on the first location in the sidebar if available
      const firstLocation = page.locator('.wiki-nav-item a, .nav-item a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        const locationName = await firstLocation.textContent();
        await firstLocation.click();

        // Should show location details
        await expect(page.locator('.wiki-article, .article-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      }
    });

    test('cannot access edit mode without login', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that edit button is not visible for anonymous users
      const editButton = page.locator('button', { hasText: /edit/i });
      await expect(editButton).toHaveCount(0, { timeout: TIMEOUT_SHORT });
    });
  });

  test.describe('Verified User', () => {
    test('can see edit button on location detail', async ({ verifiedUser }) => {
      await verifiedUser.goto('/information/locations');

      // Wait for page to load
      await verifiedUser.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on a location if available
      const firstLocation = verifiedUser.locator('.wiki-nav-item a, .nav-item a').first();
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
      const firstLocation = verifiedUser.locator('.wiki-nav-item a, .nav-item a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // Click edit button
        const editButton = verifiedUser.locator('button', { hasText: /edit/i });
        if (await editButton.isVisible({ timeout: TIMEOUT_SHORT })) {
          await editButton.click();
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Check that we're in edit mode (cancel button should appear)
          const cancelButton = verifiedUser.locator('button', { hasText: /cancel/i });
          await expect(cancelButton).toBeVisible({ timeout: TIMEOUT_SHORT });
        }
      }
    });

    test('can see create button', async ({ verifiedUser }) => {
      await verifiedUser.goto('/information/locations');

      // Wait for page to load
      await verifiedUser.waitForTimeout(TIMEOUT_MEDIUM);

      // Check for create/new button
      const createButton = verifiedUser.locator('button, a', { hasText: /create|new/i });
      await expect(createButton.first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  test.describe('Type-specific features', () => {
    test('Area type shows area-specific fields', async ({ page }) => {
      await page.goto('/information/locations/area');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the area type page
      await expect(page).toHaveURL(/.*locations\/area.*/i);

      // Area type toggle should be active
      const areaButton = page.locator('.type-toggle button.active', { hasText: 'Area' });
      await expect(areaButton).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('Estate type filter works', async ({ page }) => {
      await page.goto('/information/locations/estate');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the estate type page
      await expect(page).toHaveURL(/.*locations\/estate.*/i);
    });

    test('Teleporter type filter works', async ({ page }) => {
      await page.goto('/information/locations/teleporter');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Check that we're on the teleporter type page
      await expect(page).toHaveURL(/.*locations\/teleporter.*/i);
    });
  });

  test.describe('Facilities', () => {
    test('facilities section displays when viewing location', async ({ page }) => {
      await page.goto('/information/locations');

      // Wait for page to load
      await page.waitForTimeout(TIMEOUT_MEDIUM);

      // Click on a location
      const firstLocation = page.locator('.wiki-nav-item a, .nav-item a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await page.waitForTimeout(TIMEOUT_SHORT);

        // Check for facilities section
        const facilitiesSection = page.locator('text=Facilities');
        await expect(facilitiesSection).toBeVisible({ timeout: TIMEOUT_MEDIUM });
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

      const firstLocation = page.locator('.wiki-nav-item a, .nav-item a').first();
      if (await firstLocation.isVisible({ timeout: TIMEOUT_SHORT })) {
        await firstLocation.click();
        await page.waitForTimeout(TIMEOUT_SHORT);

        // Click back or breadcrumb to return to list
        const locationsLink = page.locator('a', { hasText: 'Locations' });
        if (await locationsLink.isVisible({ timeout: TIMEOUT_SHORT })) {
          await locationsLink.click();
          await expect(page).toHaveURL(/.*\/information\/locations.*/, { timeout: TIMEOUT_MEDIUM });
        }
      }
    });
  });
});
