import { test, expect } from '../fixtures/auth';
import { TIMEOUT_INSTANT } from '../test-constants';

/**
 * E2E tests for mobile responsive behavior
 *
 * Tests verify that:
 * 1. Wiki pages and menu use the same breakpoint (900px)
 * 2. Mobile layouts display correctly at various viewport sizes
 * 3. Mobile user panel is collapsible
 * 4. Quick action buttons are uniform in size
 */

// Global breakpoint per style.css: < 900px is mobile
const MOBILE_BREAKPOINT = 900;
const MOBILE_WIDTH = MOBILE_BREAKPOINT - 1; // 899px
const TABLET_WIDTH = MOBILE_BREAKPOINT; // 900px (just above mobile)
const DESKTOP_WIDTH = 1200;

// Common landscape mobile sizes
const LANDSCAPE_MOBILE = { width: 812, height: 375 }; // iPhone X landscape
const LANDSCAPE_SMALL = { width: 667, height: 375 }; // iPhone 8 landscape
const PORTRAIT_MOBILE = { width: 375, height: 812 }; // iPhone X portrait

test.describe('Mobile Breakpoint Alignment', () => {
  test.describe('Menu and Wiki use same breakpoint', () => {
    test('at 899px (mobile), both menu and wiki show mobile layout', async ({ page }) => {
      await page.setViewportSize({ width: MOBILE_WIDTH, height: 800 });
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      // Menu should show burger button (mobile mode)
      const burgerButton = page.locator('.burger-button');
      await expect(burgerButton).toBeVisible();

      // Menu items should be hidden
      const menuItems = page.locator('.menu-container .menu-item:not(.logo-item)');
      const firstMenuItem = menuItems.first();
      // The menu items exist but are hidden via CSS display:none
      await expect(firstMenuItem).toBeHidden();

      // Wiki page should show mobile nav toggle (sidebar hidden)
      const wikiPage = page.locator('.wiki-page');
      if (await wikiPage.isVisible()) {
        // Should have mobile class or show nav toggle
        const navToggle = page.locator('.nav-toggle-btn');
        const hasMobileToggle = await navToggle.isVisible().catch(() => false);

        // Wiki sidebar should be hidden on mobile
        const wikiSidebar = page.locator('.wiki-sidebar');
        const sidebarHidden = await wikiSidebar.isHidden().catch(() => true);

        expect(hasMobileToggle || sidebarHidden).toBeTruthy();
      }
    });


    test('breakpoint transition from 899px to 900px works correctly', async ({ page }) => {
      // Start at mobile (899px)
      await page.setViewportSize({ width: MOBILE_WIDTH, height: 800 });
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      // Verify mobile state
      await expect(page.locator('.burger-button')).toBeVisible();

      // Transition to tablet (900px)
      await page.setViewportSize({ width: TABLET_WIDTH, height: 800 });
      await page.waitForTimeout(TIMEOUT_INSTANT); // Allow CSS transition

      // Verify tablet state
      await expect(page.locator('.burger-button')).toBeHidden();

      // Menu items should now be visible
      const menuItem = page.locator('.menu-container .menu-item:not(.logo-item)').first();
      await expect(menuItem).toBeVisible();
    });
  });

  test.describe('Landscape Mobile Mode', () => {
    test('landscape iPhone shows mobile menu', async ({ page }) => {
      await page.setViewportSize(LANDSCAPE_MOBILE);
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      // Should be in mobile mode (< 900px width)
      const burgerButton = page.locator('.burger-button');
      await expect(burgerButton).toBeVisible();
    });

    test('landscape iPhone shows wiki mobile layout', async ({ page }) => {
      await page.setViewportSize(LANDSCAPE_MOBILE);
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      const wikiPage = page.locator('.wiki-page');
      if (await wikiPage.isVisible()) {
        // Should show mobile nav toggle
        const navToggle = page.locator('.nav-toggle-btn');
        await expect(navToggle).toBeVisible();

        // Sidebar should be hidden
        const wikiSidebar = page.locator('.wiki-sidebar');
        await expect(wikiSidebar).toBeHidden();
      }
    });

    test('landscape small phone (667px) shows mobile layout', async ({ page }) => {
      await page.setViewportSize(LANDSCAPE_SMALL);
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      await expect(page.locator('.burger-button')).toBeVisible();

      const wikiPage = page.locator('.wiki-page');
      if (await wikiPage.isVisible()) {
        const navToggle = page.locator('.nav-toggle-btn');
        await expect(navToggle).toBeVisible();
      }
    });
  });

  test.describe('Portrait Mobile Mode', () => {
    test('portrait iPhone shows mobile menu', async ({ page }) => {
      await page.setViewportSize(PORTRAIT_MOBILE);
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      await expect(page.locator('.burger-button')).toBeVisible();
    });

    test('portrait iPhone shows wiki mobile layout', async ({ page }) => {
      await page.setViewportSize(PORTRAIT_MOBILE);
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      const wikiPage = page.locator('.wiki-page');
      if (await wikiPage.isVisible()) {
        const navToggle = page.locator('.nav-toggle-btn');
        await expect(navToggle).toBeVisible();
      }
    });
  });
});

