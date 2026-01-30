import { test, expect } from '../fixtures/auth';

test.describe('Admin Impersonation', () => {
  test.describe('API Tests', () => {
    test('admin can start impersonating a user via API', async ({ adminUser }) => {
      const page = adminUser;

      // Get a user to impersonate - use verified1 test user
      const response = await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' } // verified1 test user ID
      });

      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data.success).toBe(true);
      expect(data.impersonating).toBeDefined();
      expect(data.impersonating.username).toBe('testuser1');
    });

    test('admin can stop impersonating via API', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating first
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      // Now stop impersonating
      const response = await page.request.delete('/api/admin/impersonate');

      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data.success).toBe(true);
    });

    test('admin can get impersonation status via API', async ({ adminUser }) => {
      const page = adminUser;

      // Check status before impersonating
      const statusBefore = await page.request.get('/api/admin/impersonate');
      expect(statusBefore.ok()).toBeTruthy();
      const dataBefore = await statusBefore.json();
      expect(dataBefore.impersonating).toBe(false);

      // Start impersonating
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      // Reload and check status after impersonating
      await page.reload();
      const statusAfter = await page.request.get('/api/admin/impersonate');
      expect(statusAfter.ok()).toBeTruthy();
      const dataAfter = await statusAfter.json();
      expect(dataAfter.impersonating).toBe(true);

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });

    test('non-admin cannot impersonate via API', async ({ verifiedUser }) => {
      const page = verifiedUser;

      const response = await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });

    test('admin cannot impersonate themselves', async ({ adminUser }) => {
      const page = adminUser;

      // Try to impersonate self (admin user ID)
      const response = await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000007' } // testadmin ID
      });

      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
      const data = await response.json();
      expect(data.error).toContain('yourself');
    });

    test('impersonation requires valid user ID', async ({ adminUser }) => {
      const page = adminUser;

      const response = await page.request.post('/api/admin/impersonate', {
        data: { userId: '999999999999999999' } // Non-existent user
      });

      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(404);
    });
  });

  test.describe('UI Tests', () => {
    test('admin sees impersonate user option in menu', async ({ adminUser }) => {
      const page = adminUser;
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Hover over user avatar to open dropdown
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be visible
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Should see impersonate user button in desktop dropdown (not mobile menu)
      const impersonateButton = dropdown.locator('button:has-text("Impersonate User")');
      await expect(impersonateButton).toBeVisible();
    });

    test('non-admin does not see impersonate option', async ({ verifiedUser }) => {
      const page = verifiedUser;
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Hover over user avatar to open dropdown
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be visible
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Should NOT see impersonate user button in desktop dropdown
      const impersonateButton = dropdown.locator('button:has-text("Impersonate User")');
      await expect(impersonateButton).not.toBeVisible();
    });

    test('admin can open impersonate dialog', async ({ adminUser }) => {
      const page = adminUser;
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Hover over user avatar to open dropdown
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be fully visible and stable
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Click impersonate button while keeping hover
      const impersonateBtn = dropdown.locator('button:has-text("Impersonate User")');
      await impersonateBtn.waitFor({ state: 'visible' });
      await impersonateBtn.click({ force: true });

      // Dialog should be visible
      const dialog = page.locator('.dialog');
      await expect(dialog).toBeVisible();

      // Should have search input
      const searchInput = page.locator('#impersonate-search');
      await expect(searchInput).toBeVisible();
    });

    test('impersonation shows visual indicator on avatar', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating via API
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      await page.goto('/');

      // Avatar should have impersonating class (red border)
      const userAvatar = page.locator('.user-image.impersonating');
      await expect(userAvatar).toBeVisible();

      // Avatar should have title attribute with impersonation info
      await expect(userAvatar).toHaveAttribute('title', /Impersonating/);

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });

    test('impersonation shows stop button in dropdown', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating via API
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Hover over user avatar
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be visible
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Should show stop impersonating button in desktop dropdown
      const stopButton = dropdown.locator('button:has-text("Stop Impersonating")');
      await expect(stopButton).toBeVisible();

      // Should show impersonation info
      const impersonateInfo = dropdown.locator('.impersonate-info');
      await expect(impersonateInfo.first()).toBeVisible();

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });

    test('admin can stop impersonating via UI', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating via API
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Verify impersonating indicator is visible
      await expect(page.locator('.user-image.impersonating')).toBeVisible();

      // Hover over user avatar
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be fully visible and stable
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Click stop button while dropdown is visible
      const stopBtn = dropdown.locator('button:has-text("Stop Impersonating")');
      await stopBtn.waitFor({ state: 'visible' });
      await stopBtn.click({ force: true });

      // Wait for page to reload/update
      await page.waitForLoadState('networkidle');

      // Avatar should no longer have impersonating class
      await expect(page.locator('.user-image.impersonating')).not.toBeVisible();
      await expect(page.locator('.user-image')).toBeVisible();
    });

    test('impersonation does not show impersonate button while impersonating', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating via API
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Hover over user avatar
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be visible
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Should NOT see "Impersonate User" button in desktop dropdown while already impersonating
      const impersonateButton = dropdown.locator('button:has-text("Impersonate User")');
      await expect(impersonateButton).not.toBeVisible();

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });
  });

  test.describe('Impersonation Behavior', () => {
    test('impersonated user sees correct permissions', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating a regular verified user
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' } // verified1 - not admin
      });

      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // The admin menu/links should not be visible since we're impersonating a non-admin
      // But we should still see admin controls for the real user (stop impersonating)
      const userAvatar = page.locator('.user-image');
      await userAvatar.hover();

      // Wait for dropdown to be visible
      const dropdown = page.locator('.dropdown-content.right');
      await dropdown.waitFor({ state: 'visible' });

      // Stop button should be visible in desktop dropdown (real user is admin)
      const stopButton = dropdown.locator('button:has-text("Stop Impersonating")');
      await expect(stopButton).toBeVisible();

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });

    test('impersonation persists across page navigation', async ({ adminUser }) => {
      const page = adminUser;

      // Start impersonating via API
      await page.request.post('/api/admin/impersonate', {
        data: { userId: '900000000000000001' }
      });

      await page.goto('/');
      await expect(page.locator('.user-image.impersonating')).toBeVisible();

      // Navigate to another page
      await page.goto('/tools/loadouts');
      await page.waitForLoadState('networkidle');

      // Impersonation indicator should still be visible
      await expect(page.locator('.user-image.impersonating')).toBeVisible();

      // Cleanup
      await page.request.delete('/api/admin/impersonate');
    });
  });
});
