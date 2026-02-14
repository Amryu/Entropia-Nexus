import { test, expect } from '../fixtures/auth';
import { TIMEOUT_LONG } from '../test-constants';

// ─── Detail View (Specific Service) ─────────────────────────────

test.describe('Service Detail - Healing Service', () => {
  test('shows service title as page heading', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    // Detail view heading shows the service title, not "Services"
    const headingText = await heading.textContent();
    expect(headingText).not.toMatch(/^Services$/);
  });

  test('has breadcrumb linking back to services list', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    const breadcrumb = page.locator('.breadcrumb');
    await expect(breadcrumb).toBeVisible();

    const servicesLink = breadcrumb.locator('a[href="/market/services"]');
    await expect(servicesLink).toBeVisible();
    await expect(servicesLink).toContainText('Services');
  });

  test('shows service type badge', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    const badge = page.locator('.service-type-badge');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText(/healing/i);
  });

  test('shows provider section with owner', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    const providerSection = page.locator('.info-section', { has: page.locator('h3', { hasText: 'Provider' }) });
    await expect(providerSection).toBeVisible();
    await expect(providerSection).toContainText('Owner');
  });

  test('shows location section', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    const locationSection = page.locator('.info-section', { has: page.locator('h3', { hasText: 'Location' }) });
    await expect(locationSection).toBeVisible();
  });

  test('owner action buttons visible for logged-in user', async ({ page }) => {
    await page.goto('/market/services/1');
    await page.waitForLoadState('networkidle');

    // Non-owner, non-logged-in user should NOT see edit or request buttons
    const editBtn = page.locator('a[href="/market/services/1/edit"]');
    await expect(editBtn).not.toBeVisible();
  });
});

test.describe('Service Detail - Transportation Service', () => {
  test('shows transportation type badge', async ({ page }) => {
    await page.goto('/market/services/3');
    await page.waitForLoadState('networkidle');

    const badge = page.locator('.service-type-badge');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText(/transport/i);
  });

  test('shows provider section', async ({ page }) => {
    await page.goto('/market/services/3');
    await page.waitForLoadState('networkidle');

    const providerSection = page.locator('.info-section', { has: page.locator('h3', { hasText: 'Provider' }) });
    await expect(providerSection).toBeVisible();
  });
});

test.describe('Service Detail - Non-Existent Service', () => {
  test('non-existent service ID falls back to list view', async ({ page }) => {
    await page.goto('/market/services/999999');
    await page.waitForLoadState('networkidle');

    // When service is not found, selectedService is null → list view renders
    // Should show the page heading as "Services" (list view)
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    await expect(heading).toContainText('Services');
  });
});

// ─── DPS Table Columns ──────────────────────────────────────────

test.describe('Service Detail - DPS Table', () => {
  test('DPS table has correct column headers', async ({ page }) => {
    await page.goto('/market/services/dps');
    await page.waitForLoadState('networkidle');

    // FancyTable uses .header-cell divs, not <th> elements
    const headers = await page.locator('.header-cell').allTextContents();
    const headerTexts = headers.map(h => h.replace(/[▲▼]/, '').trim().toLowerCase());

    for (const expected of ['service', 'dps', 'location', 'pricing', 'provider']) {
      expect(headerTexts.some(h => h.includes(expected))).toBeTruthy();
    }
  });
});

// ─── Custom Services Tab ────────────────────────────────────────

test.describe('Service Detail - Custom Tab', () => {
  test('custom tab shows coming soon message', async ({ page }) => {
    await page.goto('/market/services/custom');
    await page.waitForLoadState('networkidle');

    const customTab = page.locator('.tab-btn', { hasText: 'Custom' });
    await expect(customTab).toHaveClass(/active/);

    const emptyState = page.locator('.empty-state');
    await expect(emptyState).toBeVisible();
    await expect(emptyState).toContainText(/coming soon/i);
  });
});

// ─── Verified User Detail Actions ───────────────────────────────