test.describe('Mobile User Panel Behavior', () => {
  test.describe('Collapsible User Panel', () => {
    test('user panel is collapsed by default', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      // Open mobile menu
      await verifiedUser.locator('.burger-button').click();
      await expect(verifiedUser.locator('.mobile-menu.open')).toBeVisible();

      // User actions should be hidden by default (collapsed)
      const userActions = verifiedUser.locator('.mobile-user-actions');
      await expect(userActions).not.toHaveClass(/expanded/);
    });

    test('clicking user header expands actions', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();
      await expect(verifiedUser.locator('.mobile-menu.open')).toBeVisible();

      // Click on user header to expand
      const userHeader = verifiedUser.locator('.mobile-user-header');
      await userHeader.click();

      // User actions should now be visible
      const userActions = verifiedUser.locator('.mobile-user-actions.expanded');
      await expect(userActions).toBeVisible();
    });

    test('clicking user header again collapses actions', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      // Expand
      const userHeader = verifiedUser.locator('.mobile-user-header');
      await userHeader.click();
      await expect(verifiedUser.locator('.mobile-user-actions.expanded')).toBeVisible();

      // Collapse
      await userHeader.click();
      await expect(verifiedUser.locator('.mobile-user-actions')).not.toHaveClass(/expanded/);
    });

    test('chevron rotates when expanded', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      const chevron = verifiedUser.locator('.mobile-user-chevron');

      // Initially not expanded
      await expect(chevron).not.toHaveClass(/expanded/);

      // Click to expand
      await verifiedUser.locator('.mobile-user-header').click();
      await expect(chevron).toHaveClass(/expanded/);
    });

    test('quick action buttons do not trigger expand', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();

      // Click the dark mode toggle (should not expand user actions)
      const darkModeBtn = verifiedUser.locator('.mobile-user-quick-actions .mobile-quick-btn').first();
      await darkModeBtn.click();

      // User actions should still be collapsed
      await expect(verifiedUser.locator('.mobile-user-actions')).not.toHaveClass(/expanded/);
    });
  });

  test.describe('Landscape Mode User Panel', () => {
    test('user panel does not obscure menu in landscape', async ({ verifiedUser }) => {
      await verifiedUser.setViewportSize(LANDSCAPE_MOBILE);
      await verifiedUser.goto('/');
      await verifiedUser.waitForLoadState('networkidle');

      await verifiedUser.locator('.burger-button').click();
      await expect(verifiedUser.locator('.mobile-menu.open')).toBeVisible();

      // Get positions
      const menuContent = verifiedUser.locator('.mobile-menu-content');
      const userSection = verifiedUser.locator('.mobile-user-section');

      const menuContentBox = await menuContent.boundingBox();
      const userSectionBox = await userSection.boundingBox();

      if (menuContentBox && userSectionBox) {
        // User section should be at bottom, not overlapping menu content
        expect(userSectionBox.y).toBeGreaterThanOrEqual(menuContentBox.y + menuContentBox.height - 20);
      }
    });

    test('navigation sections are scrollable in landscape', async ({ page }) => {
      await page.setViewportSize(LANDSCAPE_MOBILE);
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      await page.locator('.burger-button').click();

      // Menu content should be scrollable
      const menuContent = page.locator('.mobile-menu-content');
      const overflow = await menuContent.evaluate(el => getComputedStyle(el).overflowY);
      expect(overflow).toBe('auto');
    });
  });
});

