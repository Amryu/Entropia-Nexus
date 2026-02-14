import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT, TIMEOUT_LONG } from '../test-constants';

test.describe('Service Creation Page - Unauthenticated', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/market/services/create');
    await page.waitForLoadState('networkidle');

    // Should redirect into auth flow (site login route or direct Discord OAuth)
    const currentUrl = page.url();
    const inAuthFlow =
      currentUrl.includes('/discord/login') ||
      currentUrl.includes('discord.com/oauth2/authorize');
    expect(inAuthFlow).toBeTruthy();
  });
});

test.describe('Service Creation Page - Unverified User', () => {
  test('shows 403 error for unverified users', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/create');
    await unverifiedUser.waitForLoadState('networkidle');

    // Should show access denied error
    const errorStatus = unverifiedUser.locator('.error-status');
    const errorTitle = unverifiedUser.locator('.error-title');

    await expect(errorStatus).toHaveText('403');
    await expect(errorTitle).toContainText('Access Denied');
  });

  test('shows verification message', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/create');
    await unverifiedUser.waitForLoadState('networkidle');

    const message = unverifiedUser.locator('.error-message');
    await expect(message).toContainText('verified');
  });

  test('has back button on error page', async ({ unverifiedUser }) => {
    await unverifiedUser.goto('/market/services/create');
    await unverifiedUser.waitForLoadState('networkidle');

    const backBtn = unverifiedUser.getByRole('button', { name: /go back/i });
    await expect(backBtn).toBeVisible();
  });
});

test.describe('Service Creation Page - Verified User', () => {
  test('can access create page', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    // Should see the form, not login or error
    const form = verifiedUser.locator('form');
    await expect(form).toBeVisible();
  });

  test('page has correct title', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    await expect(verifiedUser).toHaveTitle(/Create.*Service|Service|Entropia/i);
  });

  test('has back navigation to services list', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const backLink = verifiedUser.getByRole('link', { name: /back to services/i });
    await expect(backLink).toBeVisible();
  });

  test('has service type selector with options', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType').or(
      verifiedUser.locator('select[name="serviceType"]')
    ).or(verifiedUser.getByLabel(/service type/i));

    await expect(typeSelect).toBeVisible();

    const options = await typeSelect.locator('option').allTextContents();
    expect(options.some(o => /healing/i.test(o))).toBeTruthy();
    expect(options.some(o => /dps/i.test(o))).toBeTruthy();
    expect(options.some(o => /transport/i.test(o))).toBeTruthy();
  });

  test('has title input field', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const titleInput = verifiedUser.locator('input#title').or(
      verifiedUser.locator('input[name="title"]')
    ).or(verifiedUser.getByLabel(/title/i));

    await expect(titleInput).toBeVisible();
  });

  test('has description textarea', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const descTextarea = verifiedUser.locator('textarea#description').or(
      verifiedUser.locator('textarea[name="description"]')
    ).or(verifiedUser.getByLabel(/description/i));

    await expect(descTextarea).toBeVisible();
  });

  test('has submit and cancel buttons', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const submitBtn = verifiedUser.locator('button[type="submit"]').or(
      verifiedUser.getByRole('button', { name: /create/i })
    );
    await expect(submitBtn).toBeVisible();

    const cancelBtn = verifiedUser.locator('.cancel-btn').or(
      verifiedUser.getByRole('button', { name: /cancel/i })
    );
    await expect(cancelBtn).toBeVisible();
  });
});

