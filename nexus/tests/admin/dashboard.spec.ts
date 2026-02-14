import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT } from '../test-constants';

test.describe('Admin Dashboard', () => {
  test.describe('Access Control', () => {
    test('unauthenticated users cannot access admin', async ({ page }) => {
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Should redirect into auth flow or show an explicit error page
      const currentUrl = page.url();
      const inAuthFlow =
        currentUrl.includes('/discord/login') ||
        currentUrl.includes('discord.com');
      const errorStatus = page.locator('.error-status');
      const hasError = await errorStatus.isVisible().catch(() => false);

      expect(inAuthFlow || hasError).toBeTruthy();
    });

    test('non-admin users are redirected', async ({ verifiedUser }) => {
      await verifiedUser.goto('/admin');
      await verifiedUser.waitForLoadState('networkidle');

      // Non-admin users are redirected to homepage, not shown 403
      expect(verifiedUser.url()).not.toContain('/admin');
    });

    test('admin users can access dashboard', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Should not show error
      const errorStatus = adminUser.locator('.error-status');
      await expect(errorStatus).toBeHidden();

      // Should have admin layout
      const pageContent = adminUser.locator('.admin-layout');
      await expect(pageContent).toBeVisible();
    });
  });

  test.describe('Admin Navigation', () => {
    test('admin dashboard has sidebar navigation', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const sidebar = adminUser.locator('.admin-sidebar');
      await expect(sidebar).toBeVisible();
    });

    test('sidebar has dashboard link', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const dashboardLink = adminUser.locator('.admin-sidebar a[href="/admin"]');
      await expect(dashboardLink).toBeVisible();
    });

    test('sidebar has changes link', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const changesLink = adminUser.locator('.admin-sidebar a[href="/admin/changes"]');
      await expect(changesLink).toBeVisible();
    });

    test('sidebar has users link', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const usersLink = adminUser.locator('.admin-sidebar a[href="/admin/users"]');
      await expect(usersLink).toBeVisible();
    });

    test('sidebar navigation works', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Click users link and wait for navigation
      const usersLink = adminUser.locator('.admin-sidebar a[href="/admin/users"]');
      await Promise.all([
        adminUser.waitForURL('**/admin/users'),
        usersLink.click()
      ]);

      expect(adminUser.url()).toContain('users');
    });
  });

  test.describe('Admin Dashboard Content', () => {
    test('dashboard has title', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      await expect(adminUser).toHaveTitle(/Admin|Dashboard/i);
    });

    test('dashboard has content area', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const contentArea = adminUser.locator('.admin-content');
      await expect(contentArea).toBeVisible();
    });
  });

  test.describe('Mobile Admin Sidebar (≤768px)', () => {
    test.beforeEach(async ({ adminUser }) => {
      await adminUser.setViewportSize({ width: 600, height: 800 });
    });

    test('sidebar is hidden by default on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Sidebar should be hidden (transformed off-screen)
      const sidebar = adminUser.locator('.admin-sidebar');
      const isOffscreen = await sidebar.evaluate(el => {
        const rect = el.getBoundingClientRect();
        return rect.right <= 0;
      }).catch(() => true);

      expect(isOffscreen).toBeTruthy();
    });

    test('sidebar toggle button is visible on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const toggleBtn = adminUser.locator('.sidebar-toggle');
      await expect(toggleBtn).toBeVisible();
    });

    test('clicking toggle opens sidebar on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const toggleBtn = adminUser.locator('.sidebar-toggle');
      await toggleBtn.click();

      // Sidebar should be open
      const sidebar = adminUser.locator('.admin-sidebar.open');
      await expect(sidebar).toBeVisible();
    });

    test('sidebar has overlay when open on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const toggleBtn = adminUser.locator('.sidebar-toggle');
      await toggleBtn.click();

      const overlay = adminUser.locator('.sidebar-overlay.open');
      await expect(overlay).toBeVisible();
    });

    test('clicking overlay closes sidebar on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Open sidebar
      const toggleBtn = adminUser.locator('.sidebar-toggle');
      await toggleBtn.click();
      await expect(adminUser.locator('.admin-sidebar.open')).toBeVisible();

      // Click overlay
      const overlay = adminUser.locator('.sidebar-overlay');
      await overlay.click();

      // Sidebar should close
      await expect(adminUser.locator('.admin-sidebar.open')).toBeHidden();
    });

    test('clicking nav item closes sidebar on mobile', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Open sidebar
      await adminUser.locator('.sidebar-toggle').click();
      await expect(adminUser.locator('.admin-sidebar.open')).toBeVisible();

      // Click a nav item and wait for navigation
      const navItem = adminUser.locator('.admin-sidebar a[href="/admin/users"]');
      await Promise.all([
        adminUser.waitForURL('**/admin/users'),
        navItem.click()
      ]);

      // Sidebar should close after navigation
      await expect(adminUser.locator('.admin-sidebar.open')).toBeHidden();
    });
  });
});

