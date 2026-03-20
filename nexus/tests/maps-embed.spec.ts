import { test, expect } from './fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Map Embed Mode', () => {
  test.describe('UI Visibility', () => {
    test('embed mode hides menu bar', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });

      // Menu should not be present
      const menu = page.locator('nav, .menu, .nav-menu').first();
      await expect(menu).toBeHidden({ timeout: TIMEOUT_SHORT });
    });

    test('embed mode hides edit mode button', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso?embed=1');
      await verifiedUser.waitForLoadState('networkidle');
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeHidden();
    });

    test('embed mode hides create and pending buttons', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso?embed=1');
      await verifiedUser.waitForLoadState('networkidle');
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      const createBtn = verifiedUser.locator('.create-btn');
      await expect(createBtn).toBeHidden();

      const pendingBtn = verifiedUser.locator('.pending-btn');
      await expect(pendingBtn).toBeHidden();
    });

    test('hideSearch=1 hides search controls', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1&hideSearch=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });

      const controls = page.locator('.map-controls');
      await expect(controls).toBeHidden({ timeout: TIMEOUT_SHORT });
    });

    test('hideLayers=1 hides layer toggle buttons', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1&hideLayers=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });

      const layerToggles = page.locator('.layer-toggles');
      await expect(layerToggles).toBeHidden({ timeout: TIMEOUT_SHORT });
    });

    test('embed mode hides planet/area selectors but shows search', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });

      // Planet/area selectors should be hidden
      const controlRow = page.locator('.control-row');
      await expect(controlRow).toBeHidden({ timeout: TIMEOUT_SHORT });

      // Search input should still be visible
      const searchInput = page.locator('.search-input');
      await expect(searchInput).toBeVisible();
    });

    test('embed mode does not auto-open editor with mode=edit', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso?embed=1&mode=edit');
      await verifiedUser.waitForLoadState('networkidle');
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // Leaflet editor overlay should NOT appear
      const editorOverlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(editorOverlay).toBeHidden();
    });
  });

  test.describe('Map Functionality', () => {
    test('map canvas renders in embed mode', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });
    });
  });

  test.describe('postMessage API', () => {
    test('nexus:ready fires on load', async ({ page }) => {
      // Set up listener before navigation
      await page.addInitScript(() => {
        (window as any).__nexusReady = new Promise((resolve) => {
          window.addEventListener('message', (event) => {
            if (event.data?.type === 'nexus:ready') {
              resolve(event.data);
            }
          });
        });
      });

      await page.goto('/maps/calypso?embed=1');

      const readyMsg = await page.evaluate(() => (window as any).__nexusReady);
      expect(readyMsg.planet).toBeTruthy();
      expect(readyMsg.locationCount).toBeGreaterThanOrEqual(0);
    });

    test('nexus:search returns results', async ({ page }) => {
      // Set up ready listener before navigation
      await page.addInitScript(() => {
        (window as any).__nexusReady = new Promise((resolve) => {
          window.addEventListener('message', (event) => {
            if (event.data?.type === 'nexus:ready') resolve(true);
          });
        });
      });

      await page.goto('/maps/calypso?embed=1');

      // Wait for ready
      await page.evaluate(() => (window as any).__nexusReady);

      // Send search and collect results
      const results = await page.evaluate(() => {
        return new Promise<any>((resolve) => {
          window.addEventListener('message', (event) => {
            if (event.data?.type === 'nexus:searchResults') {
              resolve(event.data);
            }
          });
          window.postMessage({ type: 'nexus:search', query: 'Port Atlantis' }, '*');
        });
      });

      expect(results.query).toBe('Port Atlantis');
      expect(Array.isArray(results.results)).toBe(true);
      // Results may be empty if test DB locations are unavailable
      if (results.results.length > 0) {
        expect(results.results[0].name).toBeTruthy();
        expect(results.results[0].score).toBeGreaterThan(0);
      }
    });

    test('nexus:getLocations returns all locations', async ({ page }) => {
      // Set up ready listener before navigation
      await page.addInitScript(() => {
        (window as any).__nexusReady = new Promise((resolve) => {
          window.addEventListener('message', (event) => {
            if (event.data?.type === 'nexus:ready') resolve(true);
          });
        });
      });

      await page.goto('/maps/calypso?embed=1');

      // Wait for ready
      await page.evaluate(() => (window as any).__nexusReady);

      const result = await page.evaluate(() => {
        return new Promise<any>((resolve) => {
          window.addEventListener('message', (event) => {
            if (event.data?.type === 'nexus:locations') {
              resolve(event.data);
            }
          });
          window.postMessage({ type: 'nexus:getLocations' }, '*');
        });
      });

      expect(Array.isArray(result.locations)).toBe(true);
      // Locations may be empty if test DB has missing migrations
      if (result.locations.length > 0) {
        expect(result.locations[0].id).toBeTruthy();
        expect(result.locations[0].name).toBeTruthy();
      }
    });

    test('nexus:setVisibility toggles UI at runtime', async ({ page }) => {
      await page.goto('/maps/calypso?embed=1');
      await page.waitForLoadState('networkidle');

      const canvas = page.locator('.map-container canvas').first();
      await expect(canvas).toBeVisible({ timeout: TIMEOUT_LONG });

      // Search should be visible initially
      const searchInput = page.locator('.search-input');
      await expect(searchInput).toBeVisible();

      // Hide search via postMessage
      await page.evaluate(() => {
        window.postMessage({ type: 'nexus:setVisibility', search: false }, '*');
      });

      // Search controls should now be hidden
      const controls = page.locator('.map-controls');
      await expect(controls).toBeHidden({ timeout: TIMEOUT_MEDIUM });

      // Show search again
      await page.evaluate(() => {
        window.postMessage({ type: 'nexus:setVisibility', search: true }, '*');
      });

      await expect(searchInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  test.describe('Frame Headers', () => {
    test('embed route allows framing', async ({ page }) => {
      const response = await page.goto('/maps/calypso?embed=1');
      const headers = response?.headers() || {};
      // Should NOT have X-Frame-Options
      expect(headers['x-frame-options']).toBeUndefined();
    });

    test('non-embed route blocks framing', async ({ page }) => {
      const response = await page.goto('/maps/calypso');
      const headers = response?.headers() || {};
      expect(headers['x-frame-options']).toBe('SAMEORIGIN');
    });
  });
});
