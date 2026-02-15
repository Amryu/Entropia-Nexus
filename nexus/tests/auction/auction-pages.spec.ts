import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Auction System Page Tests
 *
 * Verifies:
 * 1. Auction listing page loads and displays content
 * 2. Navigation between auction pages
 * 3. Create page requires verification
 * 4. My Auctions page requires authentication
 * 5. Market overview shows Auction as active (not coming soon)
 */

function expectInAuthFlow(url: string) {
  const inAuthFlow =
    url.includes('/discord/login') ||
    url.includes('discord.com/');
  expect(inAuthFlow).toBeTruthy();
}

test.describe('Auction Listing Page', () => {
  test('loads and shows auction listing', async ({ page }) => {
    await page.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Auctions');
  });

  test('has search and filter controls', async ({ page }) => {
    await page.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(page.getByPlaceholder('Search auctions...')).toBeVisible();
    const filterSelects = page.locator('main select, .page-container select');
    expect(await filterSelects.count()).toBeGreaterThanOrEqual(2); // status + sort
  });

  test('breadcrumb links work', async ({ page }) => {
    await page.goto('/market/auction', { waitUntil: 'networkidle' });
    const marketLink = page.locator('.breadcrumb a[href="/market"]');
    await expect(marketLink).toBeVisible();
  });

  test('shows create button for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('a[href="/market/auction/create"]')).toBeVisible();
  });

  test('shows my auctions button for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('a[href="/market/auction/my"]')).toBeVisible();
  });
});

test.describe('Auction Create Page', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/market/auction/create', { waitUntil: 'networkidle' });
    expectInAuthFlow(page.url());
  });

  test('loads for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction/create', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('h1')).toContainText('Create Auction');
  });

  test('has required form sections', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction/create', { waitUntil: 'networkidle' });

    // Item Set section
    await expect(verifiedUser.getByRole('heading', { name: 'Item Set' })).toBeVisible();

    // Pricing section
    await expect(verifiedUser.getByRole('heading', { name: 'Pricing' })).toBeVisible();
    await expect(verifiedUser.locator('#starting-bid')).toBeVisible();

    // Duration section
    await expect(verifiedUser.getByRole('heading', { name: 'Duration' })).toBeVisible();

    // Details section
    await expect(verifiedUser.locator('#auction-title')).toBeVisible();
  });
});

test.describe('My Auctions Page', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/market/auction/my', { waitUntil: 'networkidle' });
    expectInAuthFlow(page.url());
  });

  test('shows tabs for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction/my', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('h1')).toContainText('My Auctions');
    await expect(verifiedUser.locator('button:has-text("My Auctions")')).toBeVisible();
    await expect(verifiedUser.locator('button:has-text("My Bids")')).toBeVisible();
  });
});

test.describe('Market Overview', () => {
  test('auction is active (not coming soon)', async ({ page }) => {
    await page.goto('/market', { waitUntil: 'networkidle' });

    // Auction card should be a link now, not disabled.
    const auctionCard = page.locator('.secondary-card[href="/market/auction"]').first();
    await expect(auctionCard).toBeVisible();

    // Auction card should not be marked as coming soon.
    await expect(auctionCard).not.toContainText(/coming soon/i);
  });
});
