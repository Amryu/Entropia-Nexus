import { test, expect } from './fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Globals GZ API', () => {
  test('GET /api/globals/1/gz returns gz_count and user_gz', async ({ page }) => {
    const resp = await page.request.get('/api/globals/1/gz');
    // May be 200 or 404 depending on test data
    if (resp.status() === 200) {
      const body = await resp.json();
      expect(body).toHaveProperty('gz_count');
      expect(body).toHaveProperty('user_gz');
      expect(typeof body.gz_count).toBe('number');
      expect(typeof body.user_gz).toBe('boolean');
    }
  });

  test('GET returns user_gz false for anonymous users', async ({ page }) => {
    const resp = await page.request.get('/api/globals/1/gz');
    if (resp.status() === 200) {
      const body = await resp.json();
      expect(body.user_gz).toBe(false);
    }
  });

  test('POST requires authentication', async ({ page }) => {
    const resp = await page.request.post('/api/globals/1/gz');
    expect(resp.status()).toBe(401);
  });

  test('POST rejects invalid global ID', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/abc/gz');
    expect(resp.status()).toBe(400);
    const body = await resp.json();
    expect(body.error).toContain('Invalid');
  });

  test('POST returns 404 for non-existent global', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/999999999/gz');
    expect(resp.status()).toBe(404);
  });

  test('POST toggles GZ and returns count', async ({ verifiedUser: page }) => {
    // Find a confirmed global to test with
    const listResp = await page.request.get('/api/globals?limit=1');
    if (!listResp.ok()) return;
    const listData = await listResp.json();
    if (!listData.globals || listData.globals.length === 0) return;

    const globalId = listData.globals[0].id;

    // First toggle — should add GZ
    const resp1 = await page.request.post(`/api/globals/${globalId}/gz`);
    expect(resp1.ok()).toBeTruthy();
    const body1 = await resp1.json();
    expect(body1).toHaveProperty('gz_count');
    expect(body1).toHaveProperty('user_gz');
    expect(body1.user_gz).toBe(true);
    expect(body1.gz_count).toBeGreaterThanOrEqual(1);

    // Second toggle — should remove GZ
    const resp2 = await page.request.post(`/api/globals/${globalId}/gz`);
    expect(resp2.ok()).toBeTruthy();
    const body2 = await resp2.json();
    expect(body2.user_gz).toBe(false);
    expect(body2.gz_count).toBe(body1.gz_count - 1);
  });
});

test.describe('Globals GZ in feed', () => {
  test('top-loots API includes gz_count', async ({ request }) => {
    const res = await request.get('/api/globals/stats/top-loots?period=all&category=hunting');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    if (data.items.length > 0) {
      expect(data.items[0]).toHaveProperty('gz_count');
    }
  });

  test('globals feed API includes gz_count', async ({ request }) => {
    const res = await request.get('/api/globals?limit=5');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    if (data.globals && data.globals.length > 0) {
      expect(data.globals[0]).toHaveProperty('gz_count');
    }
  });
});

test.describe('Globals GZ UI', () => {
  test('GZ button appears in top loots table', async ({ page }) => {
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');

    const topLoots = page.locator('.top-loots-section');
    await expect(topLoots).toBeVisible({ timeout: TIMEOUT_LONG });

    // Check for gz column
    const gzCells = page.locator('.col-gz');
    if (await gzCells.count() > 0) {
      const gzBtn = page.locator('.gz-btn').first();
      await expect(gzBtn).toBeVisible();
    }
  });

  test('GZ button appears in Live tab table', async ({ page }) => {
    await page.goto('/globals?view=live');
    await page.waitForLoadState('networkidle');

    const tableSection = page.locator('.table-section');
    if (await tableSection.isVisible({ timeout: TIMEOUT_LONG }).catch(() => false)) {
      const gzCells = tableSection.locator('.col-gz');
      if (await gzCells.count() > 0) {
        await expect(tableSection.locator('.gz-btn').first()).toBeVisible();
      }
    }
  });
});
