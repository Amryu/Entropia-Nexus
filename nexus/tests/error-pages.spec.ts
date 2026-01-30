import { test, expect } from './fixtures/auth';

test.describe('Error Pages', () => {
  test.describe('404 Not Found', () => {
    test('shows 404 for non-existent page', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const errorStatus = page.locator('.error-status');
      const errorTitle = page.locator('.error-title');

      await expect(errorStatus).toHaveText('404');
      await expect(errorTitle).toContainText('Not Found');
    });

    test('404 page has navigation buttons', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const backBtn = page.getByRole('button', { name: /go back/i });
      const homeBtn = page.getByRole('button', { name: /homepage/i });

      await expect(backBtn).toBeVisible();
      await expect(homeBtn).toBeVisible();
    });

    test('404 page home button navigates to homepage', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const homeBtn = page.getByRole('button', { name: /homepage/i });

      // Click and wait for navigation (SvelteKit client-side navigation)
      await Promise.all([
        page.waitForURL('**/'),
        homeBtn.click()
      ]);

      // Should navigate to the homepage (root path)
      const url = new URL(page.url());
      expect(url.pathname).toBe('/');
    });
  });

  test.describe('403 Forbidden (Unverified User)', () => {
    test('shows 403 when unverified user accesses protected page', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/market/services/create');
      await unverifiedUser.waitForLoadState('networkidle');

      const errorStatus = unverifiedUser.locator('.error-status');
      const errorTitle = unverifiedUser.locator('.error-title');

      await expect(errorStatus).toHaveText('403');
      await expect(errorTitle).toContainText('Access Denied');
    });

    test('403 page shows verification hint with link', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/market/services/create');
      await unverifiedUser.waitForLoadState('networkidle');

      const hint = unverifiedUser.locator('.verify-hint');
      await expect(hint).toBeVisible();
      await expect(hint).toContainText('verified');

      // Should have a link to the verification page
      const verifyBtn = unverifiedUser.locator('.btn-verify');
      await expect(verifyBtn).toBeVisible();
      await expect(verifyBtn).toHaveAttribute('href', '/account/setup');
    });

    test('403 page has proper styling', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/market/services/create');
      await unverifiedUser.waitForLoadState('networkidle');

      const errorContainer = unverifiedUser.locator('.error-container');
      await expect(errorContainer).toBeVisible();

      // Check background color is set
      const bgColor = await errorContainer.evaluate(el =>
        getComputedStyle(el).backgroundColor
      );
      expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
    });
  });

  test.describe('401 Unauthorized (Login Required)', () => {
    test('redirects to login for protected pages when not authenticated', async ({ page }) => {
      await page.goto('/market/services/create');
      await page.waitForLoadState('networkidle');

      // Should redirect to login page
      expect(page.url()).toContain('login');
    });
  });

  test.describe('Error Page Styling', () => {
    test('error icon is visible', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const errorIcon = page.locator('.error-icon');
      await expect(errorIcon).toBeVisible();
    });

    test('buttons have proper hover states', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const primaryBtn = page.locator('.btn-primary');
      await expect(primaryBtn).toBeVisible();

      // Check the button has accent color
      const bgColor = await primaryBtn.evaluate(el =>
        getComputedStyle(el).backgroundColor
      );
      expect(bgColor).not.toBe('transparent');
    });

    test('error page is properly centered', async ({ page }) => {
      await page.goto('/this-page-does-not-exist-12345');
      await page.waitForLoadState('networkidle');

      const errorPage = page.locator('.error-page');
      await expect(errorPage).toBeVisible();

      const display = await errorPage.evaluate(el =>
        getComputedStyle(el).display
      );
      const justifyContent = await errorPage.evaluate(el =>
        getComputedStyle(el).justifyContent
      );

      expect(display).toBe('flex');
      expect(justifyContent).toBe('center');
    });
  });
});
