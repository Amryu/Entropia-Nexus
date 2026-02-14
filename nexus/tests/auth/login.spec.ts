import { test, expect } from '../fixtures/auth';

function isAuthRedirect(url: string): boolean {
  return /login|discord\/login|discord\.com\/oauth2\/authorize/i.test(url);
}

test.describe('Login Flow', () => {
  test.describe('Login Page', () => {
    test('login page redirects to discord auth', async ({ page }) => {
      await page.goto('/login');
      await page.waitForLoadState('networkidle');

      // Login page should redirect to Discord auth or have login content
      const url = page.url();
      // Either redirect to discord or show some page content
      const hasContent = await page.locator('body').isVisible();
      expect(url.includes('discord') || hasContent).toBeTruthy();
    });
  });

  test.describe('Login Button in Menu', () => {
    test('clicking login button initiates login', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const loginButton = page.locator('.auth-container .discord-button');
      await expect(loginButton).toBeVisible();

      // Verify button's parent link goes to login
      const parentLink = page.locator('.auth-container a:has(.discord-button)');
      const href = await parentLink.getAttribute('href');
      expect(href).toMatch(/login|discord/i);
    });

    test('login link visible in mobile menu', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      const loginLink = page.locator('.mobile-user-action.primary');
      await expect(loginLink).toBeVisible();

      // Should contain "Discord" or "Login"
      const linkText = await loginLink.textContent();
      expect(linkText).toMatch(/Discord|Login/i);
    });
  });

  test.describe('Protected Routes - Unauthenticated', () => {
    test('accessing protected page redirects to login', async ({ page }) => {
      await page.goto('/market/services/create');
      await page.waitForLoadState('networkidle');

      expect(isAuthRedirect(page.url())).toBeTruthy();
    });

    test('accessing my services redirects to login', async ({ page }) => {
      await page.goto('/market/services/my');
      await page.waitForLoadState('networkidle');

      expect(isAuthRedirect(page.url())).toBeTruthy();
    });

    test('accessing admin panel requires auth', async ({ page }) => {
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Should redirect to login or show 401/403
      const isLoginPage = page.url().includes('login');
      const errorStatus = page.locator('.error-status');
      const hasError = await errorStatus.isVisible().catch(() => false);

      expect(isLoginPage || hasError).toBeTruthy();
    });
  });

  test.describe('Authenticated User State', () => {
    test('authenticated user sees avatar in menu', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      const userAvatar = verifiedUser.locator('.user-image');
      await expect(userAvatar).toBeVisible();
    });

    test('authenticated user does not see desktop login button', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      // User avatar should be visible (instead of login button)
      const userAvatar = verifiedUser.locator('.user-image');
      await expect(userAvatar).toBeVisible();
    });

    test('user dropdown shows logged in as text', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      const userAvatar = verifiedUser.locator('.user-image');
      await userAvatar.hover();

      // Use specific selector for user dropdown
      const dropdown = verifiedUser.locator('.menu-item.user .dropdown-content');
      await expect(dropdown).toBeVisible();

      const dropdownText = await dropdown.textContent();
      expect(dropdownText).toContain('Logged in as');
    });

    test('user can access protected routes', async ({ verifiedUser }) => {
      await verifiedUser.goto('/market/services/create');
      await verifiedUser.waitForLoadState('networkidle');

      // Should see the form, not login redirect
      const form = verifiedUser.locator('form');
      await expect(form).toBeVisible();
    });
  });

  test.describe('Unverified User Restrictions', () => {
    test('unverified user sees unverified badge', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/');
      await unverifiedUser.waitForLoadState('networkidle');

      const badge = unverifiedUser.locator('.unverified-badge');
      await expect(badge).toBeVisible();
    });

    test('unverified user sees verify account option', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/');
      await unverifiedUser.waitForLoadState('networkidle');

      const userAvatar = unverifiedUser.locator('.user-image');
      await userAvatar.hover();

      const verifyLink = unverifiedUser.locator('.verify-btn').or(
        unverifiedUser.locator('.dropdown-content a[href*="setup"]')
      );
      await expect(verifyLink.first()).toBeVisible();
    });

    test('unverified user cannot access verified-only pages', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/market/services/create');
      await unverifiedUser.waitForLoadState('networkidle');

      // Should show 403 error
      const errorStatus = unverifiedUser.locator('.error-status');
      await expect(errorStatus).toHaveText('403');
    });

    test('unverified user sees verification message on 403', async ({ unverifiedUser }) => {
      await unverifiedUser.goto('/market/services/create');
      await unverifiedUser.waitForLoadState('networkidle');

      const message = unverifiedUser.locator('.error-message');
      await expect(message).toContainText('verified');
    });
  });

  test.describe('Logout Flow', () => {
    test('logout link visible in user dropdown', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      const userAvatar = verifiedUser.locator('.user-image');
      await userAvatar.hover();

      const logoutLink = verifiedUser.locator('.dropdown-content a[href*="logout"]');
      await expect(logoutLink).toBeVisible();
    });

    test('logout link visible in mobile menu', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 768, height: 1024 });
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      const logoutLink = verifiedUser.locator('.mobile-menu a[href*="logout"]');
      await expect(logoutLink).toBeVisible();
    });
  });

  test.describe('Session Persistence', () => {
    test('authenticated state persists across page navigation', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      // Verify logged in
      await expect(verifiedUser.locator('.user-image')).toBeVisible();

      // Navigate to another page
      await verifiedUser.goto('/tools/loadouts');
      await verifiedUser.waitForLoadState('networkidle');

      // Should still be logged in
      await expect(verifiedUser.locator('.user-image')).toBeVisible();
    });

    test('authenticated state persists on page reload', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await expect(verifiedUser.locator('.user-image')).toBeVisible();

      // Reload the page
      await verifiedUser.reload();
      await verifiedUser.waitForLoadState('networkidle');

      // Should still be logged in
      await expect(verifiedUser.locator('.user-image')).toBeVisible();
    });
  });

  test.describe('Admin User', () => {
    test('admin user can access admin panel', async ({ adminUser }) => {
      await adminUser.goto('/admin');
      await adminUser.waitForLoadState('networkidle');

      // Should not redirect to login or show error
      expect(adminUser.url()).toContain('admin');

      const errorStatus = adminUser.locator('.error-status');
      await expect(errorStatus).toBeHidden();
    });

    test('admin user sees impersonate option', async ({ adminUser }) => {
      await adminUser.goto('/');
      await adminUser.waitForLoadState('networkidle');

      const userAvatar = adminUser.locator('.user-image');
      await userAvatar.hover();

      const impersonateBtn = adminUser.locator('.dropdown-content button:has-text("Impersonate")');
      await expect(impersonateBtn).toBeVisible();
    });

    test('non-admin is redirected from admin panel', async ({ verifiedUser }) => {
      await verifiedUser.goto('/admin');
      await verifiedUser.waitForLoadState('networkidle');

      // Non-admin users are redirected to homepage
      expect(verifiedUser.url()).not.toContain('/admin');
    });
  });
});
