import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

// ─── Navigation and Layout ──────────────────────────────────────

test.describe('Services List Page - Layout', () => {
  test('page loads with correct title', async ({ page }) => {
    await page.goto('/market/services/healing');
    await expect(page).toHaveTitle(/Services.*Entropia/i);
    await expect(page.locator('h1')).toContainText(/services/i);
  });

  test('has proper scroll container structure', async ({ page }) => {
    await page.goto('/market/services/healing');
    await expect(page.locator('.scroll-container')).toBeVisible();
    await expect(page.locator('.page-container')).toBeVisible();
  });

  test('has breadcrumb navigation to Market', async ({ page }) => {
    await page.goto('/market/services/healing');
    // Breadcrumb is inside the page content area (not the nav bar)
    const breadcrumb = page.locator('.page-container a[href="/market"]');
    await expect(breadcrumb).toBeVisible();
  });
});

// ─── Category Routing ───────────────────────────────────────────

test.describe('Services List Page - Category Routing', () => {
  test('auto-redirects /market/services to default category', async ({ page }) => {
    await page.goto('/market/services');
    // Should redirect to a category slug (healing by default, or last-used)
    await page.waitForURL(/\/market\/services\/(healing|dps|transportation|custom)/, { timeout: TIMEOUT_LONG });
  });

  test('direct URL /market/services/dps loads DPS tab as active', async ({ page }) => {
    await page.goto('/market/services/dps');
    await page.waitForLoadState('networkidle');
    const dpsTab = page.locator('.tab-btn', { hasText: 'DPS' });
    await expect(dpsTab).toHaveClass(/active/);
  });

  test('direct URL /market/services/transportation loads Taxi/Warp tab as active', async ({ page }) => {
    await page.goto('/market/services/transportation');
    await page.waitForLoadState('networkidle');
    const transportTab = page.getByRole('button', { name: /Taxi\/Warp/ });
    await expect(transportTab).toHaveClass(/active/);
  });

  test('direct URL /market/services/custom loads Custom tab as active', async ({ page }) => {
    await page.goto('/market/services/custom');
    await page.waitForLoadState('networkidle');
    const customTab = page.locator('.tab-btn', { hasText: 'Custom' });
    await expect(customTab).toHaveClass(/active/);
  });

  test('clicking tab navigates to category URL', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const dpsTab = page.locator('.tab-btn', { hasText: 'DPS' });
    await dpsTab.click();
    await page.waitForURL(/\/market\/services\/dps/, { timeout: TIMEOUT_LONG });
  });

  test('invalid category slug does not crash', async ({ page }) => {
    await page.goto('/market/services/invalidcategory');
    await expect(page.locator('body')).toBeVisible();
  });
});

// ─── Service Type Tabs ──────────────────────────────────────────

test.describe('Services List Page - Tabs', () => {
  test('displays all four category tabs', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const tabs = page.locator('.tab-btn');
    await expect(tabs).toHaveCount(4);
  });

  test('tab labels are correct', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const tabTexts = await page.locator('.tab-btn').allTextContents();
    // Strip whitespace and count markers like "(1)"
    const labels = tabTexts.map(t => t.replace(/\s*\(\d+\)\s*/, '').trim());
    expect(labels).toEqual(['Healing', 'DPS', 'Taxi/Warp', 'Custom']);
  });

  test('active tab has .active class', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const healingTab = page.locator('.tab-btn', { hasText: 'Healing' });
    await expect(healingTab).toHaveClass(/active/);

    // Other tabs should NOT be active
    const dpsTab = page.locator('.tab-btn', { hasText: 'DPS' });
    const classes = await dpsTab.getAttribute('class');
    expect(classes).not.toContain('active');
  });

  test('tabs show service counts', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const tabTexts = await page.locator('.tab-btn').allTextContents();
    for (const text of tabTexts) {
      expect(text).toMatch(/\(\d+\)/);
    }
  });
});

// ─── Planet Filter ──────────────────────────────────────────────

test.describe('Services List Page - Planet Filter', () => {
  test('planet filter dropdown is visible', async ({ page }) => {
    await page.goto('/market/services/healing');
    const select = page.locator('.filter-group select');
    await expect(select).toBeVisible();
  });

  test('has All Planets default option', async ({ page }) => {
    await page.goto('/market/services/healing');
    const options = await page.locator('.filter-group select option').allTextContents();
    expect(options[0]).toMatch(/All Planets/i);
  });
});

