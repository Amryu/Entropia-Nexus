import { test, expect } from '../fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

test.describe('Admin Map Editor', () => {
  test.describe('Access Control', () => {
    test('unauthenticated users cannot access admin map', async ({ page }) => {
      await page.goto('/admin/map');
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
      await verifiedUser.goto('/admin/map');
      await verifiedUser.waitForLoadState('networkidle');

      expect(verifiedUser.url()).not.toContain('/admin');
    });

    test('admin users can access map editor', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const mapPage = adminUser.locator('.admin-map-page');
      await expect(mapPage).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  test.describe('Map Editor Layout', () => {
    test('shows toolbar with planet selector', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const toolbar = adminUser.locator('.toolbar');
      await expect(toolbar).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // Planet selector
      const planetSelect = toolbar.locator('select');
      await expect(planetSelect).toBeVisible();
    });

    test('shows view/edit mode toggle', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const modeToggle = adminUser.locator('.mode-toggle');
      await expect(modeToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // View button should be active by default
      const viewBtn = modeToggle.locator('button', { hasText: 'View' });
      await expect(viewBtn).toHaveClass(/active/);
    });

    test('shows SQL output toggle with badge', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const sqlToggle = adminUser.locator('.sql-toggle');
      await expect(sqlToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(sqlToggle).toContainText('SQL Output');
    });

    test('shows three-column layout', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const leftSidebar = adminUser.locator('.left-sidebar');
      const mapArea = adminUser.locator('.map-area');
      const rightPanel = adminUser.locator('.right-panel');

      await expect(leftSidebar).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(mapArea).toBeVisible();
      await expect(rightPanel).toBeVisible();
    });

    test('shows no selection message in editor panel', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      // Before selecting a planet, the right panel should show the location editor empty state
      const noSelection = adminUser.locator('.no-selection');
      await expect(noSelection).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  test.describe('Planet Selection', () => {
    test('can select a planet and load map data', async ({ adminUser }) => {
      await adminUser.goto('/admin/map');
      await adminUser.waitForLoadState('networkidle');

      const planetSelect = adminUser.locator('.toolbar select');
      await expect(planetSelect).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // Select the first available planet
      const options = await planetSelect.locator('option:not([disabled])').all();
      if (options.length > 0) {
        const value = await options[0].getAttribute('value');
        if (value) {
          await planetSelect.selectOption(value);
          // Wait for data to load
          await adminUser.waitForTimeout(TIMEOUT_MEDIUM);

          // Map area should no longer show "Select a planet" message
          const noPlanet = adminUser.locator('.no-planet');
          await expect(noPlanet).toBeHidden({ timeout: TIMEOUT_LONG });
        }
      }
    });
  });
});