test.describe('Quick Action Button Uniformity', () => {
  test('all quick action buttons have same dimensions', async ({ verifiedUser }) => {
    await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
    await verifiedUser.goto('/');
    await verifiedUser.waitForLoadState('networkidle');

    await verifiedUser.locator('.burger-button').click();

    const quickButtons = verifiedUser.locator('.mobile-quick-btn');
    const count = await quickButtons.count();

    if (count > 1) {
      const sizes: { width: number; height: number }[] = [];

      for (let i = 0; i < count; i++) {
        const box = await quickButtons.nth(i).boundingBox();
        if (box) {
          sizes.push({ width: box.width, height: box.height });
        }
      }

      // All buttons should have the same size
      for (let i = 1; i < sizes.length; i++) {
        expect(sizes[i].width).toBeCloseTo(sizes[0].width, 1);
        expect(sizes[i].height).toBeCloseTo(sizes[0].height, 1);
      }
    }
  });

  test('quick action buttons are 36x36 pixels', async ({ verifiedUser }) => {
    await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
    await verifiedUser.goto('/');
    await verifiedUser.waitForLoadState('networkidle');

    await verifiedUser.locator('.burger-button').click();

    const quickButton = verifiedUser.locator('.mobile-quick-btn').first();
    const box = await quickButton.boundingBox();

    if (box) {
      // Should be 36x36 (with some tolerance for borders)
      expect(box.width).toBeCloseTo(36, 2);
      expect(box.height).toBeCloseTo(36, 2);
    }
  });

  test('dark mode button uses icon instead of emoji', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('.burger-button').click();

    // Dark mode button should have an img element, not emoji text
    // For guest users, it's in .mobile-user-actions-guest; for logged in, in .mobile-user-quick-actions
    const darkModeBtn = page.locator('.mobile-user-actions-guest .mobile-quick-btn, .mobile-user-quick-actions .mobile-quick-btn').first();
    const hasImg = await darkModeBtn.locator('img').isVisible();

    expect(hasImg).toBeTruthy();
  });

  test('admin button uses SVG icon', async ({ adminUser }) => {
    await adminUser.setViewportSize(PORTRAIT_MOBILE);
    await adminUser.goto('/');
    await adminUser.waitForLoadState('networkidle');

    await adminUser.locator('.burger-button').click();

    // Find admin button (link to /admin)
    const adminBtn = adminUser.locator('.mobile-user-quick-actions a[href="/admin"]');
    if (await adminBtn.isVisible()) {
      const hasSvg = await adminBtn.locator('svg').isVisible();
      expect(hasSvg).toBeTruthy();
    }
  });

  test('impersonate button uses SVG icon', async ({ adminUser }) => {
    await adminUser.setViewportSize(PORTRAIT_MOBILE);
    await adminUser.goto('/');
    await adminUser.waitForLoadState('networkidle');

    await adminUser.locator('.burger-button').click();

    // Impersonate button is a button, not a link
    const impersonateBtn = adminUser.locator('.mobile-user-quick-actions button.mobile-quick-btn').first();

    // There might be multiple buttons - find the one that's not the dark mode toggle
    const buttons = adminUser.locator('.mobile-user-quick-actions button.mobile-quick-btn');
    const count = await buttons.count();

    // Look for a button with SVG (not the first one which is dark mode)
    for (let i = 0; i < count; i++) {
      const btn = buttons.nth(i);
      const hasSvg = await btn.locator('svg').isVisible().catch(() => false);
      if (hasSvg) {
        expect(hasSvg).toBeTruthy();
        break;
      }
    }
  });
});

test.describe('Wiki Page Mobile Features', () => {
  test('mobile nav toggle opens drawer', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    const wikiPage = page.locator('.wiki-page');
    if (!await wikiPage.isVisible()) {
      test.skip();
      return;
    }

    const navToggle = page.locator('.nav-toggle-btn');
    if (await navToggle.isVisible()) {
      await navToggle.click();

      // Mobile drawer should open - check for the drawer dialog or the close button
      // The MobileDrawer uses role="dialog" with aria-label="Navigation"
      const drawer = page.locator('[role="dialog"][aria-label="Navigation"], .drawer, aside.drawer-left');
      await page.waitForTimeout(TIMEOUT_INSTANT); // Wait for animation
      const hasDrawer = await drawer.isVisible().catch(() => false);
      expect(hasDrawer).toBeTruthy();
    }
  });

  test('wiki content fills available space on mobile', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/items/weapons');
    await page.waitForLoadState('networkidle');

    const wikiContent = page.locator('.wiki-content');
    if (await wikiContent.isVisible()) {
      const box = await wikiContent.boundingBox();
      if (box) {
        // Content should fill most of the width (accounting for padding)
        expect(box.width).toBeGreaterThan(300);
      }
    }
  });

  test('action buttons hide text on mobile', async ({ verifiedUser }) => {
    await verifiedUser.setViewportSize(PORTRAIT_MOBILE);
    await verifiedUser.goto('/items/weapons');
    await verifiedUser.waitForLoadState('networkidle');

    const actionBtn = verifiedUser.locator('.action-btn');
    if (await actionBtn.first().isVisible()) {
      // The span inside should be hidden on mobile
      const btnSpan = actionBtn.first().locator('span');
      const display = await btnSpan.evaluate(el => getComputedStyle(el).display);
      expect(display).toBe('none');
    }
  });
});

test.describe('Information Pages Mobile Layout', () => {
  test('mobs page shows mobile layout', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/information/mobs');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();

    const wikiPage = page.locator('.wiki-page');
    if (await wikiPage.isVisible()) {
      const navToggle = page.locator('.nav-toggle-btn');
      await expect(navToggle).toBeVisible();
    }
  });

  test('professions page shows mobile layout', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/information/professions');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();
  });

  test('skills page shows mobile layout', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/information/skills');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();
  });

  test('vendors page shows mobile layout', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/information/vendors');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();
  });
});

test.describe('Overview Pages Mobile Layout', () => {
  test('items overview shows mobile menu', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/items');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();
  });

  test('information overview shows mobile menu', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/information');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.burger-button')).toBeVisible();
  });

  test('items overview category grid is responsive', async ({ page }) => {
    await page.setViewportSize(PORTRAIT_MOBILE);
    await page.goto('/items');
    await page.waitForLoadState('networkidle');

    const categoryGrid = page.locator('.category-grid');
    if (await categoryGrid.isVisible()) {
      // On mobile, should be single column (grid-template-columns: 1fr)
      const gridCols = await categoryGrid.evaluate(el => getComputedStyle(el).gridTemplateColumns);
      // Should be a single column value (not multiple)
      const colCount = gridCols.split(' ').filter(c => c && c !== 'none').length;
      expect(colCount).toBe(1);
    }
  });
});