test.describe('Service Detail - Verified User', () => {
  test('verified user sees Ask a Question button', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/1');
    await verifiedUser.waitForLoadState('networkidle');

    const askBtn = verifiedUser.getByRole('button', { name: /ask a question/i });
    await expect(askBtn).toBeVisible();
  });

  test('verified non-owner does not see Edit button', async ({ verifiedUser }) => {
    // Service 1 is owned by a different user
    await verifiedUser.goto('/market/services/1');
    await verifiedUser.waitForLoadState('networkidle');

    const editBtn = verifiedUser.locator('a[href="/market/services/1/edit"]');
    await expect(editBtn).not.toBeVisible();
  });
});

// ─── Auth-Gated Sub-Pages: Unauthenticated ──────────────────────

test.describe('Service Sub-Pages - Unauthenticated', () => {
  test('edit page redirects to login', async ({ page }) => {
    await page.goto('/market/services/1/edit');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize') ||
      currentUrl.includes('discord.com/login');
    expect(inAuthFlow).toBeTruthy();
  });

  test('availability page redirects to login', async ({ page }) => {
    await page.goto('/market/services/1/availability');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize') ||
      currentUrl.includes('discord.com/login');
    expect(inAuthFlow).toBeTruthy();
  });

  test('flights page redirects to login', async ({ page }) => {
    await page.goto('/market/services/3/flights');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize') ||
      currentUrl.includes('discord.com/login');
    expect(inAuthFlow).toBeTruthy();
  });

  test('ticket-offers page redirects to login', async ({ page }) => {
    await page.goto('/market/services/3/ticket-offers');
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize') ||
      currentUrl.includes('discord.com/login');
    expect(inAuthFlow).toBeTruthy();
  });
});

// ─── Auth-Gated Sub-Pages: Unverified User ──────────────────────

test.describe('Service Sub-Pages - Unverified User', () => {
  test('edit page shows 403 for unverified user', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/1/edit');
    await unverifiedUser.waitForLoadState('networkidle');

    const errorStatus = unverifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');

    const errorTitle = unverifiedUser.locator('.error-title');
    await expect(errorTitle).toContainText('Access Denied');
  });

  test('availability page shows 403 for unverified user', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/1/availability');
    await unverifiedUser.waitForLoadState('networkidle');

    const errorStatus = unverifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });

  test('flights page shows 403 for unverified user', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/3/flights');
    await unverifiedUser.waitForLoadState('networkidle');

    const errorStatus = unverifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });

  test('ticket-offers page shows 403 for unverified user', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/3/ticket-offers');
    await unverifiedUser.waitForLoadState('networkidle');

    const errorStatus = unverifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });

  test('403 page shows verify hint with account setup link', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/1/edit');
    await unverifiedUser.waitForLoadState('networkidle');

    const verifyHint = unverifiedUser.locator('.verify-hint');
    await expect(verifyHint).toBeVisible();

    const verifyLink = verifyHint.locator('a[href="/account/setup"]');
    await expect(verifyLink).toBeVisible();
    await expect(verifyLink).toContainText('Verify');
  });
});

// ─── Auth-Gated Sub-Pages: Verified Non-Owner ──────────────────

test.describe('Service Sub-Pages - Verified Non-Owner', () => {
  test('edit page shows 403 for non-owner', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/1/edit');
    await verifiedUser.waitForLoadState('networkidle');

    const errorStatus = verifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });

  test('availability page redirects non-owner to detail', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/1/availability');
    await verifiedUser.waitForLoadState('networkidle');

    // availability uses redirect(302) for non-owners, not 403
    await expect(verifiedUser).toHaveURL(/\/market\/services\/1$/);
  });

  test('flights page shows 403 for non-owner', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/3/flights');
    await verifiedUser.waitForLoadState('networkidle');

    const errorStatus = verifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });

  test('ticket-offers page shows 403 for non-owner', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/3/ticket-offers');
    await verifiedUser.waitForLoadState('networkidle');

    const errorStatus = verifiedUser.locator('.error-status');
    await expect(errorStatus).toHaveText('403');
  });
});
