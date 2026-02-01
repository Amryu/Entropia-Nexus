import { test, expect } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_MEDIUM } from '../test-constants';

/**
 * E2E tests for mobile drawer navigation
 * Tests that clicking navigation links in the mobile drawer works correctly on repeated clicks
 */

test.describe('Mobile Drawer Navigation', () => {
  test('mobile drawer allows multiple sequential navigations', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    const navToggle = page.locator('.nav-toggle-btn');
    const drawer = page.locator('[role="dialog"][aria-label="Navigation"]');

    // Drawer should auto-open on mobile when no entity is selected
    // Wait for it or open manually if needed
    await expect(navToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    if (!await drawer.isVisible()) {
      await navToggle.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
    }

    // Verify drawer is open
    await expect(drawer).toBeVisible();

    // Get the first two items
    const firstItem = page.locator('.item-link').first();
    const secondItem = page.locator('.item-link').nth(1);

    // Ensure both items are visible
    await expect(firstItem).toBeVisible();
    await expect(secondItem).toBeVisible();

    // Get the names/hrefs for verification
    const firstHref = await firstItem.getAttribute('href');
    const secondHref = await secondItem.getAttribute('href');

    if (!firstHref || !secondHref || firstHref === secondHref) {
      test.skip(); // Skip if not enough distinct items
      return;
    }

    // First navigation: click first item
    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // Verify we navigated to the first item
    expect(page.url()).toContain(firstHref);

    // Drawer should have closed
    await expect(drawer).not.toBeVisible();

    // Open drawer again
    await navToggle.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await expect(drawer).toBeVisible();

    // Second navigation: click second item
    // This is where the bug occurs - second click doesn't navigate
    await secondItem.click();
    await page.waitForLoadState('networkidle');

    // Verify we navigated to the second item
    expect(page.url()).toContain(secondHref);

    // Drawer should have closed again
    await expect(drawer).not.toBeVisible();

    // Third navigation: go back to first item to ensure it still works
    await navToggle.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await expect(drawer).toBeVisible();

    await firstItem.click();
    await page.waitForLoadState('networkidle');

    // Verify we navigated back to the first item
    expect(page.url()).toContain(firstHref);
  });

  test('mobile drawer navigation works after searching', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    const navToggle = page.locator('.nav-toggle-btn');
    const drawer = page.locator('[role="dialog"][aria-label="Navigation"]');

    // Drawer should auto-open on mobile when no entity is selected
    await expect(navToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    if (!await drawer.isVisible()) {
      await navToggle.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
    }

    await expect(drawer).toBeVisible();

    // Use search to filter items
    const searchInput = drawer.locator('input[type="search"], .search-input input');
    if (await searchInput.isVisible()) {
      await searchInput.fill('a');
      await page.waitForTimeout(TIMEOUT_INSTANT); // Wait for search filtering

      // Click on filtered item
      const firstItem = drawer.locator('.item-link').first();
      if (await firstItem.isVisible()) {
        const href = await firstItem.getAttribute('href');
        await firstItem.click();
        await page.waitForLoadState('networkidle');

        // Verify navigation worked
        if (href) {
          expect(page.url()).toContain(href);
        }
      }
    }
  });
});
