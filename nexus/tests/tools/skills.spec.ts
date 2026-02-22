import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

// Skills Calculator is gated behind admin-only access (see tools/skills/+layout.server.js).
// These tests are written for public user access and will fail until the feature is ungated.
test.describe.skip('Skills Calculator', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
  });

  test('page loads successfully', async ({ page }) => {
    await page.goto('/tools/skills');
    await expect(page).toHaveTitle(/Skills Calculator/i);
    await expect(page.locator('h1')).toContainText('Skills Calculator');
  });

  test('shows empty state when no skills imported', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Summary should show 0 values
    await expect(page.locator('.summary-value').first()).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Skills list should show empty message
    await expect(page.locator('.list-empty')).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('can switch between skills and professions tabs', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Default tab is Skills
    await expect(page.locator('.tab-btn.active')).toContainText('Skills');

    // Switch to professions
    await page.locator('.tab-btn', { hasText: 'Professions' }).click();
    await expect(page.locator('.tab-btn.active')).toContainText('Professions');
  });

  test('can open and close import dialog', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Open import dialog
    await page.getByRole('button', { name: 'Import' }).click();
    await expect(page.locator('.dialog')).toBeVisible({ timeout: TIMEOUT_INSTANT });
    await expect(page.locator('.import-textarea')).toBeVisible();

    // Close dialog
    await page.locator('.dialog-close').click();
    await expect(page.locator('.dialog')).not.toBeVisible({ timeout: TIMEOUT_INSTANT });
  });

  test('can import external format skills', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    const testData = JSON.stringify({
      "agility": 0.5,
      "electrokinesis": 10.25,
      "concentration": 5.0,
      "health": 88.18
    });

    // Open import dialog and paste data
    await page.getByRole('button', { name: 'Import' }).click();
    await page.locator('.import-textarea').fill(testData);
    await page.getByRole('button', { name: 'Preview' }).click();

    // Should show preview
    await expect(page.locator('.import-preview')).toBeVisible({ timeout: TIMEOUT_SHORT });
    await expect(page.locator('.preview-stats')).toContainText('external');

    // Confirm import
    await page.getByRole('button', { name: 'Confirm Import' }).click();
    await expect(page.locator('.dialog')).not.toBeVisible({ timeout: TIMEOUT_SHORT });

    // Skills should now be populated in the list
    await expect(page.locator('.list-item', { hasText: 'Electrokinesis' })).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('calculates profession levels after import', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Import some skills relevant to Electro Kinetic (Hit)
    const testData = JSON.stringify({
      "electrokinesis": 1000,
      "concentration": 500,
      "power-catalyst": 200
    });

    await page.getByRole('button', { name: 'Import' }).click();
    await page.locator('.import-textarea').fill(testData);
    await page.getByRole('button', { name: 'Preview' }).click();
    await page.getByRole('button', { name: 'Confirm Import' }).click();

    // Switch to professions tab
    await page.locator('.tab-btn', { hasText: 'Professions' }).click();
    await expect(page.locator('.list-item').first()).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should have profession levels > 0
    const firstLevel = await page.locator('.list-item .item-value').first().textContent();
    expect(parseFloat(firstLevel || '0')).toBeGreaterThan(0);
  });

  test('can navigate from skill to profession detail', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Import skills
    const testData = JSON.stringify({ "electrokinesis": 100 });
    await page.getByRole('button', { name: 'Import' }).click();
    await page.locator('.import-textarea').fill(testData);
    await page.getByRole('button', { name: 'Preview' }).click();
    await page.getByRole('button', { name: 'Confirm Import' }).click();

    // Click on Electrokinesis skill
    await page.locator('.list-item', { hasText: 'Electrokinesis' }).click();
    await expect(page.locator('.detail-header h2')).toContainText('Electrokinesis', { timeout: TIMEOUT_SHORT });

    // Should show professions affected
    await expect(page.locator('.detail-section h3', { hasText: 'Professions Affected' })).toBeVisible();

    // Click on a profession to navigate
    await page.locator('.detail-table-row.clickable').first().click();
    await expect(page.locator('.tab-btn.active')).toContainText('Professions');
  });

  test('optimizer panel toggles', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Optimizer should be collapsed by default
    await expect(page.locator('.optimizer-content')).not.toBeVisible();

    // Toggle open
    await page.locator('.optimizer-toggle').click();
    await expect(page.locator('.optimizer-content')).toBeVisible({ timeout: TIMEOUT_INSTANT });

    // Should show target profession dropdown
    await expect(page.locator('#target-prof')).toBeVisible();
  });

  test('shows zero-value toggle filter', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Check "0s" checkbox to show all skills
    await page.locator('.zero-toggle input').check();

    // Should now show skills with 0 values
    const items = await page.locator('.list-item').count();
    expect(items).toBeGreaterThan(0);
  });

  test('search filters skills', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Show all skills first
    await page.locator('.zero-toggle input').check();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    const initialCount = await page.locator('.list-item').count();

    // Search for "electro"
    await page.locator('.search-input').fill('electro');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    const filteredCount = await page.locator('.list-item').count();
    expect(filteredCount).toBeLessThan(initialCount);
    expect(filteredCount).toBeGreaterThan(0);
  });
});

