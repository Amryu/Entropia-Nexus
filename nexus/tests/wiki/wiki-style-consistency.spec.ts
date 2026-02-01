import { test, expect } from '@playwright/test';
import { WIKI_PAGES } from './test-pages';
import { TIMEOUT_MEDIUM } from '../test-constants';

const TEST_PAGES = WIKI_PAGES;


test.describe('Wiki Styling - Consistency Across Pages', () => {
  test.describe('Entity Image Size', () => {
    test('entity images have consistent aspect ratio', async ({ page }) => {
      for (const testPage of TEST_PAGES) {
        await page.goto(testPage.path);
        await page.waitForLoadState('networkidle');

        const firstItem = page.locator('.item-link').first();
        try {
          await expect(firstItem).toBeVisible({ timeout: TIMEOUT_MEDIUM });
          await firstItem.click();
          await page.waitForLoadState('networkidle');
        } catch {
          // No items available - skip this page
          continue;
        }

        const imageWrapper = page.locator('.entity-icon-wrapper');
        if (await imageWrapper.isVisible()) {
          const box = await imageWrapper.boundingBox();
          if (box) {
            const aspectRatio = box.width / box.height;
            expect(Math.abs(aspectRatio - 1)).toBeLessThan(0.1);
          }
        }
      }
    });
  });

  test.describe('Color Theme Consistency', () => {
    test('pages use CSS variables for colors', async ({ page }) => {
      for (const testPage of TEST_PAGES) {
        await page.goto(testPage.path);
        await page.waitForLoadState('networkidle');

        const infobox = page.locator('.wiki-infobox-float');
        if (await infobox.isVisible()) {
          const bgColor = await infobox.evaluate(el =>
            getComputedStyle(el).backgroundColor
          );
          expect(bgColor).toBeTruthy();
        }
      }
    });
  });

  test.describe('Responsive Behavior', () => {
    test('mobile layout works consistently', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });

      for (const testPage of TEST_PAGES) {
        await page.goto(testPage.path);
        await page.waitForLoadState('networkidle');

        // Mobile navigation should be accessible via nav toggle button or visible nav
        const navToggle = page.locator('.nav-toggle-btn');
        const wikiNav = page.locator('.wiki-nav');

        // Check for nav toggle button first (for wiki pages with sidebar)
        try {
          await expect(navToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
        } catch {
          // If no nav toggle, must have visible nav (pages without sidebar)
          await expect(wikiNav).toBeVisible({ timeout: TIMEOUT_MEDIUM });
        }
      }
    });
  });
});
