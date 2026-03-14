import { test, expect } from './fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Maps Page', () => {
  test.describe('Public View', () => {
    test('loads maps page successfully', async ({ page }) => {
      await page.goto('/maps/calypso');
      await page.waitForLoadState('networkidle');

      // Should have a map container
      const mapContainer = page.locator('.map-container, canvas, .map-wrapper').first();
      await expect(mapContainer).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('anonymous user does not see edit mode button', async ({ page }) => {
      await page.goto('/maps/calypso');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_SHORT);

      const editBtn = page.locator('.edit-mode-btn');
      await expect(editBtn).toBeHidden();
    });

    test('unverified user does not see edit mode button', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/maps/calypso');
      await unverifiedUser.waitForLoadState('networkidle');
      await unverifiedUser.waitForTimeout(TIMEOUT_SHORT);

      const editBtn = unverifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeHidden();
    });
  });

  test.describe('Edit Mode Button', () => {
    test('verified user sees edit mode button on desktop', async ({ verifiedUser }) => {
      // Ensure desktop viewport
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('edit mode button is hidden on mobile viewport', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 375, height: 667 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeHidden();
    });
  });

  test.describe('Edit Mode', () => {
    test('mode=edit opens Leaflet editor automatically', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso?mode=edit');
      await verifiedUser.waitForLoadState('networkidle');

      const overlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(overlay).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('mode=create opens Leaflet editor automatically', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso?mode=create');
      await verifiedUser.waitForLoadState('networkidle');

      const overlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(overlay).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('clicking edit mode button opens Leaflet editor overlay', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      // Editor overlay should appear
      const overlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(overlay).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('editor overlay has toolbar with exit button', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      const toolbar = verifiedUser.locator('.editor-toolbar');
      await expect(toolbar).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      const exitBtn = toolbar.locator('button', { hasText: 'Exit Edit Mode' });
      await expect(exitBtn).toBeVisible();
    });

    test('editor overlay has three-column layout', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      const overlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(overlay).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      const leftSidebar = overlay.locator('.left-sidebar');
      const mapArea = overlay.locator('.map-area');
      const rightPanel = overlay.locator('.right-panel');

      await expect(leftSidebar).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(mapArea).toBeVisible();
      await expect(rightPanel).toBeVisible();
    });

    test('exiting edit mode returns to normal view', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      const overlay = verifiedUser.locator('.leaflet-editor-overlay');
      await expect(overlay).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // Click exit button
      const exitBtn = verifiedUser.locator('.editor-toolbar button', { hasText: 'Exit Edit Mode' });
      await exitBtn.click();

      // Overlay should be hidden
      await expect(overlay).toBeHidden({ timeout: TIMEOUT_SHORT });

      // Edit mode button should be visible again
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('editor shows no-selection message before selecting location', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      const noSelection = verifiedUser.locator('.leaflet-editor-overlay .no-selection');
      await expect(noSelection).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('editor toolbar shows changes summary toggle', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 1280, height: 800 });
      await verifiedUser.goto('/maps/calypso');
      await verifiedUser.waitForLoadState('networkidle');

      const editBtn = verifiedUser.locator('.edit-mode-btn');
      await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await editBtn.click();

      const changesToggle = verifiedUser.locator('.editor-toolbar button', { hasText: 'Changes' });
      await expect(changesToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('pending edits stay visible with state-colored edges even when search filter hides list items', async ({ verifiedUser }) => {
      // Create a pending area change via API so the map overlay has a known edit
      const changeRes = await verifiedUser.request.post('/api/changes?entity=Location&type=Create&state=Pending', {
        data: {
          Name: 'E2E Pending Visibility Test',
          Properties: {
            Type: 'Area',
            AreaType: 'MobArea',
            Shape: 'Polygon',
            Data: { vertices: [60000, 60000, 61000, 60000, 61000, 61000, 60000, 61000, 60000, 60000] },
            Coordinates: { Longitude: 60500, Latitude: 60500, Altitude: 100 }
          },
          Planet: { Name: 'Calypso' }
        }
      });
      expect(changeRes.ok()).toBeTruthy();
      const changeData = await changeRes.json();
      const changeId = changeData.id;

      try {
        await verifiedUser.setViewportSize({ width: 1280, height: 800 });
        await verifiedUser.goto('/maps/calypso');
        await verifiedUser.waitForLoadState('networkidle');

        const editBtn = verifiedUser.locator('.edit-mode-btn');
        await expect(editBtn).toBeVisible({ timeout: TIMEOUT_LONG });
        await editBtn.click();

        const overlay = verifiedUser.locator('.leaflet-editor-overlay');
        await expect(overlay).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        // Wait for locations to load in the sidebar
        const firstLocation = overlay.locator('.left-sidebar .location-row').first();
        await expect(firstLocation).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        // Wait for DB pending changes overlay shapes to render (SVG paths with dashed stroke)
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // Filter the list so no locations match — pending overlay shapes should remain visible
        const listSearch = overlay.locator('.left-sidebar .search-input');
        await listSearch.fill('zzzzzz-no-match');
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // The DB pending change overlay should still render shapes on the map.
        // Leaflet sets stroke via inline style; getComputedStyle returns rgb() format.
        // Check for any SVG path with a pending-change stroke color or dash pattern.
        const hasOverlayShape = await verifiedUser.locator('.leaflet-overlay-pane path').evaluateAll((paths) => {
          return paths.some((pathEl) => {
            const style = pathEl.style;
            const computedStroke = getComputedStyle(pathEl).stroke || '';
            const attrStroke = pathEl.getAttribute('stroke') || '';
            const inlineStroke = style.stroke || '';
            const strokeDashArray = style.strokeDasharray || getComputedStyle(pathEl).strokeDasharray || '';
            const allStrokes = [computedStroke, attrStroke, inlineStroke]
              .map(s => s.trim().toLowerCase())
              .filter(Boolean);
            // Green for Create changes, amber for Edit changes
            const pendingColors = [
              'rgb(34, 197, 94)', '#22c55e',
              'rgb(245, 158, 11)', '#f59e0b',
              'rgb(239, 68, 68)', '#ef4444'
            ];
            const hasColor = allStrokes.some(s => pendingColors.includes(s));
            // Also match shapes with dashed borders (pending change indicator)
            const hasDash = strokeDashArray && strokeDashArray !== 'none' && strokeDashArray !== '0';
            return hasColor || hasDash;
          });
        });

        expect(hasOverlayShape).toBeTruthy();
      } finally {
        await verifiedUser.request.delete(`/api/changes/${changeId}`);
      }
    });
  });
});
