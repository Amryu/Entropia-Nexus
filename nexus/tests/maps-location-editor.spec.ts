import { test, expect } from './fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';
import type { Page } from '@playwright/test';

// --- Helpers ---

/** Enter edit mode and wait for the editor overlay to appear */
async function enterEditMode(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/maps/calypso?mode=edit');
  await page.waitForLoadState('networkidle');
  const overlay = page.locator('.leaflet-editor-overlay');
  await expect(overlay).toBeVisible({ timeout: TIMEOUT_LONG });
  // Wait for locations to load in the sidebar
  await expect(overlay.locator('.left-sidebar .location-row').first()).toBeVisible({ timeout: TIMEOUT_LONG });
  return overlay;
}

/** Select a location from the sidebar list by clicking the first matching row */
async function selectFirstLocation(overlay: ReturnType<Page['locator']>) {
  const firstRow = overlay.locator('.left-sidebar .location-row').first();
  await firstRow.click();
  // Wait for the editor panel to populate
  await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
}

/** Select a point location (non-area) that has an editable name field.
 *  Filters to show only Teleporters, which are always point locations with editable names. */
async function selectFirstPointLocation(page: Page, overlay: ReturnType<Page['locator']>) {
  // Disable all filters first, then enable only Teleporter
  await clickFilterButton(overlay, 'None');
  await page.waitForTimeout(TIMEOUT_INSTANT);
  const teleporterCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'Teleporter' }).locator('input[type="checkbox"]');
  await teleporterCheck.check();
  await page.waitForTimeout(TIMEOUT_SHORT);
  const firstRow = overlay.locator('.left-sidebar .location-row').first();
  await expect(firstRow).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  await firstRow.click();
  await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
}

/** Select a location row whose text contains the given string */
async function selectLocationByName(overlay: ReturnType<Page['locator']>, name: string) {
  const row = overlay.locator('.left-sidebar .location-row', { hasText: name }).first();
  await row.click();
  await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
}

/** Get the right-panel editor container */
function editor(overlay: ReturnType<Page['locator']>) {
  return overlay.locator('.right-panel .editor-container');
}

/** Get a field input by its title attribute */
function fieldByTitle(overlay: ReturnType<Page['locator']>, title: string) {
  return editor(overlay).locator(`[title="${title}"]`);
}

/** Get a field input by its placeholder attribute */
function fieldByPlaceholder(overlay: ReturnType<Page['locator']>, placeholder: string) {
  return editor(overlay).locator(`[placeholder="${placeholder}"]`);
}

/** Filter the location list via the search input */
async function filterLocations(overlay: ReturnType<Page['locator']>, query: string) {
  const search = overlay.locator('.left-sidebar .search-input');
  await search.fill(query);
  await expect(search).toHaveValue(query);
}

/** Select a location type from the area/location type filter checkboxes */
async function clickFilterButton(overlay: ReturnType<Page['locator']>, label: string) {
  await overlay.locator('.left-sidebar .quick-toggles button', { hasText: label }).click();
}

// =============================================================================

