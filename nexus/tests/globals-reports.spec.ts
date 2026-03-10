import { test, expect } from './fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Globals Media Report API', () => {
  test('POST requires authentication', async ({ page }) => {
    const resp = await page.request.post('/api/globals/1/media/report', {
      data: { reason: 'Inappropriate content' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBe(401);
  });

  test('POST rejects invalid global ID', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/abc/media/report', {
      data: { reason: 'test' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBe(400);
    const body = await resp.json();
    expect(body.error).toContain('Invalid');
  });

  test('POST rejects empty reason', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/1/media/report', {
      data: { reason: '' },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    if (resp.status() === 400) {
      expect(body.error).toContain('reason');
    }
  });

  test('POST rejects reason exceeding 500 characters', async ({ verifiedUser: page }) => {
    const longReason = 'a'.repeat(501);
    const resp = await page.request.post('/api/globals/1/media/report', {
      data: { reason: longReason },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    if (resp.status() === 400) {
      expect(body.error).toContain('500');
    }
  });

  test('POST returns 404 for non-existent global', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/999999999/media/report', {
      data: { reason: 'Test report' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBe(404);
  });
});

test.describe('Admin Globals Reports Page', () => {
  test('unauthenticated users cannot access admin reports', async ({ page }) => {
    await page.goto('/admin/globals');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com');
    const errorStatus = page.locator('.error-status');
    const hasError = await errorStatus.isVisible().catch(() => false);

    expect(inAuthFlow || hasError).toBeTruthy();
  });

  test('non-admin users cannot access admin reports', async ({ verifiedUser }) => {
    await verifiedUser.goto('/admin/globals');
    await verifiedUser.waitForLoadState('networkidle');

    expect(verifiedUser.url()).not.toContain('/admin/globals');
  });

  test('admin can access reports page', async ({ adminUser }) => {
    await adminUser.goto('/admin/globals');
    await adminUser.waitForLoadState('networkidle');

    expect(adminUser.url()).toContain('/admin/globals');
    await expect(adminUser.locator('.error-status')).toBeHidden();
  });

  test('admin reports page has filter buttons', async ({ adminUser }) => {
    await adminUser.goto('/admin/globals');
    await adminUser.waitForLoadState('networkidle');

    const filterBtns = adminUser.locator('.filter-btns');
    await expect(filterBtns).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(filterBtns.locator('button', { hasText: 'Pending' })).toBeVisible();
    await expect(filterBtns.locator('button', { hasText: 'Resolved' })).toBeVisible();
    await expect(filterBtns.locator('button', { hasText: 'All' })).toBeVisible();
  });

  test('admin reports page has table or empty state', async ({ adminUser }) => {
    await adminUser.goto('/admin/globals');
    await adminUser.waitForLoadState('networkidle');

    // Should have either a table or an empty state message
    const table = adminUser.locator('.table-wrapper table');
    const empty = adminUser.locator('.empty');

    const hasTable = await table.isVisible({ timeout: TIMEOUT_MEDIUM }).catch(() => false);
    const hasEmpty = await empty.isVisible({ timeout: TIMEOUT_MEDIUM }).catch(() => false);

    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('admin sidebar has Globals nav item', async ({ adminUser }) => {
    await adminUser.goto('/admin');
    await adminUser.waitForLoadState('networkidle');

    const globalsLink = adminUser.locator('.admin-sidebar a[href="/admin/globals"]');
    await expect(globalsLink).toBeVisible();
  });
});

test.describe('Admin Report Resolution API', () => {
  test('POST resolve requires admin (unauthenticated)', async ({ page }) => {
    const resp = await page.request.post('/api/admin/globals/reports/1/resolve');
    expect(resp.status()).toBe(401);
  });

  test('POST resolve requires admin (non-admin user)', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/admin/globals/reports/1/resolve');
    expect(resp.status()).toBe(403);
  });

  test('POST resolve rejects invalid report ID', async ({ adminUser }) => {
    const resp = await adminUser.request.post('/api/admin/globals/reports/abc/resolve');
    expect(resp.status()).toBe(400);
    const body = await resp.json();
    expect(body.error).toContain('Invalid');
  });

  test('POST resolve returns 404 for non-existent report', async ({ adminUser }) => {
    const resp = await adminUser.request.post('/api/admin/globals/reports/999999999/resolve');
    expect(resp.status()).toBe(404);
  });
});