test.describe('Service Type Specific Fields - Verified User', () => {
  test('healing type shows paramedic level field', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('healing');

    const paramedicInput = verifiedUser.locator('input#paramedicLevel').or(
      verifiedUser.getByLabel(/paramedic/i)
    );
    await expect(paramedicInput).toBeVisible();
  });

  test('dps type shows HP level field', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('dps');

    const hpInput = verifiedUser.locator('input#hpLevel').or(
      verifiedUser.getByLabel(/hp.*level/i)
    );
    await expect(hpInput).toBeVisible();
  });

  test('transportation type shows ship options', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('transportation');

    const transportTypeSelect = verifiedUser.locator('select#transportationType').or(
      verifiedUser.getByLabel(/transportation type/i)
    );
    await expect(transportTypeSelect).toBeVisible();

    const shipNameField = verifiedUser.locator('#shipName').or(
      verifiedUser.getByLabel(/ship.*name/i)
    );
    await expect(shipNameField).toBeVisible();
  });

  test('custom type shows custom type name field', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('custom');

    const customNameInput = verifiedUser.locator('input#customTypeName').or(
      verifiedUser.getByLabel(/custom.*type.*name/i)
    );
    await expect(customNameInput).toBeVisible();
  });
});

test.describe('Form Validation - Verified User', () => {
  test('shows error when submitting without title', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const submitBtn = verifiedUser.locator('button[type="submit"]');
    await submitBtn.click();

    // Should show error message or form validation
    const errorMsg = verifiedUser.locator('.error-message').or(
      verifiedUser.locator('[class*="error"]')
    ).or(verifiedUser.locator('text=required'));

    const hasError = await errorMsg.first().isVisible().catch(() => false);
    const hasValidation = await verifiedUser.locator('input:invalid').isVisible().catch(() => false);

    expect(hasError || hasValidation).toBeTruthy();
  });
});

test.describe('Pricing Options - Verified User', () => {
  test('healing type shows pricing options', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('healing');

    // Wait for form to update after selection
    await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

    // Should show time or decay billing options
    const pricingSection = verifiedUser.locator('[class*="pricing"]').or(
      verifiedUser.locator('text=time-based pricing')
    ).or(verifiedUser.locator('text=decay-based pricing'));

    const hasPricing = await pricingSection.first().isVisible({ timeout: TIMEOUT_LONG }).catch(() => false);
    expect(hasPricing).toBeTruthy();
  });
});

test.describe('Location Options - Verified User', () => {
  test('non-transportation types show location options', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const typeSelect = verifiedUser.locator('select#serviceType');
    await typeSelect.selectOption('healing');

    // Wait for form to update after selection
    await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

    // Use specific selector for planet select (not checkbox)
    const planetSelect = verifiedUser.locator('select#planet');
    await expect(planetSelect).toBeVisible({ timeout: TIMEOUT_LONG });

    // Check for travel option (checkbox with label containing "travel")
    const travelOption = verifiedUser.locator('text=Willing to travel').or(
      verifiedUser.locator('label:has-text("travel")')
    );
    const hasTravelOption = await travelOption.first().isVisible({ timeout: TIMEOUT_LONG }).catch(() => false);
    expect(hasTravelOption).toBeTruthy();
  });
});

test.describe('Styling and Theme', () => {
  test('form sections have proper styling', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const formSection = verifiedUser.locator('.form-section').first();

    if (await formSection.isVisible().catch(() => false)) {
      const bgColor = await formSection.evaluate(el =>
        getComputedStyle(el).backgroundColor
      );
      expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
    }
  });

  test('buttons have proper contrast', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const submitBtn = verifiedUser.locator('button[type="submit"]').or(
      verifiedUser.locator('.submit-btn')
    );

    if (await submitBtn.isVisible().catch(() => false)) {
      const color = await submitBtn.evaluate(el => getComputedStyle(el).color);
      const bgColor = await submitBtn.evaluate(el => getComputedStyle(el).backgroundColor);
      expect(color).not.toBe(bgColor);
    }
  });

  test('page has proper scroll container structure', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/services/create');
    await verifiedUser.waitForLoadState('networkidle');

    const scrollContainer = verifiedUser.locator('.scroll-container');
    await expect(scrollContainer).toBeVisible();

    const height = await scrollContainer.evaluate(el =>
      getComputedStyle(el).height
    );
    expect(height).not.toBe('auto');
    expect(height).not.toBe('0px');
  });
});
