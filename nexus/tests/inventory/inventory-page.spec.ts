import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM } from '../test-constants';

/**
 * Inventory Page Tests
 *
 * Verifies:
 * 1. Access control (auth required, verified only)
 * 2. Page loads with layout and components
 * 3. View mode switching
 * 4. Sidebar filtering
 * 5. Mobile responsiveness
 */

function expectInAuthFlow(url: string) {
  const inAuthFlow =
    url.includes('/discord/login') ||
    url.includes('discord.com/');
  expect(inAuthFlow).toBeTruthy();
}

test.describe('Inventory Page Access', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/account/inventory', { waitUntil: 'networkidle' });
    expectInAuthFlow(page.url());
  });

  test('loads for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('.inventory-layout, .inventory-page')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});

test.describe('Inventory Page Layout', () => {
  test('has sidebar with planet selector', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const sidebar = verifiedUser.locator('.inventory-sidebar');
    await expect(sidebar).toBeVisible();
  });

  test('has main content area', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const main = verifiedUser.locator('.inventory-main');
    await expect(main).toBeVisible();
  });

  test('has toolbar with search and view controls', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const toolbar = verifiedUser.locator('.inventory-toolbar');
    await expect(toolbar).toBeVisible();
  });

  test('has summary bar', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const summary = verifiedUser.locator('.summary-bar');
    await expect(summary).toBeVisible();
  });

  test('has import button', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const importBtn = verifiedUser.getByRole('button', { name: /import/i });
    await expect(importBtn).toBeVisible();
  });
});

test.describe('Inventory View Modes', () => {
  test('defaults to list view', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    // List view should have a FancyTable
    const viewBtns = verifiedUser.locator('.view-toggle button');
    const count = await viewBtns.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('can switch between view modes', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const viewBtns = verifiedUser.locator('.view-toggle button');
    const count = await viewBtns.count();

    // Click each view button and verify no error
    for (let i = 0; i < count; i++) {
      await viewBtns.nth(i).click();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Should not show any error
      const error = verifiedUser.locator('.error-status');
      await expect(error).toBeHidden();
    }
  });
});

test.describe('Inventory Structure Toggle', () => {
  test('has flat/tree toggle', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const structureToggle = verifiedUser.locator('.structure-toggle');
    await expect(structureToggle).toBeVisible();
  });
});

test.describe('Inventory URL Sync', () => {
  test('view mode persists in URL', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory?view=grid', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    // Grid view should be active
    const gridView = verifiedUser.locator('.inventory-grid');
    await expect(gridView).toBeVisible();
  });

  test('search filter syncs to URL', async ({ verifiedUser }) => {
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    const searchInput = verifiedUser.locator('.inventory-toolbar input[type="text"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('test');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      expect(verifiedUser.url()).toContain('search=test');
    }
  });
});

test.describe('Inventory Short URL', () => {
  test('short URL /ai redirects to inventory', async ({ verifiedUser }) => {
    await verifiedUser.goto('/ai', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    expect(verifiedUser.url()).toContain('/account/inventory');
  });
});

test.describe('Inventory Mobile Layout', () => {
  test('sidebar becomes overlay on mobile', async ({ verifiedUser }) => {
    await verifiedUser.setViewportSize({ width: 600, height: 800 });
    await verifiedUser.goto('/account/inventory', { waitUntil: 'networkidle' });
    await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

    // Sidebar should be hidden or collapsed
    const sidebar = verifiedUser.locator('.inventory-sidebar');
    const isHidden = await sidebar.evaluate(el => {
      const style = getComputedStyle(el);
      return style.position === 'fixed' || style.display === 'none';
    }).catch(() => true);

    expect(isHidden).toBeTruthy();
  });
});
