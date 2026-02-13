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
  function collectItems(node: unknown): Array<Record<string, unknown>> {
    if (Array.isArray(node)) return node as Array<Record<string, unknown>>;
    if (!node || typeof node !== 'object') return [];

    const out: Array<Record<string, unknown>> = [];
    for (const value of Object.values(node as Record<string, unknown>)) {
      out.push(...collectItems(value));
    }
    return out;
  }

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

  test('Detail metrics show percent markup for regular material item', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const allItems = collectItems(data);
    const materialWithMedian = allItems.find((item) =>
      item?.t === 'Material' &&
      item?.st === undefined &&
      typeof item?.m === 'number' &&
      Number.isFinite(item.m as number)
    );

    expect(materialWithMedian).toBeDefined();

    await page.goto(`/market/exchange/listings/${materialWithMedian!.i}`, { waitUntil: 'networkidle' });

    const medianValue = page.locator('.detail-title-right .metric').filter({ hasText: 'Median:' }).locator('.metric-value');
    await expect(medianValue).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(medianValue).toContainText('%', { timeout: TIMEOUT_LONG });
    await expect(medianValue).not.toContainText('+', { timeout: TIMEOUT_LONG });
  });

  test('Quick trade quantity is editable and shows owner minimum quantity hint', async ({ page, loginAs }) => {
    await page.goto('/');
    await loginAs('verified2');

    const summaryRes = await page.request.get(EXCHANGE_API);
    expect(summaryRes.ok()).toBe(true);
    const summary = await summaryRes.json();
    const candidates = collectItems(summary)
      .filter((item) =>
        item?.t === 'Material' &&
        item?.st === undefined &&
        Number.isInteger(Number(item?.i))
      )
      .map((item) => Number(item.i))
      .filter((id) => id > 0);

    expect(candidates.length).toBeGreaterThan(0);

    const ordersRes = await page.request.get('/api/market/exchange/orders');
    expect(ordersRes.ok()).toBe(true);
    const existingOrders = await ordersRes.json();

    let createdOrder: any = null;
    let itemId = 0;
    for (const candidateId of candidates.slice(0, 25)) {
      for (const order of existingOrders) {
        if (order?.item_id === candidateId && order?.type === 'SELL' && order?.state !== 'closed') {
          await page.request.delete(`/api/market/exchange/orders/${order.id}`);
        }
      }

      const createRes = await page.request.post('/api/market/exchange/orders', {
        data: {
          type: 'SELL',
          item_id: candidateId,
          quantity: 9,
          min_quantity: 3,
          markup: 110,
          planet: 'Calypso'
        }
      });

      if (createRes.ok()) {
        createdOrder = await createRes.json();
        itemId = candidateId;
        break;
      }
    }

    expect(createdOrder?.id).toBeDefined();

    try {
      await loginAs('verified1');
      await page.goto(`/market/exchange/listings/${itemId}`, { waitUntil: 'networkidle' });

      const buyBtn = page.locator(`[data-trade-buy="${createdOrder.id}"]`).first();
      await expect(buyBtn).toBeVisible({ timeout: TIMEOUT_LONG });
      await buyBtn.click();

      const qtyInput = page.locator('#tradeQty');
      await expect(qtyInput).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(qtyInput).toHaveValue('9');

      await qtyInput.fill('5');
      await expect(qtyInput).toHaveValue('5');
      await page.waitForTimeout(TIMEOUT_MEDIUM);
      await expect(qtyInput).toHaveValue('5');

      const qtyHint = page.locator('.qty-hint');
      await expect(qtyHint).toContainText('Owner minimum');
      await expect(qtyHint).toContainText('3');
      await expect(qtyHint).toContainText('9');
    } finally {
      await loginAs('verified2');
      if (createdOrder?.id) {
        await page.request.delete(`/api/market/exchange/orders/${createdOrder.id}`);
      }
    }
  });

  test('User orders page is visible in read-only mode when logged out', async ({ page, loginAs, logout }) => {
    await page.goto('/');
    await loginAs('verified1');

    const profileRes = await page.request.get('/api/users/profiles/900000000000000001');
    expect(profileRes.ok()).toBe(true);
    const profileData = await profileRes.json();
    const sellerName = profileData?.profile?.euName;
    expect(typeof sellerName).toBe('string');
    expect(sellerName.length).toBeGreaterThan(0);

    await logout();
    await page.goto(`/market/exchange/orders/${encodeURIComponent(sellerName)}`, { waitUntil: 'networkidle' });
    await expect(page.locator('.floating-panel')).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.locator('.panel-title-text')).toContainText(sellerName, { timeout: TIMEOUT_LONG });
    await expect(page.locator('.user-orders-panel')).toBeVisible({ timeout: TIMEOUT_LONG });

    await expect(page.locator('[data-order-action]')).toHaveCount(0, { timeout: TIMEOUT_LONG });
    await expect(page.locator('.panel-action-btn', { hasText: 'Trade List' })).toHaveCount(0, { timeout: TIMEOUT_LONG });
  });
});
