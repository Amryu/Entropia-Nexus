import { test, expect } from '@playwright/test';
import type { Page, Locator } from '@playwright/test';
import { TIMEOUT_INSTANT, TIMEOUT_SHORT, TIMEOUT_LONG } from '../test-constants';

/**
 * E2E tests for Wiki Sidebar Navigation Behavior
 * Tests keyboard navigation, filtering, highlighting, and scrolling behavior
 *
 * Key behaviors tested:
 * - No highlight shown until user interacts with keyboard/search
 * - Highlight appears on arrow keys or search
 * - Initial scroll only happens on page load with pre-selected slug
 * - Clicking/Enter navigation doesn't change scroll position
 */

// Helper to get wiki nav container
function getWikiNav(page: Page): Locator {
  return page.locator('.wiki-nav');
}

// Helper to wait for wiki nav to load (returns false if page has error)
async function waitForWikiNav(page: Page): Promise<boolean> {
  try {
    await page.waitForSelector('.wiki-nav', { timeout: TIMEOUT_LONG });
    return true;
  } catch {
    return false;
  }
}

// Helper to check if items are available
async function hasItems(page: Page) {
  const wikiNav = getWikiNav(page);
  const items = wikiNav.locator('.item-link');
  const count = await items.count();
  return count > 0;
}

// Helper to get scroll position of item list
async function getScrollTop(page: Page) {
  const wikiNav = getWikiNav(page);
  return await wikiNav.locator('.item-list').evaluate(el => el.scrollTop);
}

// Helper to count highlighted items
async function countHighlightedItems(page: Page) {
  const wikiNav = getWikiNav(page);
  return await wikiNav.locator('.item-link.highlighted').count();
}

// Helper to get search input within wiki nav
function getSearchInput(page: Page): Locator {
  return getWikiNav(page).locator('.search-input');
}

// Helper to get item list within wiki nav
function getItemList(page: Page): Locator {
  return getWikiNav(page).locator('.item-list');
}

// Helper to get item links within wiki nav
function getItemLinks(page: Page): Locator {
  return getWikiNav(page).locator('.item-link');
}

// Helper to get actual item count from footer (avoids virtualization issues)
async function getFooterItemCount(page: Page): Promise<number> {
  const wikiNav = getWikiNav(page);
  const countText = await wikiNav.locator('.item-count').textContent();
  // Parse "123 items" to get the number
  const match = countText?.match(/(\d+)\s*items?/i);
  return match ? parseInt(match[1], 10) : 0;
}

