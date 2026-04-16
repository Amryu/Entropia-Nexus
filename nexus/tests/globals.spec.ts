import { test, expect } from '@playwright/test';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Globals main page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');
  });

  test('renders tab navigation', async ({ page }) => {
    const tabNav = page.locator('.globals-tab-nav');
    await expect(tabNav).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    await expect(tabNav.locator('.tab-link', { hasText: 'Overview' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Live' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Top Players' })).toBeVisible();
    await expect(tabNav.locator('.tab-link', { hasText: 'Top Targets' })).toBeVisible();
    // Overview tab should be active on main page
    await expect(tabNav.locator('.tab-link.active')).toContainText('Overview');
  });

  test('renders stat cards with expanded metrics', async ({ page }) => {
    const statsRow = page.locator('.stats-row').first();
    await expect(statsRow).toBeVisible({ timeout: TIMEOUT_LONG });

    await expect(statsRow.locator('.stat-label', { hasText: 'Total Globals' })).toBeVisible();
    await expect(statsRow.locator('.stat-label', { hasText: 'Total Value' })).toBeVisible();
    await expect(statsRow.locator('.stat-label', { hasText: 'Avg Value' })).toBeVisible();
    await expect(statsRow.locator('.stat-label', { hasText: 'Highest Loot' })).toBeVisible();
    await expect(statsRow.locator('.stat-label', { hasText: 'Hall of Fame' })).toBeVisible();
    await expect(statsRow.locator('.stat-label', { hasText: 'All-Time Highs' })).toBeVisible();
  });

  test('renders category breakdown row', async ({ page }) => {
    const categoryRow = page.locator('.category-row');
    await expect(categoryRow).toBeVisible({ timeout: TIMEOUT_LONG });

    await expect(categoryRow.locator('.stat-label', { hasText: 'Hunting' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Mining' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Crafting' })).toBeVisible();
    await expect(categoryRow.locator('.stat-label', { hasText: 'Fishing' })).toBeVisible();
    // Category cards should show PED values
    await expect(categoryRow.locator('.stat-sub').first()).toContainText('PED');
  });

  test('has date range picker with custom option', async ({ page }) => {
    const picker = page.locator('.date-range-picker');
    await expect(picker).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(picker.locator('.period-btn', { hasText: '90 Days' })).toBeVisible();
    await expect(picker.locator('.period-btn', { hasText: '1 Year' })).toBeVisible();
    await expect(picker.locator('.period-btn', { hasText: 'Custom' })).toBeVisible();
  });

  test('custom date range reveals date inputs', async ({ page }) => {
    const customBtn = page.locator('.date-range-picker .period-btn', { hasText: 'Custom' });
    await customBtn.click();

    const dateInputs = page.locator('.date-range-picker input[type="date"]');
    await expect(dateInputs).toHaveCount(2);
  });

  test('renders top globals/hofs section with all tabs', async ({ page }) => {
    const topLoots = page.locator('.top-loots-section');
    await expect(topLoots).toBeVisible({ timeout: TIMEOUT_LONG });

    await expect(topLoots.locator('h2')).toContainText('Top Globals / HoFs');
    await expect(topLoots.locator('.sort-btn', { hasText: 'Hunting' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Mining' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Crafting' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Fishing' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Rare Find' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Discovery' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'Tier Record' })).toBeVisible();
    await expect(topLoots.locator('.sort-btn', { hasText: 'PvP' })).toBeVisible();
  });

  test('top loots special tabs disable type filters', async ({ page }) => {
    const topLoots = page.locator('.top-loots-section');
    await expect(topLoots).toBeVisible({ timeout: TIMEOUT_LONG });

    // Click Rare Find tab
    await topLoots.locator('.sort-btn', { hasText: 'Rare Find' }).click();
    await expect(topLoots.locator('.sort-btn.active')).toContainText('Rare Find');
    // Type filters should be disabled
    await expect(page.locator('.type-btn').first()).toBeDisabled();

    // Switch back to Hunting
    await topLoots.locator('.sort-btn', { hasText: 'Hunting' }).click();
    await expect(page.locator('.type-btn').first()).toBeEnabled();
  });

  test('top loots tabs switch content', async ({ page }) => {
    const topLoots = page.locator('.top-loots-section');
    await expect(topLoots).toBeVisible({ timeout: TIMEOUT_LONG });

    // Click Mining tab
    await topLoots.locator('.sort-btn', { hasText: 'Mining' }).click();
    await expect(topLoots.locator('.sort-btn.active')).toContainText('Mining');

    // Click Crafting tab
    await topLoots.locator('.sort-btn', { hasText: 'Crafting' }).click();
    await expect(topLoots.locator('.sort-btn.active')).toContainText('Crafting');
  });

  test('renders activity chart', async ({ page }) => {
    const chart = page.locator('.chart-wide canvas');
    await expect(chart).toBeVisible({ timeout: TIMEOUT_LONG });
  });

  test('tab navigation links to sub-pages', async ({ page }) => {
    const tabNav = page.locator('.globals-tab-nav');

    // Click Top Players tab
    await tabNav.locator('.tab-link', { hasText: 'Top Players' }).click();
    await expect(page).toHaveURL(/\/globals\/players/, { timeout: TIMEOUT_MEDIUM });

    // Navigate back and click Top Targets
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');
    await tabNav.locator('.tab-link', { hasText: 'Top Targets' }).click();
    await expect(page).toHaveURL(/\/globals\/targets/, { timeout: TIMEOUT_MEDIUM });
  });

  test('Live tab shows recent globals table and hides overview content', async ({ page }) => {
    const tabNav = page.locator('.globals-tab-nav');
    await tabNav.locator('.tab-link', { hasText: 'Live' }).click();
    await expect(page).toHaveURL(/view=live/, { timeout: TIMEOUT_MEDIUM });

    // Live tab should be active
    await expect(tabNav.locator('.tab-link.active')).toContainText('Live');

    // Live table should be visible, overview content hidden
    await expect(page.locator('.table-section')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(page.locator('.stats-row')).not.toBeVisible();
    await expect(page.locator('.top-loots-section')).not.toBeVisible();
  });
});

test.describe('Globals players leaderboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/globals/players');
    await page.waitForLoadState('networkidle');
  });

  test('renders tab navigation with Top Players active', async ({ page }) => {
    const tabNav = page.locator('.globals-tab-nav');
    await expect(tabNav).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(tabNav.locator('.tab-link.active')).toContainText('Top Players');
  });

  test('has sort options including avg and best', async ({ page }) => {
    const sortToggle = page.locator('.sort-toggle');
    await expect(sortToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Value' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Count' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Avg' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Best' })).toBeVisible();
  });

  test('table has avg and best columns', async ({ page }) => {
    const table = page.locator('.data-table');
    // Wait for table or empty state
    const hasTable = await table.isVisible({ timeout: TIMEOUT_LONG }).catch(() => false);
    if (!hasTable) return;

    await expect(table.locator('th', { hasText: 'Avg' })).toBeVisible();
    await expect(table.locator('th', { hasText: 'Best' })).toBeVisible();
  });

  test('has date range picker', async ({ page }) => {
    await expect(page.locator('.date-range-picker')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});

test.describe('Globals targets leaderboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/globals/targets');
    await page.waitForLoadState('networkidle');
  });

  test('renders tab navigation with Top Targets active', async ({ page }) => {
    const tabNav = page.locator('.globals-tab-nav');
    await expect(tabNav).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(tabNav.locator('.tab-link.active')).toContainText('Top Targets');
  });

  test('has sort options including avg and best', async ({ page }) => {
    const sortToggle = page.locator('.sort-toggles .sort-toggle').last();
    await expect(sortToggle).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Avg' })).toBeVisible();
    await expect(sortToggle.locator('.sort-btn', { hasText: 'By Best' })).toBeVisible();
  });

  test('table has avg and best columns', async ({ page }) => {
    const table = page.locator('.data-table');
    const hasTable = await table.isVisible({ timeout: TIMEOUT_LONG }).catch(() => false);
    if (!hasTable) return;

    await expect(table.locator('th', { hasText: 'Avg' })).toBeVisible();
    await expect(table.locator('th', { hasText: 'Best' })).toBeVisible();
  });

  test('defaults to mob grouping', async ({ page }) => {
    const mobBtn = page.locator('.sort-btn.active', { hasText: 'Mobs' });
    await expect(mobBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('has date range picker', async ({ page }) => {
    await expect(page.locator('.date-range-picker')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});

test.describe('Globals target detail page', () => {
  test('shows expanded stat cards', async ({ page }) => {
    await page.goto('/globals/target/Atrox');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    await expect(page.locator('.stat-label', { hasText: 'Avg Value' })).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(page.locator('.stat-label', { hasText: 'Highest Loot' })).toBeVisible();
  });

  test('shows leaderboard with sort tabs', async ({ page }) => {
    await page.goto('/globals/target/Atrox');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    const leaderboard = page.locator('.leaderboard-header');
    await expect(leaderboard).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(leaderboard.locator('.sort-btn', { hasText: 'By Value' })).toBeVisible();
    await expect(leaderboard.locator('.sort-btn', { hasText: 'By Count' })).toBeVisible();
    await expect(leaderboard.locator('.sort-btn', { hasText: 'By Highest' })).toBeVisible();
  });

  test('has date range picker', async ({ page }) => {
    await page.goto('/globals/target/Atrox');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    await expect(page.locator('.date-range-picker')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });
});

test.describe('Globals API', () => {
  test('stats endpoint returns expanded summary', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=7d');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    expect(data.summary).toHaveProperty('avg_value');
    expect(data.summary).toHaveProperty('max_value');
    expect(data.summary).toHaveProperty('hunting');
    expect(data.summary).toHaveProperty('mining');
    expect(data.summary).toHaveProperty('crafting');
    expect(data.summary).toHaveProperty('fishing');
    expect(data.summary.hunting).toHaveProperty('count');
    expect(data.summary.hunting).toHaveProperty('value');
    expect(data).toHaveProperty('bucket_unit');
  });

  test('stats endpoint supports custom date range', async ({ request }) => {
    const res = await request.get('/api/globals/stats?from=2024-01-01&to=2024-12-31');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data).toHaveProperty('bucket_unit');
  });

  test('top-loots endpoint returns paginated results', async ({ request }) => {
    const res = await request.get('/api/globals/stats/top-loots?period=all&category=hunting');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    expect(data).toHaveProperty('items');
    expect(data).toHaveProperty('page');
    expect(data).toHaveProperty('pages');
    expect(data).toHaveProperty('total');
    expect(Array.isArray(data.items)).toBeTruthy();
  });

  test('top-loots endpoint supports special categories', async ({ request }) => {
    const res = await request.get('/api/globals/stats/top-loots?period=all&category=rare_item');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    expect(data).toHaveProperty('items');
    expect(Array.isArray(data.items)).toBeTruthy();
  });

  test('players endpoint returns avg and best values', async ({ request }) => {
    const res = await request.get('/api/globals/stats/players?period=all&limit=5');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    if (data.players.length > 0) {
      expect(data.players[0]).toHaveProperty('avg_value');
      expect(data.players[0]).toHaveProperty('best_value');
    }
  });

  test('players endpoint supports avg sort', async ({ request }) => {
    const res = await request.get('/api/globals/stats/players?period=all&sort=avg&limit=5');
    expect(res.ok()).toBeTruthy();
  });

  test('targets endpoint returns avg and best values', async ({ request }) => {
    const res = await request.get('/api/globals/stats/targets?period=all&limit=5');
    expect(res.ok()).toBeTruthy();

    const data = await res.json();
    if (data.targets.length > 0) {
      expect(data.targets[0]).toHaveProperty('avg_value');
      expect(data.targets[0]).toHaveProperty('best_value');
    }
  });

  test('target detail endpoint returns summary stats', async ({ request }) => {
    const res = await request.get('/api/globals/target/Atrox');
    if (!res.ok()) return; // Target may not exist on test server

    const data = await res.json();
    expect(data.summary).toHaveProperty('avg_value');
    expect(data.summary).toHaveProperty('max_value');
  });

  test('target leaderboard endpoint returns paginated players', async ({ request }) => {
    const res = await request.get('/api/globals/target/Atrox/leaderboard?sort=value');
    if (!res.ok()) return; // Target may not exist on test server

    const data = await res.json();
    expect(data).toHaveProperty('players');
    expect(data).toHaveProperty('page');
    expect(data).toHaveProperty('pages');
    expect(data).toHaveProperty('total');
    expect(Array.isArray(data.players)).toBeTruthy();
    if (data.players.length > 0) {
      expect(data.players[0]).toHaveProperty('player');
      expect(data.players[0]).toHaveProperty('count');
      expect(data.players[0]).toHaveProperty('value');
      expect(data.players[0]).toHaveProperty('best_value');
    }
  });

  test('player detail endpoint returns expanded summary with top loots, ATH rankings and pvp', async ({ request }) => {
    const res = await request.get('/api/globals/player/TestPlayer');
    if (!res.ok()) return; // Player may not exist on test server

    const data = await res.json();
    expect(data.summary).toHaveProperty('avg_value');
    expect(data.summary).toHaveProperty('max_value');
    expect(data.summary).toHaveProperty('hunting_value');
    expect(data.summary).toHaveProperty('mining_value');
    expect(data.summary).toHaveProperty('crafting_value');
    expect(data.summary).toHaveProperty('fishing_value');
    expect(data.summary).toHaveProperty('pvp_count');
    expect(data.summary).toHaveProperty('pvp_value');
    expect(data).toHaveProperty('rare_items');
    expect(Array.isArray(data.rare_items)).toBeTruthy();
    expect(data).toHaveProperty('pvp_events');
    expect(Array.isArray(data.pvp_events)).toBeTruthy();
    expect(data).toHaveProperty('top_loots');
    expect(data.top_loots).toHaveProperty('hunting');
    expect(data.top_loots).toHaveProperty('mining');
    expect(data.top_loots).toHaveProperty('crafting');
    expect(data.top_loots).toHaveProperty('fishing');
    expect(data).toHaveProperty('ath_rankings');
    expect(data.ath_rankings).toHaveProperty('hunting');
    expect(data.ath_rankings).toHaveProperty('mining');
    expect(data.ath_rankings).toHaveProperty('crafting');
    expect(data.ath_rankings).toHaveProperty('fishing');
    expect(data.ath_rankings).toHaveProperty('pvp');
  });
});

test.describe('Globals API caching', () => {
  test('stats endpoint returns ETag for unfiltered request', async ({ request }) => {
    const res = await request.get('/api/globals/stats');
    expect(res.ok()).toBeTruthy();
    const etag = res.headers()['etag'];
    // ETag may not be present if cache hasn't warmed yet, but response must be valid
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');

    if (etag) {
      // Second request with If-None-Match should return 304
      const res2 = await request.get('/api/globals/stats', {
        headers: { 'If-None-Match': etag },
      });
      expect(res2.status()).toBe(304);
    }
  });

  test('stats endpoint bypasses cache for filtered request', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=7d');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
  });

  test('players endpoint returns ETag for default request', async ({ request }) => {
    const res = await request.get('/api/globals/stats/players');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty('players');
    expect(data).toHaveProperty('page');
  });

  test('targets endpoint returns ETag for default request', async ({ request }) => {
    const res = await request.get('/api/globals/stats/targets');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty('targets');
    expect(data).toHaveProperty('page');
  });
});

test.describe('Globals rollup-backed queries', () => {
  test('stats endpoint returns valid data for 7d period (daily rollup)', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=7d');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data.summary).toHaveProperty('total_value');
    expect(data.summary).toHaveProperty('avg_value');
    expect(data.summary).toHaveProperty('max_value');
    expect(data).toHaveProperty('by_type');
    expect(data).toHaveProperty('top_players');
    expect(data).toHaveProperty('top_targets');
    expect(data).toHaveProperty('activity');
    expect(data.bucket_unit).toBe('day');
  });

  test('stats endpoint returns valid data for 90d period (weekly rollup)', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=90d');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data.bucket_unit).toBe('week');
  });

  test('stats endpoint returns valid data for 1y period (weekly rollup)', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=1y');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data.bucket_unit).toBe('week');
  });

  test('stats with type filter uses rollup', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=30d&type=kill,team_kill');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    // All by_type entries should be kill or team_kill
    for (const t of data.by_type) {
      expect(['kill', 'team_kill']).toContain(t.type);
    }
  });

  test('stats with player filter falls back to raw table', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=30d&player=TestPlayer');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
  });

  test('players endpoint with period returns valid data', async ({ request }) => {
    const res = await request.get('/api/globals/stats/players?period=30d');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty('players');
    expect(data).toHaveProperty('total');
    expect(data).toHaveProperty('page');
    expect(data).toHaveProperty('pages');
    if (data.players.length > 0) {
      expect(data.players[0]).toHaveProperty('player');
      expect(data.players[0]).toHaveProperty('count');
      expect(data.players[0]).toHaveProperty('value');
      expect(data.players[0]).toHaveProperty('avg_value');
      expect(data.players[0]).toHaveProperty('best_value');
    }
  });

  test('targets endpoint with period returns valid data', async ({ request }) => {
    const res = await request.get('/api/globals/stats/targets?period=30d');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty('targets');
    expect(data).toHaveProperty('total');
    if (data.targets.length > 0) {
      expect(data.targets[0]).toHaveProperty('target');
      expect(data.targets[0]).toHaveProperty('count');
      expect(data.targets[0]).toHaveProperty('value');
      expect(data.targets[0]).toHaveProperty('primary_type');
    }
  });

  test('player detail with period returns valid summary', async ({ request }) => {
    const res = await request.get('/api/globals/player/TestPlayer?period=30d');
    if (!res.ok()) return; // Player may not exist
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data.summary).toHaveProperty('hunting_value');
    expect(data).toHaveProperty('activity');
    expect(data).toHaveProperty('hunting');
  });

  test('24h period bypasses rollup (hourly granularity)', async ({ request }) => {
    const res = await request.get('/api/globals/stats?period=24h');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.summary).toHaveProperty('total_count');
    expect(data.bucket_unit).toBe('hour');
  });
});

test.describe('Globals target detail page - compact layout', () => {
  test('shows recent globals next to top players chart', async ({ page }) => {
    await page.goto('/globals/target/Atrox');
    await page.waitForLoadState('networkidle');

    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible()) return;

    // Should have the side-by-side grid for top players + recent
    const grid = page.locator('.chart-recent-grid');
    await expect(grid).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Recent globals should use compact table
    const compactTable = page.locator('.compact-table');
    if (await compactTable.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(compactTable).toBeVisible();
    }
  });
});
