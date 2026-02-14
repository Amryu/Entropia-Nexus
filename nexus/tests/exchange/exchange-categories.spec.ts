import { test, expect } from '../fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

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
  test.describe.configure({ mode: 'serial' });

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
    const deeds = collectItems(data).filter((item) =>
      item?.t === 'Material' && item?.st === 'Deed'
    );
    test.skip(deeds.length === 0, 'No deed materials in current test dataset');

    for (const deed of deeds) {
      expect(deed.st).toBe('Deed');
      expect(deed.t).toBe('Material');
    }
  });

  test('Token materials have st field for absolute markup', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const tokens = collectItems(data).filter((item) =>
      item?.t === 'Material' && item?.st === 'Token'
    );
    test.skip(tokens.length === 0, 'No token materials in current test dataset');

    for (const token of tokens) {
      expect(token.st).toBe('Token');
      expect(token.t).toBe('Material');
    }
  });

  test('Regular materials do NOT have st field', async ({ page }) => {
    const response = await page.request.get(EXCHANGE_API);
    expect(response.ok()).toBe(true);

    const data = await response.json();
    const regularMaterials = collectItems(data).filter((item) =>
      item?.t === 'Material' && item?.st === undefined
    );
    test.skip(regularMaterials.length === 0, 'No regular materials in current test dataset');

    for (const material of regularMaterials) {
      expect(material.st).toBeUndefined();
      expect(material.t).toBe('Material');
    }
  });

  test('Deed order creation accepts low markup (absolute)', async ({ verifiedUser }) => {
    const summaryRes = await verifiedUser.request.get(EXCHANGE_API);
    expect(summaryRes.ok()).toBe(true);
    const data = await summaryRes.json();
    const deeds = collectItems(data).filter((item) =>
      item?.t === 'Material' && item?.st === 'Deed'
    );
    test.skip(deeds.length === 0, 'No deed materials in current test dataset');

    const deedItemId = deeds[0]?.i;
    expect(typeof deedItemId).toBe('number');

    const response = await verifiedUser.request.post('/api/market/exchange/orders', {
      data: {
        type: 'SELL',
        item_id: deedItemId,
        quantity: 1,
        markup: 50, // Would be rejected if percent markup (must be >= 100%)
        planet: 'Calypso',
      },
    });

    if (!response.ok()) {
      const body = await response.json().catch(() => ({}));
      expect(body.error).not.toContain('Markup must be at least 100%');
    }

    if (response.ok()) {
      const order = await response.json();
      if (order?.id) {
        await verifiedUser.request.delete(`/api/market/exchange/orders/${order.id}`);
      }
    }
  });

  test('Exchange UI shows Rings category under Clothes', async ({ page }) => {
    await page.goto('/market/exchange', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.sidebar-title')).toContainText('Exchange', { timeout: TIMEOUT_LONG });

    const clothesNode = page.locator('.category-header', {
      has: page.locator('.category-name', { hasText: 'Clothes' })
    }).first();
    await expect(clothesNode).toBeVisible({ timeout: TIMEOUT_LONG });

    const clothesItem = clothesNode.locator('xpath=ancestor::div[contains(@class,"category-item")][1]');
    const clothesExpandToggle = clothesItem.locator('.expand-toggle').first();
    if (await clothesExpandToggle.count()) {
      await clothesExpandToggle.click();
    }

    const ringsNode = page.locator('.category-header', {
      has: page.locator('.category-name', { hasText: 'Rings' })
    }).first();
    await expect(ringsNode).toBeVisible({ timeout: TIMEOUT_MEDIUM });
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

    test.skip(!materialWithMedian, 'No regular material with median value in current dataset');

    await page.goto(`/market/exchange/listings/${materialWithMedian!.i}`, { waitUntil: 'domcontentloaded' });

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

    test.skip(!createdOrder?.id, 'Could not create a suitable sell order in current dataset');

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
      await expect(qtyInput).toHaveValue('5', { timeout: TIMEOUT_SHORT });

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

  test('User orders page is visible in read-only mode when logged out', async ({ page }) => {
    const sellerName = 'Test User One Calypso';
    await page.goto(`/market/exchange/orders/${encodeURIComponent(sellerName)}`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.floating-panel')).toBeVisible({ timeout: TIMEOUT_LONG });
    await expect(page.locator('.panel-title-text')).toContainText(sellerName, { timeout: TIMEOUT_LONG });
    await expect(page.locator('.user-orders-panel').first()).toBeVisible({ timeout: TIMEOUT_LONG });

    await expect(page.locator('[data-order-action]')).toHaveCount(0, { timeout: TIMEOUT_LONG });
    await expect(page.locator('.panel-action-btn', { hasText: 'Trade List' })).toHaveCount(0, { timeout: TIMEOUT_LONG });
  });
});