test.describe('Admin Users Page', () => {
  test.describe('Access and Layout', () => {
    test('admin can access users page', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      expect(adminUser.url()).toContain('users');
      await expect(adminUser.locator('.error-status')).toBeHidden();
    });

    test('users page has table', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      // Wait for data to load
      await adminUser.waitForTimeout(TIMEOUT_INSTANT);

      // FancyTable uses fancy-table-container
      const table = adminUser.locator('.fancy-table-container');
      await expect(table).toBeVisible();
    });

    test('users table has header', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      // Wait for data to load
      await adminUser.waitForTimeout(TIMEOUT_INSTANT);

      // FancyTable uses .table-header
      const header = adminUser.locator('.table-header');
      await expect(header).toBeVisible();
    });

    test('users page has status filter', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      // Look for status filter dropdown
      const statusFilter = adminUser.locator('#status-filter');
      await expect(statusFilter).toBeVisible();
    });
  });

  test.describe('User Status Badges', () => {
    test('user list shows status badges', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      // Wait for table to load with data
      await adminUser.waitForTimeout(TIMEOUT_SHORT);

      // FancyTable renders rows
      const rows = adminUser.locator('.table-row');
      const rowCount = await rows.count();

      // If we have rows, check for status badges
      if (rowCount > 0) {
        const badges = adminUser.locator('.status-badge');
        expect(await badges.count()).toBeGreaterThan(0);
      }
    });
  });

  test.describe('User Table Interactions', () => {
    test('clicking user row navigates to user detail', async ({ adminUser }) => {
      await adminUser.goto('/admin/users');
      await adminUser.waitForLoadState('networkidle');

      // Wait for data to load
      await adminUser.waitForTimeout(TIMEOUT_SHORT);

      // Click a row (FancyTable uses .table-row)
      const row = adminUser.locator('.table-row').first();
      if (await row.isVisible()) {
        await Promise.all([
          adminUser.waitForURL(/\/admin\/users\/\d+/),
          row.click()
        ]);

        // Should navigate to user detail
        expect(adminUser.url()).toMatch(/admin\/users\/\d+/);
      }
    });
  });

  test.describe('Users API', () => {
    test('users API returns data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/users');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(data.users).toBeDefined();
      expect(Array.isArray(data.users)).toBeTruthy();
    });

    test('users API supports pagination', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/users?page=1&limit=10');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(data.total).toBeDefined();
      expect(data.page).toBeDefined();
      expect(data.limit).toBeDefined();
    });

    test('users API supports search', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/users?q=test');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(data.mode).toBe('search');
    });

    test('users API requires admin', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/admin/users');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });
  });
});

test.describe('Admin Changes Page', () => {
  test.describe('Access and Layout', () => {
    test('admin can access changes page', async ({ adminUser }) => {
      await adminUser.goto('/admin/changes');
      await adminUser.waitForLoadState('networkidle');

      expect(adminUser.url()).toContain('changes');
      await expect(adminUser.locator('.error-status')).toBeHidden();
    });

    test('changes page has table', async ({ adminUser }) => {
      await adminUser.goto('/admin/changes');
      await adminUser.waitForLoadState('networkidle');

      // Changes page uses .changes-table
      const table = adminUser.locator('.changes-table, .changes-page');
      await expect(table.first()).toBeVisible();
    });
  });

  test.describe('Change Filtering', () => {
    test('changes page has state filter', async ({ adminUser }) => {
      await adminUser.goto('/admin/changes');
      await adminUser.waitForLoadState('networkidle');

      // Look for state filter dropdown
      const filter = adminUser.locator('.filters select, .filter-group select').first();
      await expect(filter).toBeVisible();
    });

    test('changes page has entity filter', async ({ adminUser }) => {
      await adminUser.goto('/admin/changes');
      await adminUser.waitForLoadState('networkidle');

      // Look for entity filter
      const filters = adminUser.locator('.filter-group select');
      expect(await filters.count()).toBeGreaterThan(1);
    });
  });
});

test.describe('Admin Styling', () => {
  test('admin pages use theme variables', async ({ adminUser }) => {
    await adminUser.goto('/admin');
    await adminUser.waitForLoadState('networkidle');

    const sidebar = adminUser.locator('.admin-sidebar');
    if (await sidebar.isVisible()) {
      const bgColor = await sidebar.evaluate(el => getComputedStyle(el).backgroundColor);
      expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
    }
  });

  test('admin layout is properly structured', async ({ adminUser }) => {
    await adminUser.goto('/admin');
    await adminUser.waitForLoadState('networkidle');

    // Should have admin layout container
    const layout = adminUser.locator('.admin-layout');
    await expect(layout).toBeVisible();
  });

  test('admin content area has proper padding', async ({ adminUser }) => {
    await adminUser.goto('/admin');
    await adminUser.waitForLoadState('networkidle');

    const content = adminUser.locator('.admin-content');
    if (await content.isVisible()) {
      const padding = await content.evaluate(el => getComputedStyle(el).padding);
      expect(padding).not.toBe('0px');
    }
  });
});
