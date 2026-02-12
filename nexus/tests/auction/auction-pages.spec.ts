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

test.describe('Auction Listing Page', () => {
  test('loads and shows auction listing', async ({ page }) => {
    await page.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Auctions');
  });

  test('has search and filter controls', async ({ page }) => {
    await page.goto('/market/auction', { waitUntil: 'networkidle' });
    await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
    await expect(page.locator('select')).toHaveCount(2); // status + sort
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
    // Should redirect to login
    expect(page.url()).toContain('/discord/login');
  });

  test('loads for verified users', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction/create', { waitUntil: 'networkidle' });
    await expect(verifiedUser.locator('h1')).toContainText('Create Auction');
  });

  test('has required form sections', async ({ verifiedUser }) => {
    await verifiedUser.goto('/market/auction/create', { waitUntil: 'networkidle' });

    // Item Set section
    await expect(verifiedUser.locator('text=Item Set')).toBeVisible();

    // Pricing section
    await expect(verifiedUser.locator('text=Pricing')).toBeVisible();
    await expect(verifiedUser.locator('#starting-bid')).toBeVisible();

    // Duration section
    await expect(verifiedUser.locator('text=Duration')).toBeVisible();

    // Details section
    await expect(verifiedUser.locator('#auction-title')).toBeVisible();
  });
});

test.describe('My Auctions Page', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/market/auction/my', { waitUntil: 'networkidle' });
    expect(page.url()).toContain('/discord/login');
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

    // Auction card should be a link now, not disabled
    const auctionLink = page.locator('a[href="/market/auction"]');
    await expect(auctionLink).toBeVisible();

    // Should NOT have "Coming Soon" badge
    await expect(page.locator('text=Coming Soon')).not.toBeVisible();
  });
});
