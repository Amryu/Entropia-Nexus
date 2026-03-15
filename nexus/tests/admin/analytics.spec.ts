import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

test.describe('Admin Analytics', () => {
  test.describe('Access Control', () => {
    test('unauthenticated users cannot access analytics', async ({ page }) => {
      await page.goto('/admin/analytics');
      await page.waitForLoadState('networkidle');

      const currentUrl = page.url();
      const inAuthFlow =
        currentUrl.includes('/discord/login') ||
        currentUrl.includes('discord.com');
      const errorStatus = page.locator('.error-status');
      const hasError = await errorStatus.isVisible().catch(() => false);

      expect(inAuthFlow || hasError).toBeTruthy();
    });

    test('non-admin users are redirected', async ({ verifiedUser }) => {
      await verifiedUser.goto('/admin/analytics');
      await verifiedUser.waitForLoadState('networkidle');

      expect(verifiedUser.url()).not.toContain('/admin');
    });

    test('admin users can access analytics page', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      const pageContent = adminUser.locator('.admin-layout');
      await expect(pageContent).toBeVisible();

      // Should show analytics page title
      await expect(adminUser.locator('h1')).toContainText('Route Analytics');
    });
  });

  test.describe('Page Layout', () => {
    test('analytics page has period picker', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      const periodPicker = adminUser.locator('.period-picker');
      await expect(periodPicker).toBeVisible();

      // Should have period buttons
      await expect(adminUser.locator('.period-btn')).toHaveCount(6);
    });

    test('analytics page has tabs', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      const tabs = adminUser.locator('.tabs .tab');
      await expect(tabs).toHaveCount(7); // Overview, Routes, API, Geography, Referrers, Bots, Live
    });

    test('analytics page has stat cards', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      // Wait for stat cards to appear (overview loads on mount)
      const statCards = adminUser.locator('.stat-card');
      await statCards.first().waitFor({ state: 'visible', timeout: TIMEOUT_LONG });
      const count = await statCards.count();
      expect(count).toBeGreaterThanOrEqual(4);
    });
  });

  test.describe('Tab Navigation', () => {
    test('clicking tabs switches content', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      // Wait for initial overview to render
      await adminUser.locator('.stat-card').first().waitFor({ state: 'visible', timeout: TIMEOUT_LONG });

      // Click Routes tab and wait for route data to render
      const routesResponsePromise = adminUser.waitForResponse(resp =>
        resp.url().includes('/api/admin/analytics/routes'), { timeout: TIMEOUT_LONG }
      );
      await adminUser.locator('.tab', { hasText: 'Routes' }).click();
      await routesResponsePromise;

      // Click Bots tab and wait for bot data to render
      const botsResponsePromise = adminUser.waitForResponse(resp =>
        resp.url().includes('/api/admin/analytics/bots'), { timeout: TIMEOUT_LONG }
      );
      await adminUser.locator('.tab', { hasText: 'Bots' }).click();
      await botsResponsePromise;

      // Bot pattern table should be visible
      const patternTable = adminUser.locator('.data-table');
      await expect(patternTable).toBeVisible();
    });

    test('period picker updates data', async ({ adminUser }) => {
      await adminUser.goto('/admin/analytics');
      await adminUser.waitForLoadState('networkidle');

      // Wait for initial overview to render
      await adminUser.locator('.stat-card').first().waitFor({ state: 'visible', timeout: TIMEOUT_LONG });

      // Click "30 Days" period — set up response listener before clicking
      const responsePromise = adminUser.waitForResponse(resp =>
        resp.url().includes('period=30d'), { timeout: TIMEOUT_LONG }
      );
      await adminUser.locator('.period-btn', { hasText: '30 Days' }).click();
      await responsePromise;
    });
  });

  test.describe('API Endpoints', () => {
    test('overview API returns data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/overview?period=7d');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('totalRequests');
      expect(data).toHaveProperty('uniqueVisitors');
      expect(data).toHaveProperty('botPercent');
      expect(data).toHaveProperty('topRoutes');
      expect(data).toHaveProperty('topCountries');
      expect(data).toHaveProperty('topReferrers');
    });

    test('routes API returns paginated data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/routes?period=7d&page=1&limit=10');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('routes');
      expect(data).toHaveProperty('total');
      expect(data).toHaveProperty('page');
      expect(data).toHaveProperty('totalPages');
      expect(data).toHaveProperty('categories');
      expect(Array.isArray(data.routes)).toBe(true);
    });

    test('timeseries API returns data points', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/timeseries?period=7d');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('points');
      expect(data).toHaveProperty('granularity');
      expect(Array.isArray(data.points)).toBe(true);
    });

    test('geo API returns country data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/geo?period=7d');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('countries');
      expect(Array.isArray(data.countries)).toBe(true);
    });

    test('oauth API returns client data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/oauth?period=7d');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('clients');
      expect(data).toHaveProperty('details');
    });

    test('referrers API returns data', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/referrers?period=7d');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('referrers');
      expect(Array.isArray(data.referrers)).toBe(true);
    });

    test('bots API returns patterns', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/bots');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('patterns');
      expect(Array.isArray(data.patterns)).toBe(true);
      // Should have seeded patterns
      expect(data.patterns.length).toBeGreaterThan(0);
    });

    test('recent API returns visits', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/analytics/recent?limit=10');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('visits');
      expect(Array.isArray(data.visits)).toBe(true);
    });

    test('overview API requires admin', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/admin/analytics/overview');
      expect(response.status()).toBe(403);
    });
  });

  test.describe('Bot Management', () => {
    test('can add and delete bot patterns', async ({ adminUser }) => {
      // Add a new pattern
      const addResponse = await adminUser.request.post('/api/admin/analytics/bots', {
        data: { pattern: 'TestBot-E2E', description: 'E2E test bot' }
      });
      expect(addResponse.status()).toBe(201);
      const addData = await addResponse.json();
      expect(addData.pattern.pattern).toBe('TestBot-E2E');
      const patternId = addData.pattern.id;

      // Verify it shows in the list
      const listResponse = await adminUser.request.get('/api/admin/analytics/bots');
      const listData = await listResponse.json();
      const found = listData.patterns.find((p: any) => p.pattern === 'TestBot-E2E');
      expect(found).toBeTruthy();

      // Toggle disable
      const patchResponse = await adminUser.request.patch(`/api/admin/analytics/bots/${patternId}`, {
        data: { enabled: false }
      });
      expect(patchResponse.status()).toBe(200);
      const patchData = await patchResponse.json();
      expect(patchData.pattern.enabled).toBe(false);

      // Delete it
      const deleteResponse = await adminUser.request.delete(`/api/admin/analytics/bots/${patternId}`);
      expect(deleteResponse.status()).toBe(200);

      // Verify it's gone
      const listResponse2 = await adminUser.request.get('/api/admin/analytics/bots');
      const listData2 = await listResponse2.json();
      const notFound = listData2.patterns.find((p: any) => p.pattern === 'TestBot-E2E');
      expect(notFound).toBeUndefined();
    });

    test('adding duplicate pattern returns 409', async ({ adminUser }) => {
      const response = await adminUser.request.post('/api/admin/analytics/bots', {
        data: { pattern: 'Googlebot', description: 'Duplicate test' }
      });
      expect(response.status()).toBe(409);
    });
  });

  test.describe('Admin Sidebar', () => {
    test('sidebar includes Analytics link', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      const analyticsLink = adminUser.locator('.admin-sidebar a[href="/admin/analytics"]');
      await expect(analyticsLink).toBeVisible();
      await expect(analyticsLink).toContainText('Analytics');
    });
  });
});
