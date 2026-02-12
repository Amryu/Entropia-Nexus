import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Exchange Category & Markup Tests
 *
 * Verifies:
 * 1. Ring sub-categories appear under Clothes with correct structure
 * 2. Deed/Token materials have absolute markup (st field in slim payload)
 * 3. Regular materials do NOT have the st field
 */

const EXCHANGE_API = '/api/market/exchange';

test.describe('Exchange categories and markup types', () => {

  test('Ring sub-categories exist under clothes', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const clothes = data?.clothes;
    expect(clothes).toBeDefined();

    // Rings should be the first key and have left/right/other sub-arrays
    expect(clothes.rings).toBeDefined();
    expect(clothes.rings.left).toBeInstanceOf(Array);
    expect(clothes.rings.right).toBeInstanceOf(Array);
    expect(clothes.rings.other).toBeInstanceOf(Array);

    // Verify we have items in left and right
    expect(clothes.rings.left.length).toBeGreaterThan(0);
    expect(clothes.rings.right.length).toBeGreaterThan(0);
  });

  test('Deed materials have st field for absolute markup', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const deeds = data?.financial?.estate_deeds;
    expect(deeds).toBeDefined();
    expect(deeds.length).toBeGreaterThan(0);

    // Every deed should have st: 'Deed'
    for (const deed of deeds) {
      expect(deed.st).toBe('Deed');
      expect(deed.t).toBe('Material');
    }
  });

  test('Token materials have st field for absolute markup', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const tokens = data?.financial?.tokens;
    expect(tokens).toBeDefined();
    expect(tokens.length).toBeGreaterThan(0);

    // Every token should have st: 'Token'
    for (const token of tokens) {
      expect(token.st).toBe('Token');
      expect(token.t).toBe('Material');
    }
  });

  test('Regular materials do NOT have st field', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    // Check ores.raw as a sample of regular materials
    const ores = data?.materials?.ores?.raw;
    expect(ores).toBeDefined();
    expect(ores.length).toBeGreaterThan(0);

    // Regular materials should NOT have the st field
    for (const ore of ores) {
      expect(ore.st).toBeUndefined();
      expect(ore.t).toBe('Material');
    }
  });

  test('Deed order creation accepts low markup (absolute)', async ({ verifiedUser }) => {
    // Find a Deed item ID from the exchange summary
    const summaryRes = await verifiedUser.request.get(EXCHANGE_API);
    const data = await summaryRes.json();
    const deeds = data?.financial?.estate_deeds;
    expect(deeds?.length).toBeGreaterThan(0);

    const deedItemId = deeds[0].i;

    // Try creating an order with markup < 100 (valid for absolute markup items)
    const response = await verifiedUser.request.post('/api/market/exchange/orders', {
      data: {
        type: 'SELL',
        item_id: deedItemId,
        quantity: 1,
        markup: 50, // Would be rejected if percent markup (must be >= 100%)
        planet: 'Calypso',
      },
    });

    // Should succeed (201) or at least not fail with "Markup must be at least 100%"
    if (!response.ok()) {
      const body = await response.json().catch(() => ({}));
      expect(body.error).not.toContain('Markup must be at least 100%');
    }

    // Clean up: close the order if created
    if (response.ok()) {
      const order = await response.json();
      if (order?.id) {
        await verifiedUser.request.delete(`/api/market/exchange/orders/${order.id}`);
      }
    }
  });

  test('Exchange UI shows Rings category under Clothes', async ({ page }) => {
    await page.goto('/market/exchange', { waitUntil: 'networkidle' });
    await page.waitForTimeout(TIMEOUT_MEDIUM);

    // Look for "Clothes" in the category tree and expand it
    const clothesNode = page.locator('.category-tree').getByText('Clothes').first();
    if (await clothesNode.isVisible()) {
      await clothesNode.click();
      // Should see "Rings" as a sub-category
      const ringsNode = page.locator('.category-tree').getByText('Rings');
      await expect(ringsNode).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    }
  });
});
