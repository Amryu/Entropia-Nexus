import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT } from '../test-constants';

test.describe('Admin Rewards Page', () => {
  test('admin can access rewards page', async ({ adminUser }) => {
    await adminUser.goto('/admin/rewards');
    await adminUser.waitForLoadState('networkidle');

    await expect(adminUser.locator('h1')).toContainText('Contributor Rewards');
    await expect(adminUser.locator('.error-status')).toBeHidden();
  });

  test('rewards page renders contributor controls', async ({ adminUser }) => {
    await adminUser.goto('/admin/rewards');
    await adminUser.waitForLoadState('networkidle');

    await expect(adminUser.locator('.tabs .tab').first()).toContainText('Contributors');
    await expect(adminUser.getByPlaceholder('Search contributors...')).toBeVisible();
  });

  test('admin rewards contributors API returns paged payload', async ({ adminUser }) => {
    const response = await adminUser.request.get('/api/admin/rewards/contributors?page=1&limit=5');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(Array.isArray(data.contributors)).toBeTruthy();
    expect(typeof data.total).toBe('number');
    expect(typeof data.totalPages).toBe('number');
  });

  test('expanded contributor detail includes eligible changes section', async ({ adminUser }) => {
    await adminUser.goto('/admin/rewards');
    await adminUser.waitForLoadState('networkidle');
    await adminUser.waitForTimeout(TIMEOUT_INSTANT);

    const firstContributorRow = adminUser.locator('tbody tr.clickable-row').first();
    const rowCount = await adminUser.locator('tbody tr.clickable-row').count();
    if (rowCount === 0) test.skip();

    await firstContributorRow.click();
    await expect(adminUser.locator('text=Eligible Approved Changes').first()).toBeVisible();
  });
});