// ─── Transportation Tab Content ─────────────────────────────────

test.describe('Services List Page - Transportation Tab', () => {
  test('transportation table has correct column headers', async ({ page }) => {
    await page.goto('/market/services/transportation');
    await page.waitForLoadState('networkidle');

    // FancyTable uses .header-cell divs, not <th> elements
    const headers = await page.locator('.header-cell').allTextContents();
    const headerTexts = headers.map(h => h.replace(/[▲▼]/, '').trim().toLowerCase());

    for (const expected of ['service', 'type', 'ship', 'location', 'price', 'provider']) {
      expect(headerTexts.some(h => h.includes(expected))).toBeTruthy();
    }
  });

  test('shows empty state or data rows', async ({ page }) => {
    await page.goto('/market/services/transportation');
    await page.waitForLoadState('networkidle');

    // Should show either data rows (FancyTable uses .table-row) or an empty state message
    const dataRow = page.locator('.table-row:not(.empty)');
    const emptyState = page.locator('.empty-state, .table-row.empty');
    const hasData = await dataRow.first().isVisible().catch(() => false);
    const hasEmpty = await emptyState.first().isVisible().catch(() => false);
    expect(hasData || hasEmpty).toBeTruthy();
  });
});

// ─── Healing Tab Content ────────────────────────────────────────

test.describe('Services List Page - Healing Tab', () => {
  test('healing table has correct column headers', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    // FancyTable uses .header-cell divs, not <th> elements
    const headers = await page.locator('.header-cell').allTextContents();
    const headerTexts = headers.map(h => h.replace(/[▲▼]/, '').trim().toLowerCase());

    for (const expected of ['service', 'hp/s', 'decay', 'location', 'pricing', 'provider']) {
      expect(headerTexts.some(h => h.includes(expected))).toBeTruthy();
    }
  });
});

// ─── LoginToCreateButton (unauthenticated) ──────────────────────

test.describe('Services List Page - LoginToCreateButton', () => {
  test('shows lock icon button when not logged in', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    const loginBtn = page.getByRole('button', { name: /Login to create service/i });
    await expect(loginBtn).toBeVisible();
  });

  test('clicking opens auth dialog with 3-step instructions', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /Login to create service/i }).click();

    // Dialog uses role="dialog" attribute
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(dialog.locator('h2')).toContainText('Login Required');

    // Should have 3 steps
    const steps = dialog.locator('.auth-step');
    await expect(steps).toHaveCount(3);
  });

  test('auth dialog has Login with Discord link', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /Login to create service/i }).click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    const discordLink = dialog.getByRole('link', { name: /Login with Discord/i });
    await expect(discordLink).toBeVisible();
    const href = await discordLink.getAttribute('href');
    expect(href).toContain('/discord/login');
    expect(href).toContain('redirect');
  });

  test('auth dialog can be closed', async ({ page }) => {
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /Login to create service/i }).click();
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    await dialog.getByRole('button', { name: 'Close' }).click();
    await expect(dialog).not.toBeVisible();
  });
});

// ─── Authenticated Header Actions ───────────────────────────────

test.describe('Services List Page - Verified User Actions', () => {
  test('verified user sees My Services and Create Service buttons', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/healing');
    await verifiedUser.waitForLoadState('networkidle');

    const myServicesLink = verifiedUser.locator('a[href="/market/services/my"]');
    await expect(myServicesLink).toBeVisible();

    const createLink = verifiedUser.locator('a[href="/market/services/create"]');
    await expect(createLink).toBeVisible();
  });

  test('verified user does not see LoginToCreateButton', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/healing');
    await verifiedUser.waitForLoadState('networkidle');

    const loginBtn = verifiedUser.getByRole('button', { name: /Login to create/i });
    await expect(loginBtn).not.toBeVisible();
  });
});

// ─── Responsiveness ─────────────────────────────────────────────

test.describe('Services List Page - Responsiveness', () => {
  test('renders on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.tab-btn').first()).toBeVisible();
  });

  test('renders on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/market/services/healing');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.tab-btn').first()).toBeVisible();
  });
});