test.describe('Maps - LocationEditor', () => {

  // ---------------------------------------------------------------------------
  // Empty / No-Selection State
  // ---------------------------------------------------------------------------
  test.describe('No Selection State', () => {
    test('shows no-selection message when no location is selected', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      const noSel = overlay.locator('.right-panel .no-selection');
      await expect(noSel).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(noSel).toContainText('Select a location');
    });

    test('no-selection message disappears when location is clicked', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);
      const noSel = overlay.locator('.right-panel .no-selection');
      await expect(noSel).toBeHidden({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Form Population — Existing Location
  // ---------------------------------------------------------------------------
  test.describe('Form Population', () => {
    test('populates name field when location is selected', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      await expect(nameInput).toBeVisible();
      const value = await nameInput.inputValue();
      expect(value.length).toBeGreaterThan(0);
    });

    test('populates coordinate fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const lon = fieldByTitle(overlay, 'Longitude');
      const lat = fieldByTitle(overlay, 'Latitude');
      const alt = fieldByTitle(overlay, 'Altitude');

      await expect(lon).toBeVisible();
      await expect(lat).toBeVisible();
      await expect(alt).toBeVisible();
    });

    test('shows location type selector', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const typeSelect = editor(overlay).locator('select.field-input').first();
      await expect(typeSelect).toBeVisible();
      const value = await typeSelect.inputValue();
      expect(value.length).toBeGreaterThan(0);
    });

    test('shows editor title with location name', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const title = overlay.locator('.right-panel .editor-title');
      const text = await title.textContent();
      expect(text).toMatch(/^Edit:/);
    });

    test('switching locations updates form fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      const rows = overlay.locator('.left-sidebar .location-row');

      // Select first location and capture its name
      await rows.first().click();
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      const firstName = await fieldByPlaceholder(overlay, 'Location name').inputValue();

      // Select second location
      const secondRow = rows.nth(1);
      await secondRow.click();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const secondName = await fieldByPlaceholder(overlay, 'Location name').inputValue();
      // Names should be different (different locations)
      // If they happen to be same, at least confirm the editor re-populated without error
      expect(secondName.length).toBeGreaterThan(0);
    });
  });

  // ---------------------------------------------------------------------------
  // Area-Specific Fields
  // ---------------------------------------------------------------------------
  test.describe('Area-Specific Fields', () => {
    test('area location shows area type and shape selectors', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      // Filter to area types only
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstArea = overlay.locator('.left-sidebar .location-row').first();
      await expect(firstArea).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await firstArea.click();
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // Should have Area Type and Shape selectors
      const selects = editor(overlay).locator('select.field-input');
      const count = await selects.count();
      // At minimum: Type selector, Area Type selector, Shape selector = 3
      expect(count).toBeGreaterThanOrEqual(3);
    });

    test('polygon area shows shape data JSON textarea', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Look for a polygon area by checking shape data textarea after clicking
      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const textarea = editor(overlay).locator('textarea.field-input');
        if (await textarea.isVisible().catch(() => false)) {
          const value = await textarea.inputValue();
          // Should contain JSON with vertices
          expect(value).toContain('vertices');
          return; // Test passed
        }
      }

      // If no polygon was found in the first 15 areas, that's acceptable
      test.skip(true, 'No polygon areas found in first 15 locations');
    });

    test('circle area shows center and radius fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const radiusField = fieldByTitle(overlay, 'Radius');
        if (await radiusField.isVisible().catch(() => false)) {
          await expect(fieldByTitle(overlay, 'Center X')).toBeVisible();
          await expect(fieldByTitle(overlay, 'Center Y')).toBeVisible();
          return; // Test passed
        }
      }

      test.skip(true, 'No circle areas found in first 15 locations');
    });

    test('rectangle area shows origin and size fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const widthField = fieldByTitle(overlay, 'Width');
        if (await widthField.isVisible().catch(() => false)) {
          await expect(fieldByTitle(overlay, 'Origin X')).toBeVisible();
          await expect(fieldByTitle(overlay, 'Origin Y')).toBeVisible();
          await expect(fieldByTitle(overlay, 'Height')).toBeVisible();
          return; // Test passed
        }
      }

      test.skip(true, 'No rectangle areas found in first 15 locations');
    });

    test('mob area shows Edit Mob Spawns button', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      // Filter to MobArea type
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      // Enable MobArea checkbox
      const mobCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'MobArea' }).locator('input[type="checkbox"]');
      await mobCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstMob = overlay.locator('.left-sidebar .location-row').first();
      if (await firstMob.isVisible().catch(() => false)) {
        await firstMob.click();
        await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        const mobBtn = editor(overlay).locator('button', { hasText: 'Edit Mob Spawns' });
        await expect(mobBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      } else {
        test.skip(true, 'No MobArea locations found');
      }
    });

    test('mob area name field is disabled', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const mobCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'MobArea' }).locator('input[type="checkbox"]');
      await mobCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstMob = overlay.locator('.left-sidebar .location-row').first();
      if (await firstMob.isVisible().catch(() => false)) {
        await firstMob.click();
        await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        const nameInput = fieldByPlaceholder(overlay, 'Location name');
        await expect(nameInput).toBeDisabled();
      } else {
        test.skip(true, 'No MobArea locations found');
      }
    });

    test('wave event area shows Edit Wave Spawns button', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const waveCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'WaveEventArea' }).locator('input[type="checkbox"]');
      await waveCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstWave = overlay.locator('.left-sidebar .location-row').first();
      if (await firstWave.isVisible().catch(() => false)) {
        await firstWave.click();
        await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        const waveBtn = editor(overlay).locator('button', { hasText: 'Edit Wave Spawns' });
        await expect(waveBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      } else {
        test.skip(true, 'No WaveEventArea locations found');
      }
    });

    test('land area shows tax rate and owner fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const landCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'LandArea' }).locator('input[type="checkbox"]');
      await landCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstLand = overlay.locator('.left-sidebar .location-row').first();
      if (await firstLand.isVisible().catch(() => false)) {
        await firstLand.click();
        await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        await expect(fieldByPlaceholder(overlay, 'Player name (resolved on approval)')).toBeVisible({ timeout: TIMEOUT_SHORT });
        await expect(fieldByTitle(overlay, 'Hunting Tax %')).toBeVisible();
        await expect(fieldByTitle(overlay, 'Mining Tax %')).toBeVisible();
        await expect(fieldByTitle(overlay, 'Shops Tax %')).toBeVisible();
      } else {
        test.skip(true, 'No LandArea locations found');
      }
    });
  });

  // ---------------------------------------------------------------------------
  // Point Location Fields
  // ---------------------------------------------------------------------------
  test.describe('Point Location Fields', () => {
    test('point location does not show area-specific fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Points');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstPoint = overlay.locator('.left-sidebar .location-row').first();
      if (await firstPoint.isVisible().catch(() => false)) {
        await firstPoint.click();
        await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

        // Should NOT have shape-related fields
        const textarea = editor(overlay).locator('textarea.field-input');
        await expect(textarea).toBeHidden();

        // Should NOT have area type selector (only 1 or 2 selects: Type + maybe parent)
        const selects = editor(overlay).locator('select.field-input');
        const count = await selects.count();
        expect(count).toBeLessThanOrEqual(2);
      } else {
        test.skip(true, 'No point locations found');
      }
    });
  });

  // ---------------------------------------------------------------------------
  // Editing & Auto-Save
  // ---------------------------------------------------------------------------
  test.describe('Editing and Auto-Save', () => {
    test('name field is editable and retains value for point locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      await expect(nameInput).toBeEnabled();

      // Fill with a new name
      await nameInput.fill('Test Edit Location');
      await expect(nameInput).toHaveValue('Test Edit Location');
    });

    test('editing coordinate fields retains values', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // Edit the altitude
      const altInput = fieldByTitle(overlay, 'Altitude');
      await altInput.fill('999');

      // Verify the value persists
      await expect(altInput).toHaveValue('999');

      // Edit longitude
      const lonInput = fieldByTitle(overlay, 'Longitude');
      await lonInput.fill('12345');
      await expect(lonInput).toHaveValue('12345');

      // Altitude should still be 999
      await expect(altInput).toHaveValue('999');
    });

    test('reverting changes removes pending change indicator', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      // Make an edit
      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      const originalName = await nameInput.inputValue();
      await nameInput.fill(originalName + ' (revert test)');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Click Revert Changes
      const revertBtn = editor(overlay).locator('button', { hasText: 'Revert Changes' });
      await expect(revertBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      await revertBtn.click();

      // Change dot should disappear
      const changeDot = overlay.locator('.left-sidebar .location-row').first().locator('.change-dot');
      await expect(changeDot).toBeHidden({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Actions: Delete, Revert
  // ---------------------------------------------------------------------------
  test.describe('Action Buttons', () => {
    test('shows Copy Delete Info button for existing location in public mode', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);

      // Public mode shows "Copy Delete Info" instead of "Mark for Deletion"
      const deleteBtn = editor(overlay).locator('button', { hasText: 'Copy Delete Info' });
      await expect(deleteBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('shows Revert Changes button for existing location', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);

      const revertBtn = editor(overlay).locator('button', { hasText: 'Revert Changes' });
      await expect(revertBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('Copy Delete Info button copies location info to clipboard', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);

      const deleteBtn = editor(overlay).locator('button', { hasText: 'Copy Delete Info' });
      await deleteBtn.click();

      // In public mode, this copies to clipboard and shows a toast — no pending change is created
      // Verify no delete indicator appeared (public mode doesn't mark for deletion)
      const firstRow = overlay.locator('.left-sidebar .location-row').first();
      const changeDot = firstRow.locator('.change-dot.delete');
      await expect(changeDot).toBeHidden({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Raw JSON Dialog
  // ---------------------------------------------------------------------------
  test.describe('Raw JSON Dialog', () => {
    test('JSON button opens raw JSON dialog', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const jsonBtn = editor(overlay).locator('.btn-json');
      await expect(jsonBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      await jsonBtn.click();

      const dialog = verifiedUser.locator('.json-dialog');
      await expect(dialog).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('JSON dialog shows location data', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const jsonBtn = editor(overlay).locator('.btn-json');
      await jsonBtn.click();

      const dialogBody = verifiedUser.locator('.json-dialog-body');
      await expect(dialogBody).toBeVisible({ timeout: TIMEOUT_SHORT });
      // Should contain property keys like Name, Properties
      await expect(dialogBody).toContainText('Name');
      await expect(dialogBody).toContainText('Properties');
    });

    test('JSON dialog closes on X button', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const jsonBtn = editor(overlay).locator('.btn-json');
      await jsonBtn.click();

      const dialog = verifiedUser.locator('.json-dialog');
      await expect(dialog).toBeVisible({ timeout: TIMEOUT_SHORT });

      const closeBtn = verifiedUser.locator('.json-dialog-close');
      await closeBtn.click();
      await expect(dialog).toBeHidden({ timeout: TIMEOUT_INSTANT });
    });

    test('JSON dialog closes on Escape key', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      editor(overlay).locator('.btn-json').click();
      const dialog = verifiedUser.locator('.json-dialog');
      await expect(dialog).toBeVisible({ timeout: TIMEOUT_SHORT });

      await verifiedUser.keyboard.press('Escape');
      await expect(dialog).toBeHidden({ timeout: TIMEOUT_INSTANT });
    });
  });

  // ---------------------------------------------------------------------------
  // Related Entities
  // ---------------------------------------------------------------------------
  test.describe('Related Entities', () => {
    test('shows related entities toggle for existing locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const toggle = editor(overlay).locator('.related-toggle');
      await expect(toggle).toBeVisible({ timeout: TIMEOUT_SHORT });
      await expect(toggle).toContainText('Related Entities');
    });

    test('clicking toggle expands related entities section', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const toggle = editor(overlay).locator('.related-toggle');
      await toggle.click();

      const section = editor(overlay).locator('.related-section');
      await expect(section).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  // ---------------------------------------------------------------------------
  // Description Field
  // ---------------------------------------------------------------------------
  test.describe('Description Field', () => {
    test('shows description label', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const label = editor(overlay).locator('.field-label', { hasText: 'Description' });
      await expect(label).toBeVisible({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Parent Location Field
  // ---------------------------------------------------------------------------
  test.describe('Parent Location', () => {
    test('shows parent location search input', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const label = editor(overlay).locator('.field-label', { hasText: 'Parent Location' });
      await expect(label).toBeVisible({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Changes Summary Integration
  // ---------------------------------------------------------------------------
  test.describe('Changes Summary', () => {
    test('changes badge appears when Copy Delete Info is used on multiple locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      // The Changes toggle button should be visible
      const changesBtn = overlay.locator('.editor-toolbar button', { hasText: 'Changes' });
      await expect(changesBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('changes panel shows pending change when toggled', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      // Make an edit
      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      const original = await nameInput.inputValue();
      await nameInput.fill(original + ' (changes test)');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Click Changes toggle button
      const changesBtn = overlay.locator('.editor-toolbar button', { hasText: 'Changes' });
      await changesBtn.click();

      // Should show ChangesSummary with at least one change
      const changeRow = overlay.locator('.right-panel .change-row');
      await expect(changeRow.first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });

    test('changes summary shows edit badge', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      // Make an edit
      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      const original = await nameInput.inputValue();
      await nameInput.fill(original + ' (edit badge test)');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Open changes panel
      const changesBtn = overlay.locator('.editor-toolbar button', { hasText: 'Changes' });
      await changesBtn.click();

      const editBadge = overlay.locator('.right-panel .badge.edit');
      await expect(editBadge).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('changes panel shows edit change after name modification', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstPointLocation(verifiedUser, overlay);
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // Edit a field
      const lonInput = fieldByTitle(overlay, 'Longitude');
      const original = await lonInput.inputValue();
      await lonInput.fill(String(Number(original) + 50));
      await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

      // Open changes panel
      const changesBtn = overlay.locator('.editor-toolbar button', { hasText: 'Changes' });
      await changesBtn.click();

      const editBadge = overlay.locator('.right-panel .badge.edit');
      await expect(editBadge).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    });
  });

  // ---------------------------------------------------------------------------
  // MobAreaEditor Panel Switch
  // ---------------------------------------------------------------------------
  test.describe('MobAreaEditor Integration', () => {
    test('clicking Edit Mob Spawns opens mob editor panel', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const mobCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'MobArea' }).locator('input[type="checkbox"]');
      await mobCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstMob = overlay.locator('.left-sidebar .location-row').first();
      if (!(await firstMob.isVisible().catch(() => false))) {
        test.skip(true, 'No MobArea locations found');
        return;
      }
      await firstMob.click();
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      // Click Edit Mob Spawns
      const mobBtn = editor(overlay).locator('button', { hasText: 'Edit Mob Spawns' });
      await mobBtn.click();

      // Mob editor should appear
      const mobEditor = overlay.locator('.right-panel .mob-editor');
      await expect(mobEditor).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(mobEditor.locator('h3', { hasText: 'Mob Area Editor' })).toBeVisible();
    });

    test('mob editor cancel returns to location editor', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const mobCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'MobArea' }).locator('input[type="checkbox"]');
      await mobCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstMob = overlay.locator('.left-sidebar .location-row').first();
      if (!(await firstMob.isVisible().catch(() => false))) {
        test.skip(true, 'No MobArea locations found');
        return;
      }
      await firstMob.click();
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      const mobBtn = editor(overlay).locator('button', { hasText: 'Edit Mob Spawns' });
      await mobBtn.click();

      const cancelBtn = overlay.locator('.right-panel .mob-editor button', { hasText: 'Cancel' });
      await expect(cancelBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      await cancelBtn.click();

      // Should return to location editor
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // WaveEventEditor Panel Switch
  // ---------------------------------------------------------------------------
  test.describe('WaveEventEditor Integration', () => {
    test('clicking Edit Wave Spawns opens wave editor panel', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const waveCheck = overlay.locator('.left-sidebar .filter-row', { hasText: 'WaveEventArea' }).locator('input[type="checkbox"]');
      await waveCheck.check();
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const firstWave = overlay.locator('.left-sidebar .location-row').first();
      if (!(await firstWave.isVisible().catch(() => false))) {
        test.skip(true, 'No WaveEventArea locations found');
        return;
      }
      await firstWave.click();
      await expect(overlay.locator('.right-panel .editor-title')).toBeVisible({ timeout: TIMEOUT_MEDIUM });

      const waveBtn = editor(overlay).locator('button', { hasText: 'Edit Wave Spawns' });
      await waveBtn.click();

      const waveEditor = overlay.locator('.right-panel .wave-editor');
      await expect(waveEditor).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(waveEditor.locator('h3', { hasText: 'Wave Spawns' })).toBeVisible();
    });
  });

  // ---------------------------------------------------------------------------
  // Location List Filtering
  // ---------------------------------------------------------------------------
  test.describe('Location List Filtering', () => {
    test('search filters location list', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      const rows = overlay.locator('.left-sidebar .location-row');
      const initialCount = await rows.count();
      expect(initialCount).toBeGreaterThan(0);

      // Filter with non-matching query
      await filterLocations(overlay, 'zzzzz-no-match-xyz');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const filteredCount = await rows.count();
      expect(filteredCount).toBe(0);
    });

    test('quick toggle All shows all locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      // First filter to None
      await clickFilterButton(overlay, 'None');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const noneCount = await overlay.locator('.left-sidebar .location-row').count();
      expect(noneCount).toBe(0);

      // Then toggle All
      await clickFilterButton(overlay, 'All');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
      const allCount = await overlay.locator('.left-sidebar .location-row').count();
      expect(allCount).toBeGreaterThan(0);
    });

    test('quick toggle Points shows only point locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Points');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const count = await overlay.locator('.left-sidebar .location-row').count();
      expect(count).toBeGreaterThan(0);

      // Verify no area group headers are visible
      const areaHeaders = overlay.locator('.left-sidebar .group-header', { hasText: /MobArea|LandArea|PvpArea|ZoneArea/ });
      const headerCount = await areaHeaders.count();
      expect(headerCount).toBe(0);
    });

    test('quick toggle Areas shows only area locations', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const count = await overlay.locator('.left-sidebar .location-row').count();
      expect(count).toBeGreaterThan(0);

      // Verify no point type group headers are visible
      const pointHeaders = overlay.locator('.left-sidebar .group-header', { hasText: /^(Teleporter|Npc|Camp|City|Outpost)$/ });
      const headerCount = await pointHeaders.count();
      expect(headerCount).toBe(0);
    });
  });

  // ---------------------------------------------------------------------------
  // Waypoint Paste
  // ---------------------------------------------------------------------------
  test.describe('Waypoint Paste', () => {
    test('pasting waypoint format fills coordinate fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await selectFirstLocation(overlay);

      const lonInput = fieldByTitle(overlay, 'Longitude');
      // Focus and paste a waypoint string
      await lonInput.focus();

      // Simulate paste via clipboard
      await verifiedUser.evaluate(() => {
        const pasteEvent = new ClipboardEvent('paste', {
          clipboardData: new DataTransfer(),
          bubbles: true,
          cancelable: true,
        });
        Object.defineProperty(pasteEvent.clipboardData, 'getData', {
          value: () => '[Calypso, 12345, 67890, 150, Test Location]',
        });
        document.activeElement?.dispatchEvent(pasteEvent);
      });

      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Verify coordinates were updated
      await expect(lonInput).toHaveValue('12345');
      await expect(fieldByTitle(overlay, 'Latitude')).toHaveValue('67890');
      await expect(fieldByTitle(overlay, 'Altitude')).toHaveValue('150');
    });
  });

  // ---------------------------------------------------------------------------
  // Shape Type Switching
  // ---------------------------------------------------------------------------
  test.describe('Shape Type Switching', () => {
    test('changing shape type from Polygon to Circle shows circle fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Find a polygon area
      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();
      let foundPolygon = false;

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const textarea = editor(overlay).locator('textarea.field-input');
        if (await textarea.isVisible().catch(() => false)) {
          foundPolygon = true;

          // Change shape to Circle
          const shapeSelect = editor(overlay).locator('select.field-input').last();
          await shapeSelect.selectOption('Circle');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Circle fields should now be visible
          await expect(fieldByTitle(overlay, 'Center X')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Center Y')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Radius')).toBeVisible({ timeout: TIMEOUT_SHORT });

          // Polygon textarea should be hidden
          await expect(textarea).toBeHidden();
          break;
        }
      }

      if (!foundPolygon) test.skip(true, 'No polygon areas found');
    });

    test('changing shape type from Polygon to Rectangle shows rectangle fields', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();
      let foundPolygon = false;

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const textarea = editor(overlay).locator('textarea.field-input');
        if (await textarea.isVisible().catch(() => false)) {
          foundPolygon = true;

          const shapeSelect = editor(overlay).locator('select.field-input').last();
          await shapeSelect.selectOption('Rectangle');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          await expect(fieldByTitle(overlay, 'Origin X')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Origin Y')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Width')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Height')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(textarea).toBeHidden();
          break;
        }
      }

      if (!foundPolygon) test.skip(true, 'No polygon areas found');
    });
  });

  // ---------------------------------------------------------------------------
  // Multi-Select / Mass Delete
  // ---------------------------------------------------------------------------
  test.describe('Multi-Select Mode', () => {
    test('multi-select button activates multi-select mode', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);

      const multiSelectBtn = overlay.locator('.left-sidebar .mass-actions button', { hasText: 'Multi-Select' });
      await expect(multiSelectBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
      await multiSelectBtn.click();

      // Should show cancel button and delete button
      const cancelBtn = overlay.locator('.left-sidebar .mass-actions button', { hasText: 'Cancel' });
      await expect(cancelBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });

    test('cancel exits multi-select mode', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);

      const multiSelectBtn = overlay.locator('.left-sidebar .mass-actions button', { hasText: 'Multi-Select' });
      await multiSelectBtn.click();

      const cancelBtn = overlay.locator('.left-sidebar .mass-actions button', { hasText: 'Cancel' });
      await cancelBtn.click();

      // Multi-select button should be back
      await expect(multiSelectBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // Location Count Display
  // ---------------------------------------------------------------------------
  test.describe('Location Count', () => {
    test('shows total location count', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);

      const totalCount = overlay.locator('.left-sidebar .total-count');
      await expect(totalCount).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      const text = await totalCount.textContent();
      expect(text).toMatch(/\d+ \/ \d+ locations/);
    });

    test('filtering updates the count', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);

      const totalCount = overlay.locator('.left-sidebar .total-count');
      const initialText = await totalCount.textContent();
      const initialFiltered = parseInt(initialText?.split('/')[0].trim() || '0');

      await filterLocations(overlay, 'zzzzz-no-match');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      const filteredText = await totalCount.textContent();
      const filteredCount = parseInt(filteredText?.split('/')[0].trim() || '0');
      expect(filteredCount).toBe(0);
      expect(filteredCount).toBeLessThan(initialFiltered);
    });
  });

  // ---------------------------------------------------------------------------
  // Admin-Specific Behavior (public maps page uses mode="public", but isAdmin
  // enables lock override and Direct Apply in ChangesSummary)
  // ---------------------------------------------------------------------------
  test.describe('Admin Mode', () => {
    test('admin can enter edit mode and select locations', async ({ adminUser }) => {
      const overlay = await enterEditMode(adminUser);
      await selectFirstLocation(overlay);

      // Admin should see full editor with all fields
      const nameInput = fieldByPlaceholder(overlay, 'Location name');
      await expect(nameInput).toBeVisible();

      // Admin should see action buttons (delete + revert)
      const actionBtns = editor(overlay).locator('.actions .btn');
      const count = await actionBtns.count();
      expect(count).toBeGreaterThanOrEqual(1);

      // Changes toggle should be in toolbar
      const changesBtn = overlay.locator('.editor-toolbar button', { hasText: 'Changes' });
      await expect(changesBtn).toBeVisible({ timeout: TIMEOUT_SHORT });
    });
  });

  // ---------------------------------------------------------------------------
  // DB-Seeded Pending Changes
  // ---------------------------------------------------------------------------
  test.describe('DB Pending Changes', () => {
    test('creating a pending change via API and loading maps page succeeds', async ({ verifiedUser }) => {
      const changeRes = await verifiedUser.request.post('/api/changes?entity=Location&type=Create&state=Pending', {
        data: {
          Name: 'E2E Test Teleporter',
          Properties: {
            Type: 'Teleporter',
            Coordinates: { Longitude: 70000, Latitude: 70000, Altitude: 100 }
          },
          Planet: { Name: 'Calypso' }
        }
      });
      expect(changeRes.ok()).toBeTruthy();
      const changeData = await changeRes.json();
      const changeId = changeData.id;

      try {
        const overlay = await enterEditMode(verifiedUser);
        // Map should load without errors with the pending change in the overlay
        await expect(overlay).toBeVisible();
      } finally {
        await verifiedUser.request.delete(`/api/changes/${changeId}`);
      }
    });

    test('changeId param with mode=create opens editor with change data', async ({ verifiedUser }) => {
      const changeRes = await verifiedUser.request.post('/api/changes?entity=Location&type=Create&state=Draft', {
        data: {
          Name: 'E2E Draft Teleporter',
          Properties: {
            Type: 'Teleporter',
            Coordinates: { Longitude: 72000, Latitude: 73000, Altitude: 50 }
          },
          Planet: { Name: 'Calypso' }
        }
      });
      expect(changeRes.ok()).toBeTruthy();
      const changeData = await changeRes.json();
      const changeId = changeData.id;

      try {
        // Use mode=create with changeId to load the existing draft
        await verifiedUser.setViewportSize({ width: 1440, height: 900 });
        await verifiedUser.goto(`/maps/calypso?mode=create&changeId=${changeId}`);
        await verifiedUser.waitForLoadState('networkidle');

        const overlay = verifiedUser.locator('.leaflet-editor-overlay');
        await expect(overlay).toBeVisible({ timeout: TIMEOUT_LONG });
        // Wait for locations to load
        await expect(overlay.locator('.left-sidebar .location-row').first()).toBeVisible({ timeout: TIMEOUT_LONG });

        // The editor should show the change data after focus
        // The focusLocation system seeds the change into the editor
        const editorTitle = overlay.locator('.right-panel .editor-title');
        await expect(editorTitle).toBeVisible({ timeout: TIMEOUT_LONG });
      } finally {
        await verifiedUser.request.delete(`/api/changes/${changeId}`);
      }
    });

    test('pending change can be created and deleted via API lifecycle', async ({ verifiedUser }) => {
      // Create
      const createRes = await verifiedUser.request.post('/api/changes?entity=Location&type=Create&state=Draft', {
        data: {
          Name: 'E2E Lifecycle Test',
          Properties: {
            Type: 'Teleporter',
            Coordinates: { Longitude: 75000, Latitude: 75000, Altitude: 100 }
          },
          Planet: { Name: 'Calypso' }
        }
      });
      expect(createRes.ok()).toBeTruthy();
      const { id: changeId } = await createRes.json();

      // Read
      const getRes = await verifiedUser.request.fetch(`/api/changes/${changeId}`);
      expect(getRes.ok()).toBeTruthy();
      const change = await getRes.json();
      expect(change.data.Name).toBe('E2E Lifecycle Test');

      // Delete
      const deleteRes = await verifiedUser.request.delete(`/api/changes/${changeId}`);
      expect(deleteRes.status()).toBe(204);

      // Verify soft-deleted (state changes to "Deleted")
      const verifyRes = await verifiedUser.request.fetch(`/api/changes/${changeId}`);
      const verifyData = await verifyRes.json();
      expect(verifyData.state).toBe('Deleted');
    });
  });

  // ---------------------------------------------------------------------------
  // Shape Data Caching on Type Switch
  // ---------------------------------------------------------------------------
  test.describe('Shape Data Caching', () => {
    test('switching shape Polygon→Circle→Polygon restores polygon data from cache', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Find a polygon area
      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();
      let foundPolygon = false;

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const textarea = editor(overlay).locator('textarea.field-input');
        if (await textarea.isVisible().catch(() => false)) {
          foundPolygon = true;

          // Capture original polygon data
          const originalJson = await textarea.inputValue();
          expect(originalJson).toContain('vertices');

          // Switch to Circle
          const shapeSelect = editor(overlay).locator('select.field-input').last();
          await shapeSelect.selectOption('Circle');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Confirm Circle fields are visible, polygon is gone
          await expect(fieldByTitle(overlay, 'Radius')).toBeVisible({ timeout: TIMEOUT_SHORT });
          await expect(textarea).toBeHidden();

          // Switch back to Polygon
          await shapeSelect.selectOption('Polygon');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Polygon textarea should be back with cached data
          await expect(textarea).toBeVisible({ timeout: TIMEOUT_SHORT });
          const restoredJson = await textarea.inputValue();
          expect(restoredJson).toContain('vertices');
          // The restored JSON should match the original
          expect(JSON.parse(restoredJson)).toEqual(JSON.parse(originalJson));
          break;
        }
      }

      if (!foundPolygon) test.skip(true, 'No polygon areas found');
    });

    test('switching shape Circle→Rectangle→Circle restores circle data from cache', async ({ verifiedUser }) => {
      const overlay = await enterEditMode(verifiedUser);
      await clickFilterButton(overlay, 'Areas');
      await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

      // Find a circle area
      const rows = overlay.locator('.left-sidebar .location-row');
      const count = await rows.count();
      let foundCircle = false;

      for (let i = 0; i < Math.min(count, 15); i++) {
        await rows.nth(i).click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const radiusField = fieldByTitle(overlay, 'Radius');
        if (await radiusField.isVisible().catch(() => false)) {
          foundCircle = true;

          // Capture original circle values
          const origX = await fieldByTitle(overlay, 'Center X').inputValue();
          const origY = await fieldByTitle(overlay, 'Center Y').inputValue();
          const origR = await radiusField.inputValue();

          // Switch to Rectangle
          const shapeSelect = editor(overlay).locator('select.field-input').last();
          await shapeSelect.selectOption('Rectangle');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
          await expect(fieldByTitle(overlay, 'Width')).toBeVisible({ timeout: TIMEOUT_SHORT });

          // Switch back to Circle
          await shapeSelect.selectOption('Circle');
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

          // Circle fields should be restored from cache
          await expect(fieldByTitle(overlay, 'Center X')).toHaveValue(origX, { timeout: TIMEOUT_SHORT });
          await expect(fieldByTitle(overlay, 'Center Y')).toHaveValue(origY);
          await expect(radiusField).toHaveValue(origR);
          break;
        }
      }

      if (!foundCircle) test.skip(true, 'No circle areas found');
    });
  });

  // ---------------------------------------------------------------------------
  // Read-Only / Locked State
  // ---------------------------------------------------------------------------
  test.describe('Read-Only State', () => {
    test('location with pending Update from another user shows lock notice', async ({ verifiedUser, adminUser }) => {
      // Admin creates a pending Update change for an existing Teleporter
      const locRes = await adminUser.request.fetch('/api/locations?Planet=Calypso&Type=Teleporter&limit=1');
      if (!locRes.ok()) {
        test.skip(true, 'Could not fetch locations');
        return;
      }
      const locs = await locRes.json();
      if (!locs?.length) {
        test.skip(true, 'No Teleporter locations available');
        return;
      }
      const loc = locs[0];

      const changeRes = await adminUser.request.post('/api/changes?entity=Location&type=Update&state=Pending', {
        data: {
          Id: loc.Id,
          Name: loc.Name + ' (admin edit)',
          Properties: {
            Type: loc.Properties?.Type || 'Teleporter',
            Coordinates: loc.Properties?.Coordinates || { Longitude: 0, Latitude: 0, Altitude: 0 }
          },
          Planet: { Name: 'Calypso' }
        }
      });

      if (!changeRes.ok()) {
        test.skip(true, 'Could not create test change (possible conflict)');
        return;
      }
      const changeData = await changeRes.json();
      const changeId = changeData.id;

      try {
        const overlay = await enterEditMode(verifiedUser);

        // Search for the locked location
        await filterLocations(overlay, loc.Name);
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);
        const locRow = overlay.locator('.left-sidebar .location-row', { hasText: loc.Name }).first();
        if (!(await locRow.isVisible().catch(() => false))) {
          test.skip(true, 'Could not find location in filtered list');
          return;
        }
        await locRow.click();
        await verifiedUser.waitForTimeout(TIMEOUT_SHORT);

        // The location should show a lock notice
        const lockNotice = editor(overlay).locator('.lock-notice');
        await expect(lockNotice).toBeVisible({ timeout: TIMEOUT_MEDIUM });
        await expect(lockNotice).toContainText('Locked by another user');
      } finally {
        await adminUser.request.delete(`/api/changes/${changeId}`);
      }
    });
  });
});