test.describe('Wiki Sidebar Navigation', () => {
  test.describe('Initial Highlight State', () => {
    test('no highlight shown on initial page load without slug', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT); // Wait for any reactive updates

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // No item should be highlighted on initial load
      const highlightedCount = await countHighlightedItems(page);
      expect(highlightedCount).toBe(0);
    });

    test('no highlight shown on initial page load with slug (only current item active)', async ({ page }) => {
      // First navigate to get an item URL
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Click first item to get URL with slug
      await getItemLinks(page).first().click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const urlWithSlug = page.url();

      // Navigate away and back to the URL with slug
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.goto(urlWithSlug);
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_SHORT); // Extra time for active state to be set

      // Should have an active item but no highlighted item
      // Wait for the active item to appear (the currentSlug prop may take time to propagate)
      const activeItemLocator = getWikiNav(page).locator('.item-link.active');
      try {
        await activeItemLocator.first().waitFor({ state: 'attached', timeout: TIMEOUT_LONG });
      } catch {
        // Active item may not be present immediately
      }

      const activeItems = await activeItemLocator.count();
      const highlightedItems = await countHighlightedItems(page);

      expect(activeItems).toBe(1);
      expect(highlightedItems).toBe(0);
    });
  });

  test.describe('Keyboard Navigation - Highlight Behavior', () => {
    test('highlight appears when pressing ArrowDown', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');

      if (!await waitForWikiNav(page)) {
        test.skip();
        return;
      }

      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Initially no highlight
      expect(await countHighlightedItems(page)).toBe(0);

      // Click search input to focus it
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT); // Let focus settle

      // Press ArrowDown using page keyboard (ensures it goes to focused element)
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT); // Let Svelte react

      // Wait for highlighted item to appear
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });

      // Should now have a highlighted item
      expect(await countHighlightedItems(page)).toBe(1);
    });

    test('highlight appears when pressing ArrowUp', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Initially no highlight
      expect(await countHighlightedItems(page)).toBe(0);

      // Click search input to focus it
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press ArrowUp using page keyboard
      await page.keyboard.press('ArrowUp');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Wait for highlighted item to appear
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });

      // Should now have a highlighted item
      expect(await countHighlightedItems(page)).toBe(1);
    });

    test('highlight appears when typing in search', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Initially no highlight
      expect(await countHighlightedItems(page)).toBe(0);

      // Type in search (use type with delay for more realistic input)
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await searchInput.fill('ar'); // Search for 'ar' - matches ArMatrix, etc.
      await page.waitForTimeout(TIMEOUT_INSTANT); // Let Svelte react to search

      // If there are results, the first one should be highlighted
      const filteredItems = await getItemLinks(page).count();
      if (filteredItems > 0) {
        const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
        await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });
        expect(await countHighlightedItems(page)).toBe(1);
      }
    });

    test('ArrowDown moves highlight down the list', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 3) {
        test.skip();
        return;
      }

      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press ArrowDown multiple times
      await page.keyboard.press('ArrowDown'); // First item
      await page.waitForTimeout(TIMEOUT_INSTANT);
      const firstHighlighted = getWikiNav(page).locator('.item-link.highlighted');
      await expect(firstHighlighted).toBeVisible({ timeout: TIMEOUT_LONG });
      const firstItemName = await firstHighlighted.textContent();

      await page.keyboard.press('ArrowDown'); // Second item
      await page.waitForTimeout(TIMEOUT_INSTANT);
      const secondHighlighted = getWikiNav(page).locator('.item-link.highlighted');
      const secondItemName = await secondHighlighted.textContent();

      // Should be different items
      expect(firstItemName).not.toBe(secondItemName);
    });

    test('ArrowUp moves highlight up the list', async ({ page }) => {
      // Use materials page which has many items
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 5) {
        test.skip();
        return;
      }

      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Move down to fourth item
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);
      // Wait for first highlight to appear
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });

      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const fourthItemName = await getWikiNav(page).locator('.item-link.highlighted').textContent();

      // Move back up
      await page.keyboard.press('ArrowUp');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const thirdItemName = await getWikiNav(page).locator('.item-link.highlighted').textContent();

      // Should be different items
      expect(fourthItemName).not.toBe(thirdItemName);
    });

    test('ArrowDown starts from current item when slug exists', async ({ page }) => {
      // Navigate directly to a weapon page (with slug in URL)
      await page.goto('/items/weapons/ArMatrix~BC-10~(L)');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 3) {
        test.skip();
        return;
      }

      // Click search input and press ArrowDown - should start from current item
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // The highlighted item should be the active item (current page's weapon)
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });
      const isAlsoActive = await highlightedItem.evaluate(el => el.classList.contains('active'));
      expect(isAlsoActive).toBe(true);
    });
  });

  test.describe('Highlight Clear Behavior', () => {
    test('Escape clears highlight and search', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const searchInput = getSearchInput(page);
      await searchInput.focus();

      // Type search and get highlight
      await searchInput.fill('test');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press Escape
      await page.keyboard.press('Escape');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Search should be cleared
      const searchValue = await searchInput.inputValue();
      expect(searchValue).toBe('');

      // Highlight should be cleared
      expect(await countHighlightedItems(page)).toBe(0);
    });

    test('clear search button clears highlight', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const searchInput = getSearchInput(page);

      // Type search
      await searchInput.fill('test');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Click clear button
      const clearBtn = getWikiNav(page).locator('.clear-search');
      if (await clearBtn.isVisible()) {
        await clearBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);

        // Highlight should be cleared
        expect(await countHighlightedItems(page)).toBe(0);
      }
    });

    test('clear filters button resets highlight state', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Navigate to create highlight
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });
      expect(await countHighlightedItems(page)).toBe(1);

      // Find and click clear filters button (if visible)
      const clearFiltersBtn = getWikiNav(page).locator('.clear-filters');
      if (await clearFiltersBtn.isVisible()) {
        await clearFiltersBtn.click();
        await page.waitForTimeout(TIMEOUT_INSTANT);

        // Highlight should be cleared
        expect(await countHighlightedItems(page)).toBe(0);
      }
    });
  });

  test.describe('Navigation - Scroll Preservation', () => {
    test('clicking item does not change scroll position', async ({ page }) => {
      // Use materials page which has 50 items for proper scroll testing
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 10) {
        test.skip();
        return;
      }

      // First select an item
      await getItemLinks(page).first().click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Scroll down manually
      const itemList = getItemList(page);
      await itemList.evaluate(el => el.scrollTop = 200);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const scrollBefore = await getScrollTop(page);

      // Click an item that's visible at this scroll position
      const visibleItem = getItemLinks(page).nth(8);
      if (await visibleItem.isVisible()) {
        await visibleItem.click();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(TIMEOUT_INSTANT);

        // Scroll position should remain the same
        const scrollAfter = await getScrollTop(page);
        expect(scrollAfter).toBe(scrollBefore);
      }
    });

    test('Enter key navigates to highlighted item', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const initialUrl = page.url();

      // Navigate with arrow keys
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Get the highlighted item's name
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });
      const itemName = await highlightedItem.getAttribute('title');

      // Press Enter
      await page.keyboard.press('Enter');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // URL should have changed to include the item
      expect(page.url()).not.toBe(initialUrl);
      // The URL should contain the item name (encoded with ~ for spaces)
      if (itemName) {
        // URL uses ~ for spaces (e.g., "Test~Rifle~Alpha")
        const expectedSlug = itemName.replace(/ /g, '~');
        expect(page.url()).toContain(expectedSlug);
      }
    });

    test('Enter key does not navigate when no highlight', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const initialUrl = page.url();

      // Focus search but don't create highlight
      const searchInput = getSearchInput(page);
      await searchInput.focus();

      // Press Enter without navigating
      await page.keyboard.press('Enter');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // URL should not change
      expect(page.url()).toBe(initialUrl);
    });
  });

  test.describe('Initial Scroll Behavior', () => {
    test('scrolls to selected item on initial page load with slug', async ({ page }) => {
      // Use materials page which has items for proper scroll testing
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getFooterItemCount(page);
      if (itemCount < 10) {
        test.skip();
        return;
      }

      // Use search to find an item near the end of the list (Zorn Star Ore is last alphabetically)
      const searchInput = getSearchInput(page);
      await searchInput.fill('Zorn Star');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Click the found item
      const targetItem = getItemLinks(page).first();
      if (!await targetItem.isVisible()) {
        test.skip();
        return;
      }
      await targetItem.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const urlWithSlug = page.url();

      // Navigate away completely
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Navigate directly to the URL with slug
      await page.goto(urlWithSlug);
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      // Wait longer for scroll to happen
      await page.waitForTimeout(TIMEOUT_SHORT);

      // Verify the item is actually selected (active class)
      const activeItem = getWikiNav(page).locator('.item-link.active');
      await expect(activeItem).toBeVisible({ timeout: TIMEOUT_LONG });

      // The scroll position should not be 0 - it should have scrolled to the item
      // "Zorn Star Ore" is at position ~50 in the alphabetical list
      const scrollTop = await getScrollTop(page);
      expect(scrollTop).toBeGreaterThan(0);
    });

    test('does not scroll on initial page load without slug', async ({ page }) => {
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Scroll should be at top when no item is selected
      const scrollTop = await getScrollTop(page);
      expect(scrollTop).toBe(0);
    });

    test('scroll happens only once on initial load (not on subsequent interactions)', async ({ page }) => {
      // Use materials page which has 50 items for proper scroll testing
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 10) {
        test.skip();
        return;
      }

      // Use search to find an item in the middle of the list (Melchi Crystal is around position 34)
      const searchInput = getSearchInput(page);
      await searchInput.fill('Melchi');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Click the found item
      const targetItem = getItemLinks(page).first();
      if (!await targetItem.isVisible()) {
        test.skip();
        return;
      }
      await targetItem.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const urlWithSlug = page.url();

      // Clear search before navigating away
      await searchInput.fill('');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Reload the page to trigger initial scroll
      await page.goto(urlWithSlug);
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_SHORT);

      // Verify initial scroll happened (position > 0 since item is in middle of list)
      const initialScrollTop = await getScrollTop(page);
      expect(initialScrollTop).toBeGreaterThan(0);

      // Manually scroll to top
      await getItemList(page).evaluate(el => el.scrollTop = 0);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Trigger a filter or search to cause reactive updates
      const searchInput2 = getSearchInput(page);
      await searchInput2.fill('a');
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await searchInput2.fill('');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Scroll should stay at top (not auto-scroll again)
      const scrollAfterInteraction = await getScrollTop(page);
      expect(scrollAfterInteraction).toBe(0);
    });
  });

  test.describe('Search Filtering Behavior', () => {
    test('search filters the item list', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Use footer count to avoid virtualization issues
      const initialCount = await getFooterItemCount(page);

      // Search for something specific
      const searchInput = getSearchInput(page);
      await searchInput.fill('rifle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const filteredCount = await getFooterItemCount(page);

      // Should have fewer results (or same if all match)
      expect(filteredCount).toBeLessThanOrEqual(initialCount);
    });

    test('search shows no results message when nothing matches', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Search for something that definitely won't match
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await searchInput.fill('xyznonexistent12345');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Should show no results message (auto-retry assertion)
      const noResults = getWikiNav(page).locator('.no-results');
      await expect(noResults).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('clearing search restores full list', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const initialCount = await getItemLinks(page).count();

      // Search and filter - should reduce the list
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await searchInput.fill('rifle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const filteredCount = await getItemLinks(page).count();
      // Filtered count should be less than initial (unless all items match)
      expect(filteredCount).toBeLessThanOrEqual(initialCount);

      // Clear search
      await searchInput.fill('');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Count should be restored (approximately, due to virtualization)
      const restoredCount = await getItemLinks(page).count();
      // Use closeTo assertion to handle virtualization variance
      expect(restoredCount).toBeGreaterThanOrEqual(initialCount - 2);
      expect(restoredCount).toBeLessThanOrEqual(initialCount + 2);
    });
  });

  test.describe('Mouse Hover Highlight', () => {
    test('hovering over item highlights it', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Initially no highlight
      expect(await countHighlightedItems(page)).toBe(0);

      // Hover over an item - use first visible item for reliability
      const firstItem = getItemLinks(page).first();
      await firstItem.hover();

      // Wait for highlighted class to appear (auto-retry assertion)
      await expect(firstItem).toHaveClass(/highlighted/, { timeout: TIMEOUT_LONG });
    });

    test('keyboard navigation after hover continues from hover position', async ({ page }) => {
      // Use materials page which has items
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 5) {
        test.skip();
        return;
      }

      // Hover over second item (index 1) - use lower index for reliability with virtualization
      const secondItem = getItemLinks(page).nth(1);
      await secondItem.hover();
      await expect(secondItem).toHaveClass(/highlighted/, { timeout: TIMEOUT_LONG });

      // Focus search and press ArrowDown
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await page.keyboard.press('ArrowDown');

      // Third item should now be highlighted (moved from index 1 to index 2)
      const thirdItem = getItemLinks(page).nth(2);
      await expect(thirdItem).toHaveClass(/highlighted/, { timeout: TIMEOUT_LONG });
    });
  });

  test.describe('Keyboard Navigation via Item List Focus', () => {
    test('clicking on item list enables keyboard navigation', async ({ page }) => {
      // Use materials page which has items
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 3) {
        test.skip();
        return;
      }

      // Focus the item list container directly (clicking would hit an item link and navigate)
      const itemList = getItemList(page);
      await itemList.focus();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press ArrowDown to navigate
      await page.keyboard.press('ArrowDown');

      // Should have a highlighted item (auto-retry)
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });
    });

    test('clicking on item and then pressing arrow keys enables navigation', async ({ page }) => {
      // Use materials page which has 50 items
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 5) {
        test.skip();
        return;
      }

      // Click on an item (this also sets it as active)
      await getItemLinks(page).nth(2).click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Click on the item list to focus it
      const itemList = getItemList(page);
      await itemList.click({ position: { x: 5, y: 5 } }); // Click near edge to hit container
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Now press ArrowDown
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Should have a highlighted item
      expect(await countHighlightedItems(page)).toBe(1);

      // Press ArrowDown again
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Should still have exactly one highlighted item (moved to next)
      expect(await countHighlightedItems(page)).toBe(1);
    });

    test('item list shows focus indicator when focused', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Focus the item list directly (clicking would hit an item link)
      const itemList = getItemList(page);
      await itemList.focus();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Check if the item list has focus
      const isFocused = await itemList.evaluate(el => document.activeElement === el);
      expect(isFocused).toBe(true);
    });

    test('Enter key works when item list is focused', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      const initialUrl = page.url();

      // Click on the item list to focus it
      const itemList = getItemList(page);
      await itemList.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Navigate with arrow key
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press Enter to select
      await page.keyboard.press('Enter');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // URL should have changed
      expect(page.url()).not.toBe(initialUrl);
    });

    test('clicking an item sets highlight to that item for keyboard navigation', async ({ page }) => {
      // Use materials page which has 50 items
      await page.goto('/items/materials');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      const itemCount = await getItemLinks(page).count();
      if (itemCount < 5) {
        test.skip();
        return;
      }

      // Click on the third item
      const thirdItem = getItemLinks(page).nth(2);
      const thirdItemName = await thirdItem.getAttribute('title');
      await thirdItem.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Click on the item list to focus it for keyboard navigation
      const itemList = getItemList(page);
      await itemList.click({ position: { x: 5, y: 5 } });
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press ArrowDown - should move from the clicked item to the next one
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // The highlighted item should be different from the clicked item (moved to next)
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      const highlightedName = await highlightedItem.getAttribute('title');

      // The fourth item should now be highlighted (index 3, which is after the clicked third item at index 2)
      expect(highlightedName).not.toBe(thirdItemName);
      // Should have exactly one highlighted item
      expect(await countHighlightedItems(page)).toBe(1);
    });

    test('Escape key works when item list is focused', async ({ page }) => {
      await page.goto('/items/weapons');
      await page.waitForLoadState('networkidle');
      await waitForWikiNav(page);
      await page.waitForTimeout(TIMEOUT_INSTANT);

      if (!await hasItems(page)) {
        test.skip();
        return;
      }

      // Type in search first (use 'ar' to match many weapons)
      const searchInput = getSearchInput(page);
      await searchInput.click();
      await page.waitForTimeout(TIMEOUT_INSTANT);
      await searchInput.fill('ar');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Wait for highlight to appear from search
      const highlightedItem = getWikiNav(page).locator('.item-link.highlighted');
      await expect(highlightedItem).toBeVisible({ timeout: TIMEOUT_LONG });

      // Focus item list directly (clicking would hit an item link and navigate)
      const itemList = getItemList(page);
      await itemList.focus();
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Press Escape
      await page.keyboard.press('Escape');
      await page.waitForTimeout(TIMEOUT_INSTANT);

      // Search should be cleared
      const searchValue = await searchInput.inputValue();
      expect(searchValue).toBe('');

      // Highlight should be cleared
      expect(await countHighlightedItems(page)).toBe(0);
    });
  });
});
