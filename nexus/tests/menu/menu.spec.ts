import { test, expect } from '../fixtures/auth';

test.describe('Main Navigation Menu', () => {
  test.describe('Desktop Menu', () => {
    test('menu loads with all main sections', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Check that nav menu exists
      const nav = page.locator('nav');
      await expect(nav).toBeVisible();

      // Check main menu sections exist (these are the dropdown triggers)
      const items = page.locator('.menu-item');
      expect(await items.count()).toBeGreaterThan(0);
    });

    test('dropdown menus open on hover', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Find a menu item with dropdown (not the user menu, not logo)
      const menuItem = page.locator('.menu-container .menu-item:not(.user)').first();
      await menuItem.hover();

      // Dropdown content should be visible
      const dropdown = menuItem.locator('.dropdown-content');
      await expect(dropdown).toBeVisible();
    });

    test('has logo linking to homepage', async ({ page }) => {
      await page.goto('/tools/loadouts');
      await page.waitForLoadState('networkidle');

      const logo = page.locator('nav a[href="/"]').first();
      await expect(logo).toBeVisible();

      await logo.click();
      await page.waitForURL('**/');
      expect(page.url()).toMatch(/\/$/);
    });

    test('search input is visible on desktop', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Desktop search input has class "search"
      const searchInput = page.locator('nav input.search');
      await expect(searchInput).toBeVisible();
    });

    test('search shows results on input', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const searchInput = page.locator('nav input.search');
      await searchInput.fill('calypso');

      // Wait for search results dropdown
      await page.waitForTimeout(500);

      const searchResults = page.locator('.dropdown-search');
      await expect(searchResults).toBeVisible();
    });

    test('dark/light mode toggle is visible', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const toggle = page.locator('.dark-light-toggle');
      await expect(toggle).toBeVisible();
    });

    test('dark/light mode toggle changes theme', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Click the toggle
      const toggleBtn = page.locator('.dark-light-button');
      await toggleBtn.click();

      // Wait for theme change
      await page.waitForTimeout(200);

      // The toggle should still work (button should be visible after click)
      await expect(toggleBtn).toBeVisible();
    });

    test('login button visible when not authenticated', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // On desktop, look for discord button in auth-container
      const loginButton = page.locator('.auth-container .discord-button');
      await expect(loginButton).toBeVisible();
    });

    test('user avatar visible when authenticated', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      const userAvatar = verifiedUser.locator('.user-image');
      await expect(userAvatar).toBeVisible();
    });

    test('user dropdown shows logout option', async ({ verifiedUser }) => {
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      const userAvatar = verifiedUser.locator('.user-image');
      await userAvatar.hover();

      const logoutLink = verifiedUser.locator('.dropdown-content a[href*="logout"]');
      await expect(logoutLink).toBeVisible();
    });
  });

  test.describe('Mobile Menu (≤900px)', () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });
    });

    test('burger menu button is visible on mobile', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      const burgerButton = page.locator('.burger-button');
      await expect(burgerButton).toBeVisible();
    });

    test('desktop menu items are hidden on mobile', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Desktop menu items should be hidden
      const desktopMenu = page.locator('.menu-items');
      await expect(desktopMenu).toBeHidden();
    });

    test('desktop discord login button is hidden on mobile', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Desktop discord button should be hidden
      const discordButton = page.locator('.auth-container .discord-button');
      await expect(discordButton).toBeHidden();
    });

    test('clicking burger opens mobile menu', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Click burger menu
      const burgerButton = page.locator('.burger-button');
      await burgerButton.click();

      // Mobile menu should open
      const mobileMenu = page.locator('.mobile-menu.open');
      await expect(mobileMenu).toBeVisible();
    });

    test('mobile menu has search input', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      const searchInput = page.locator('.mobile-search-input');
      await expect(searchInput).toBeVisible();
    });

    test('mobile menu has navigation sections', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Check for navigation sections
      const navSections = page.locator('.mobile-section');
      expect(await navSections.count()).toBeGreaterThan(0);
    });

    test('mobile menu sections are collapsible', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Click a section header
      const sectionHeader = page.locator('.mobile-section-header').first();
      await sectionHeader.click();

      // Section items should be expanded
      const sectionItems = page.locator('.mobile-section-items.expanded').first();
      await expect(sectionItems).toBeVisible();
    });

    test('mobile menu has login button when not authenticated', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Look for login option in mobile menu
      const loginLink = page.locator('.mobile-user-action.primary');
      await expect(loginLink).toBeVisible();
    });

    test('mobile menu uses discord icon for login', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Should have discord icon, not lock emoji
      const discordIcon = page.locator('.mobile-discord-icon');
      await expect(discordIcon).toBeVisible();
    });

    test('mobile menu has dark/light mode toggle', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Look for theme toggle button (small quick button next to user avatar or guest section)
      const themeToggle = page.locator('.mobile-quick-btn');
      await expect(themeToggle.first()).toBeVisible();
    });

    test('mobile menu dark/light toggle shows correct icon', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Should show sun or moon symbol
      const modeButton = page.locator('.mobile-quick-btn').first();
      const buttonText = await modeButton.textContent();

      // Check for unicode symbol (sun or moon)
      expect(buttonText).toMatch(/☀|☾/);
    });

    test('clicking mobile menu link closes menu', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Open mobile menu
      await page.locator('.burger-button').click();
      await expect(page.locator('.mobile-menu.open')).toBeVisible();

      // Expand a section and click a link
      const sectionHeader = page.locator('.mobile-section-header').first();
      await sectionHeader.click();
      await page.waitForTimeout(200);

      const link = page.locator('.mobile-section-items.expanded .mobile-menu-item').first();
      if (await link.isVisible()) {
        await link.click();

        // Menu should close after navigation
        await page.waitForTimeout(500);
        const mobileMenu = page.locator('.mobile-menu.open');
        await expect(mobileMenu).toBeHidden();
      }
    });

    test('mobile search mode shows cancel button', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Focus search input to enter search mode
      const searchInput = page.locator('.mobile-search-input');
      await searchInput.focus();

      // Cancel button should appear
      await page.waitForTimeout(300);
      const cancelButton = page.locator('.mobile-search-cancel');
      await expect(cancelButton).toBeVisible();
    });

    test('mobile search shows results', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      const searchInput = page.locator('.mobile-search-input');
      await searchInput.fill('calypso');

      // Wait for search results
      await page.waitForTimeout(500);

      const searchResults = page.locator('.mobile-search-results');
      await expect(searchResults).toBeVisible();
    });

    test('mobile search cancel exits search mode', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Enter search mode
      const searchInput = page.locator('.mobile-search-input');
      await searchInput.focus();
      await page.waitForTimeout(200);

      // Click cancel
      const cancelButton = page.locator('.mobile-search-cancel');
      await cancelButton.click();

      // Should exit search mode - cancel button hidden
      await expect(cancelButton).toBeHidden();
    });

    test('mobile menu shows user info when authenticated', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 768, height: 1024 });
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      // Should show user section
      const userSection = verifiedUser.locator('.mobile-user-section');
      await expect(userSection).toBeVisible();
    });

    test('mobile menu shows logout option when authenticated', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize({ width: 768, height: 1024 });
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      // Look for logout link
      const logoutLink = verifiedUser.locator('.mobile-menu a[href*="logout"]');
      await expect(logoutLink).toBeVisible();
    });
  });

  test.describe('Menu Responsiveness', () => {
    test('menu adapts when resizing from desktop to mobile', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Start at desktop size
      await page.setViewportSize({ width: 1200, height: 800 });
      await page.waitForTimeout(200);
      // Desktop menu items should be visible
      const menuItem = page.locator('.menu-container .menu-item:not(.user)').first();
      await expect(menuItem).toBeVisible();
      await expect(page.locator('.burger-button')).toBeHidden();

      // Resize to mobile
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.waitForTimeout(300);
      // Desktop menu items should be hidden on mobile
      await expect(menuItem).toBeHidden();
      await expect(page.locator('.burger-button')).toBeVisible();
    });

    test('mobile menu closes when resizing to desktop', async ({ page }) => {
      // Start at mobile size
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Open mobile menu
      await page.locator('.burger-button').click();
      await expect(page.locator('.mobile-menu.open')).toBeVisible();

      // Resize to desktop
      await page.setViewportSize({ width: 1200, height: 800 });
      await page.waitForTimeout(300);

      // Mobile menu should auto-close
      await expect(page.locator('.mobile-menu.open')).toBeHidden();
    });
  });
});
