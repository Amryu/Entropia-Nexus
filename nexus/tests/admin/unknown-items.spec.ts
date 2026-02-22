import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM } from '../test-constants';

/**
 * Admin Unknown Items Page Tests
 *
 * Verifies:
 * 1. Access control (admin only)
 * 2. Page layout and table
 * 3. Navigation from admin sidebar
 */

test.describe('Admin Unknown Items Page', () => {
  test.describe('Access Control', () => {
    test('non-admin users cannot access unknown items page', async ({ verifiedUser }) => {
      await verifiedUser.goto('/admin/unknown-items');
      await verifiedUser.waitForLoadState('networkidle');

      // Non-admin users are redirected
      expect(verifiedUser.url()).not.toContain('/admin/unknown-items');
    });

    test('admin can access unknown items page', async ({ adminUser }) => {
      await adminUser.goto('/admin/unknown-items');
      await adminUser.waitForLoadState('networkidle');

      expect(adminUser.url()).toContain('unknown-items');
      await expect(adminUser.locator('.error-status')).toBeHidden();
    });
  });

  test.describe('Page Content', () => {
    test('has page title', async ({ adminUser }) => {
      await adminUser.goto('/admin/unknown-items');
      await adminUser.waitForLoadState('networkidle');
      await adminUser.waitForTimeout(TIMEOUT_SHORT);

      // Use .admin-content to avoid matching the sidebar "Admin Panel" h2
      await expect(adminUser.locator('.admin-content h1')).toContainText(/unknown items/i, { timeout: TIMEOUT_MEDIUM });
    });

    test('has table for unknown items', async ({ adminUser }) => {
      await adminUser.goto('/admin/unknown-items');
      await adminUser.waitForLoadState('networkidle');
      await adminUser.waitForTimeout(TIMEOUT_SHORT);

      const table = adminUser.locator('.fancy-table-container');
      await expect(table).toBeVisible();
    });

    test('has resolved toggle', async ({ adminUser }) => {
      await adminUser.goto('/admin/unknown-items');
      await adminUser.waitForLoadState('networkidle');
      await adminUser.waitForTimeout(TIMEOUT_SHORT);

      // Should have a checkbox or toggle for showing resolved items
      const resolvedToggle = adminUser.locator('label:has-text("resolved"), input[type="checkbox"]').first();
      await expect(resolvedToggle).toBeVisible();
    });
  });

  test.describe('Admin Navigation', () => {
    test('sidebar has unknown items link', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const unknownItemsLink = adminUser.locator('.admin-sidebar a[href="/admin/unknown-items"]');
      await expect(unknownItemsLink).toBeVisible();
    });

    test('sidebar navigation to unknown items works', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const unknownItemsLink = adminUser.locator('.admin-sidebar a[href="/admin/unknown-items"]');
      await Promise.all([
        adminUser.waitForURL('**/admin/unknown-items'),
        unknownItemsLink.click()
      ]);

      expect(adminUser.url()).toContain('unknown-items');
    });
  });
});