test.describe.skip('Skills Calculator - Authenticated', () => {
  test('shows online/local toggle for logged-in users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/tools/skills');
    await verifiedUser.waitForLoadState('networkidle');

    await expect(verifiedUser.locator('.source-toggle')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(verifiedUser.locator('.toggle-btn', { hasText: 'Online' })).toBeVisible();
    await expect(verifiedUser.locator('.toggle-btn', { hasText: 'Local' })).toBeVisible();
  });

  test('does not show online/local toggle for anonymous users', async ({ page }) => {
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.source-toggle')).not.toBeVisible();
  });
});

test.describe.skip('Skills Calculator - Unlocks System', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/tools/skills');
    await page.waitForLoadState('networkidle');

    // Show all skills (including 0-value)
    await page.locator('.zero-toggle input').check();
    await page.waitForTimeout(TIMEOUT_INSTANT);
  });

  test('shows unlocks remaining count for hidden skills', async ({ page }) => {
    // Should show "Unlocks remaining" stat in summary bar
    const unlocksLabel = page.locator('.summary-item', { hasText: 'Unlocks remaining' });
    await expect(unlocksLabel).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Value should be > 0 (all hidden skills at 0 when nothing imported)
    const count = await unlocksLabel.locator('.summary-value').textContent();
    expect(parseInt(count || '0')).toBeGreaterThan(0);
  });

  test('hidden skills show lock/unlock icon in sidebar', async ({ page }) => {
    // Hidden skills should have an unlock button in the sidebar
    const unlockBtns = page.locator('.sidebar-unlock');
    await expect(unlockBtns.first()).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Count should match the number of hidden skills
    const btnCount = await unlockBtns.count();
    expect(btnCount).toBeGreaterThan(0);
  });

  test('clicking unlock button toggles skill value 0 to 1', async ({ page }) => {
    // Get the initial unlocks remaining count
    const unlocksLabel = page.locator('.summary-item', { hasText: 'Unlocks remaining' });
    const initialCount = parseInt(await unlocksLabel.locator('.summary-value').textContent() || '0');

    // Find a hidden skill with unlock button and click it
    const firstUnlockBtn = page.locator('.sidebar-unlock').first();
    await firstUnlockBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Unlocks remaining should decrease by 1
    const newCount = parseInt(await unlocksLabel.locator('.summary-value').textContent() || '0');
    expect(newCount).toBe(initialCount - 1);

    // Total skill points should now be 1
    const skillPointsLabel = page.locator('.summary-item', { hasText: 'Total Skill Points' });
    const skillPoints = parseInt(await skillPointsLabel.locator('.summary-value').textContent() || '0');
    expect(skillPoints).toBe(1);
  });

  test('clicking lock button toggles skill value back to 0', async ({ page }) => {
    // Unlock a skill first
    const firstUnlockBtn = page.locator('.sidebar-unlock').first();
    await firstUnlockBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Now it should show as "locked" (unlocked state) - click again to lock
    await firstUnlockBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Skill points should be back to 0
    const skillPointsLabel = page.locator('.summary-item', { hasText: 'Total Skill Points' });
    const skillPoints = parseInt(await skillPointsLabel.locator('.summary-value').textContent() || '0');
    expect(skillPoints).toBe(0);
  });

  test('skill detail shows unlock/lock button for hidden skills', async ({ page }) => {
    // Click on a hidden skill (one with unlock button visible)
    const hiddenSkillItem = page.locator('.sidebar-item.hidden-skill').first();
    await hiddenSkillItem.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show "Hidden" badge in detail header
    await expect(page.locator('.detail-badge.is-hidden')).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should show unlock button in detail view
    await expect(page.locator('.detail-unlock')).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('unlocks overview opens and shows hidden skills', async ({ page }) => {
    // Click the "Unlocks" button in header
    await page.getByRole('button', { name: 'Unlocks' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Unlocks view should be visible
    await expect(page.locator('.unlocks-view')).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should show header with count
    await expect(page.locator('.unlocks-header h2')).toContainText('Skill Unlocks');
    await expect(page.locator('.unlocks-count')).toBeVisible();

    // Should have rows for hidden skills
    const rows = page.locator('.unlock-row');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test('unlocks view skill name navigates to skill detail', async ({ page }) => {
    // Open unlocks view
    await page.getByRole('button', { name: 'Unlocks' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Click on a skill name in the unlocks table
    const firstSkillName = page.locator('.unlock-skill-name').first();
    const skillName = await firstSkillName.textContent();
    await firstSkillName.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Unlocks view should close
    await expect(page.locator('.unlocks-view')).not.toBeVisible();

    // Skill detail should open with the clicked skill
    await expect(page.locator('.detail-header h2')).toContainText(skillName?.trim() || '', { timeout: TIMEOUT_SHORT });
  });

  test('target button in unlocks view opens optimizer', async ({ page }) => {
    // Open unlocks view
    await page.getByRole('button', { name: 'Unlocks' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Click target button on first row that has one
    const targetBtn = page.locator('.unlock-row:not(.unlocked) .target-btn').first();
    await targetBtn.click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Optimizer should be visible
    await expect(page.locator('.optimizer-content')).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Target level should be > 0
    const targetLevel = await page.locator('#target-level').inputValue();
    expect(parseInt(targetLevel)).toBeGreaterThan(0);
  });

  test('profession detail shows skill unlocks with target buttons', async ({ page }) => {
    // Switch to professions tab
    await page.locator('.tab-btn', { hasText: 'Professions' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Find a profession that has skill unlocks - search for one we know has them
    await page.locator('.search-input').fill('BLP Pistoleer');
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Click on the profession
    await page.locator('.sidebar-item', { hasText: 'BLP Pistoleer (Hit)' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should have "Skill Unlocks" section
    await expect(page.locator('.detail-section h3', { hasText: 'Skill Unlocks' })).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should have target buttons
    await expect(page.locator('.detail-section:has(h3:text("Skill Unlocks")) .target-btn').first()).toBeVisible();
  });

  test('target button in profession unlocks opens optimizer with correct values', async ({ page }) => {
    // Navigate to a profession with skill unlocks
    await page.locator('.tab-btn', { hasText: 'Professions' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await page.locator('.search-input').fill('BLP Pistoleer');
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await page.locator('.sidebar-item', { hasText: 'BLP Pistoleer (Hit)' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Click target button on first unlock row
    await page.locator('.detail-section:has(h3:text("Skill Unlocks")) .target-btn').first().click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Optimizer should open with the profession selected
    await expect(page.locator('.optimizer-content')).toBeVisible({ timeout: TIMEOUT_SHORT });

    // The profession dropdown should have "BLP Pistoleer (Hit)" selected
    await expect(page.locator('#target-prof option:checked')).toContainText('BLP Pistoleer (Hit)');
  });

  test('skill detail unlocked-by section shows target buttons', async ({ page }) => {
    // Click on a hidden skill that has unlocked-by info (e.g., Marksmanship)
    await page.locator('.search-input').fill('Marksmanship');
    await page.waitForTimeout(TIMEOUT_INSTANT);
    await page.locator('.sidebar-item', { hasText: 'Marksmanship' }).click();
    await page.waitForTimeout(TIMEOUT_INSTANT);

    // Should show "Unlocked By" section
    await expect(page.locator('.detail-section h3', { hasText: 'Unlocked By' })).toBeVisible({ timeout: TIMEOUT_SHORT });

    // Should have target buttons in the Unlocked By table
    await expect(page.locator('.detail-section:has(h3:text("Unlocked By")) .target-btn').first()).toBeVisible();
  });
});

test.describe.skip('Skills API', () => {
  test('GET returns empty skills for new user', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.get('/api/tools/skills');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data).toHaveProperty('skills');
  });

  test('PUT saves skills', async ({ verifiedUser }) => {
    const skills = { "Electrokinesis": 100.5, "Concentration": 50.0 };
    const response = await verifiedUser.request.put('/api/tools/skills', {
      data: { skills, trackImport: true }
    });
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.skills).toBeDefined();
    expect(data.skills["Electrokinesis"]).toBe(100.5);
  });

  test('rejects unauthenticated requests', async ({ page }) => {
    const getResponse = await page.request.get('/api/tools/skills');
    expect(getResponse.status()).toBe(401);

    const putResponse = await page.request.put('/api/tools/skills', {
      data: { skills: {} }
    });
    expect(putResponse.status()).toBe(401);
  });

  test('GET imports returns history', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.get('/api/tools/skills/imports');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });
});

test.describe.skip('Skill Values API', () => {
  test('converts skill points to PED', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { skillPointsToPED: [100, 500, 1000] }
    });
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.skillPointsToPED).toHaveLength(3);
    data.skillPointsToPED.forEach((v: number) => {
      expect(v).toBeGreaterThan(0);
      expect(typeof v).toBe('number');
    });
    // Higher skill points should yield higher PED
    expect(data.skillPointsToPED[2]).toBeGreaterThan(data.skillPointsToPED[1]);
    expect(data.skillPointsToPED[1]).toBeGreaterThan(data.skillPointsToPED[0]);
  });

  test('converts PED to skill points', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { pedToSkillPoints: [0.01, 0.1, 1.0] }
    });
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.pedToSkillPoints).toHaveLength(3);
    data.pedToSkillPoints.forEach((v: number) => {
      expect(v).toBeGreaterThan(0);
      expect(typeof v).toBe('number');
    });
    // Higher PED should yield higher skill points
    expect(data.pedToSkillPoints[2]).toBeGreaterThan(data.pedToSkillPoints[1]);
    expect(data.pedToSkillPoints[1]).toBeGreaterThan(data.pedToSkillPoints[0]);
  });

  test('supports bidirectional batch in one request', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: {
        skillPointsToPED: [500],
        pedToSkillPoints: [0.5]
      }
    });
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.skillPointsToPED).toHaveLength(1);
    expect(data.pedToSkillPoints).toHaveLength(1);
  });

  test('rejects empty request', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: {}
    });
    expect(response.status()).toBe(400);
  });

  test('rejects invalid values', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { skillPointsToPED: [-5] }
    });
    expect(response.status()).toBe(400);
  });

  test('rejects oversized batch', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { skillPointsToPED: Array(201).fill(100) }
    });
    expect(response.status()).toBe(400);
  });

  test('returns zero for zero input', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { skillPointsToPED: [0], pedToSkillPoints: [0] }
    });
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.skillPointsToPED[0]).toBe(0);
    expect(data.pedToSkillPoints[0]).toBe(0);
  });

  test('is publicly accessible without auth', async ({ page }) => {
    const response = await page.request.post('/api/tools/skills/values', {
      data: { skillPointsToPED: [100] }
    });
    expect(response.ok()).toBeTruthy();
  });
});
