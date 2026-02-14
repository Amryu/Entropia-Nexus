import { test, expect } from '../fixtures/auth';

/**
 * Exchange Batch Order Tests
 *
 * Tests the batch order creation endpoint (/api/market/exchange/orders/batch).
 * Covers authentication, validation, per-item limits, partial success, and rate limits.
 *
 * Item IDs used (9000xxx range — IDs that don't exist in the DB to avoid
 * gendered-type validation and conflicts with exchange-rate-limits.spec.ts):
 * - 9000001–9000010: Single-item batch tests
 * - 9000011–9000020: Multi-item batch tests
 */

const BATCH_API = '/api/market/exchange/orders/batch';
const SINGLE_API = '/api/market/exchange/orders';
const TEST_TURNSTILE_TOKEN = 'test';

/** Helper to create a batch of orders */
async function createBatch(
  page: import('@playwright/test').Page,
  orders: Array<{
    type?: string;
    item_id: number;
    quantity?: number;
    markup: number;
    planet?: string;
    details?: object;
  }>,
  turnstileToken: string = TEST_TURNSTILE_TOKEN
) {
  return page.request.post(BATCH_API, {
    data: {
      orders: orders.map(o => ({
        type: o.type ?? 'SELL',
        item_id: o.item_id,
        quantity: o.quantity ?? 1,
        markup: o.markup,
        planet: o.planet ?? 'Calypso',
        details: o.details,
      })),
      turnstile_token: turnstileToken,
    },
  });
}

/** Helper to create a single order (for pre-populating) */
async function createSingleOrder(
  page: import('@playwright/test').Page,
  opts: { type?: string; item_id: number; quantity?: number; markup: number }
) {
  return page.request.post(SINGLE_API, {
    data: {
      type: opts.type ?? 'SELL',
      item_id: opts.item_id,
      quantity: opts.quantity ?? 1,
      markup: opts.markup,
      planet: 'Calypso',
      turnstile_token: TEST_TURNSTILE_TOKEN,
    },
  });
}

/** Helper to close an order */
async function closeOrder(page: import('@playwright/test').Page, orderId: number) {
  return page.request.delete(`${SINGLE_API}/${orderId}`, {
    data: { turnstile_token: TEST_TURNSTILE_TOKEN },
  });
}

// ─── Authentication ──────────────────────────────────────────────

test.describe('Batch Orders - Authentication', () => {
  test('rejects unauthenticated batch creation', async ({ page }) => {
    const res = await createBatch(page, [{ item_id: 9000001, markup: 110 }]);
    expect(res.status()).toBe(401);
    const data = await res.json();
    expect(data.error).toContain('Authentication required');
  });

  test('rejects unverified user batch creation', async ({ unverifiedUser }) => {
    const res = await createBatch(unverifiedUser, [{ item_id: 9000001, markup: 110 }]);
    expect(res.status()).toBe(403);
    const data = await res.json();
    expect(data.error).toContain('Verified account required');
  });
});

// ─── Validation ──────────────────────────────────────────────────

test.describe('Batch Orders - Validation', () => {
  test('rejects empty orders array', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: { orders: [], turnstile_token: TEST_TURNSTILE_TOKEN },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('non-empty array');
  });

  test('rejects non-array orders', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: { orders: 'not-an-array', turnstile_token: TEST_TURNSTILE_TOKEN },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('non-empty array');
  });

  test('rejects missing turnstile token', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: {
        orders: [{ type: 'SELL', item_id: 9000001, quantity: 1, markup: 110, planet: 'Calypso' }],
      },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha verification required');
  });

  test('rejects batch exceeding MAX_BATCH_SIZE', async ({ verifiedUser }) => {
    // MAX_BATCH_SIZE = 50, send 51
    const orders = Array.from({ length: 51 }, (_, i) => ({
      item_id: 9000001 + (i % 10),
      markup: 110,
    }));
    const res = await createBatch(verifiedUser, orders);
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Maximum');
    expect(data.error).toContain('per batch');
  });

  test('per-order validation errors on invalid type', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: {
        orders: [
          { type: 'INVALID', item_id: 9000002, quantity: 1, markup: 110, planet: 'Calypso' },
        ],
        turnstile_token: TEST_TURNSTILE_TOKEN,
      },
    });
    // All orders failed → 400
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.results[0].success).toBe(false);
    expect(data.results[0].error).toContain('BUY or SELL');
  });

  test('per-order validation errors on negative markup', async ({ verifiedUser }) => {
    const res = await createBatch(verifiedUser, [{ item_id: 9000003, markup: -5 }]);
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.results[0].success).toBe(false);
    expect(data.results[0].error).toContain('markup');
  });
});

// ─── Successful Batch Creation ───────────────────────────────────

test.describe('Batch Orders - Successful Creation', () => {
  const createdOrderIds: number[] = [];

  test.afterAll(async ({ verifiedUser }) => {
    // Clean up created orders
    for (const id of createdOrderIds) {
      await closeOrder(verifiedUser, id);
    }
  });

  test('creates multiple orders in single batch', async ({ verifiedUser }) => {
    const res = await createBatch(verifiedUser, [
      { item_id: 9000011, markup: 110 },
      { item_id: 9000012, markup: 120 },
      { item_id: 9000013, markup: 130 },
    ]);
    expect(res.status()).toBe(201);
    const data = await res.json();

    expect(data.created).toBe(3);
    expect(data.failed).toBe(0);
    expect(data.results).toHaveLength(3);

    for (const result of data.results) {
      expect(result.success).toBe(true);
      expect(result.order.id).toBeDefined();
      expect(result.order.type).toBe('SELL');
      createdOrderIds.push(result.order.id);
    }
  });
});

// ─── Per-Item Limit Enforcement ──────────────────────────────────

test.describe('Batch Orders - Per-Item Limit', () => {
  const createdOrderIds: number[] = [];

  test.afterAll(async ({ verifiedUser }) => {
    for (const id of createdOrderIds) {
      await closeOrder(verifiedUser, id);
    }
  });

  test('enforces per-item limit across orders in same batch', async ({ verifiedUser }) => {
    // MAX_ORDERS_PER_ITEM = 5 — send 6 orders for same item
    const orders = Array.from({ length: 6 }, () => ({
      item_id: 9000004,
      markup: 110,
    }));

    const res = await createBatch(verifiedUser, orders);
    const data = await res.json();

    // Should be 201 since at least some succeeded
    expect(res.status()).toBe(201);
    expect(data.created).toBe(5);
    expect(data.failed).toBe(1);

    // First 5 should succeed, 6th should fail
    for (let i = 0; i < 5; i++) {
      expect(data.results[i].success).toBe(true);
      createdOrderIds.push(data.results[i].order.id);
    }
    expect(data.results[5].success).toBe(false);
    expect(data.results[5].error).toContain('Maximum');
  });

  test('per-item limit accounts for existing orders', async ({ verifiedUser }) => {
    // Create 1 order via single endpoint first
    const singleRes = await createSingleOrder(verifiedUser, { item_id: 9000005, markup: 110 });
    expect(singleRes.status()).toBe(201);
    const singleOrder = await singleRes.json();
    createdOrderIds.push(singleOrder.id);

    // Now batch 5 more for the same item — only 4 should succeed (5 - 1 existing)
    const orders = Array.from({ length: 5 }, () => ({
      item_id: 9000005,
      markup: 115,
    }));

    const res = await createBatch(verifiedUser, orders);
    const data = await res.json();

    expect(res.status()).toBe(201);
    expect(data.created).toBe(4);
    expect(data.failed).toBe(1);

    for (const result of data.results) {
      if (result.success) createdOrderIds.push(result.order.id);
    }
  });
});

// ─── Partial Success ─────────────────────────────────────────────

test.describe('Batch Orders - Partial Success', () => {
  const createdOrderIds: number[] = [];

  test.afterAll(async ({ verifiedUser }) => {
    for (const id of createdOrderIds) {
      await closeOrder(verifiedUser, id);
    }
  });

  test('returns mixed results on partial failure', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: {
        orders: [
          { type: 'SELL', item_id: 9000014, quantity: 1, markup: 110, planet: 'Calypso' },
          { type: 'INVALID', item_id: 9000015, quantity: 1, markup: 110, planet: 'Calypso' },
          { type: 'SELL', item_id: 9000016, quantity: 1, markup: 120, planet: 'Calypso' },
        ],
        turnstile_token: TEST_TURNSTILE_TOKEN,
      },
    });

    // At least one succeeded → 201
    expect(res.status()).toBe(201);
    const data = await res.json();

    expect(data.created).toBe(2);
    expect(data.failed).toBe(1);

    // First order succeeds
    expect(data.results[0].success).toBe(true);
    createdOrderIds.push(data.results[0].order.id);

    // Second order fails (invalid type)
    expect(data.results[1].success).toBe(false);
    expect(data.results[1].error).toContain('BUY or SELL');

    // Third order succeeds
    expect(data.results[2].success).toBe(true);
    createdOrderIds.push(data.results[2].order.id);
  });

  test('response status is 400 when all orders fail', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(BATCH_API, {
      data: {
        orders: [
          { type: 'INVALID', item_id: 9000017, quantity: 1, markup: 110, planet: 'Calypso' },
          { type: 'SELL', item_id: 9000018, quantity: 1, markup: -5, planet: 'Calypso' },
        ],
        turnstile_token: TEST_TURNSTILE_TOKEN,
      },
    });

    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.created).toBe(0);
    expect(data.failed).toBe(2);
    expect(data.results[0].success).toBe(false);
    expect(data.results[1].success).toBe(false);
  });
});

// ─── Rate Limit Pre-Check ────────────────────────────────────────

test.describe('Batch Orders - Rate Limit Pre-Check', () => {
  test('batch pre-checks global rate limit budget', async ({ verifiedUser }) => {
    // The batch endpoint pre-checks that `remaining >= batchSize` before processing.
    // We can't easily exhaust the rate limit (100/min) in a test, but we can verify
    // that a batch of valid orders returns proper rate-limit-related response shape.
    // This is a smoke test that the pre-check doesn't falsely reject small batches.
    const res = await createBatch(verifiedUser, [
      { item_id: 9000019, markup: 110 },
    ]);
    // Should succeed (well under limit)
    expect(res.status()).toBe(201);

    // Clean up
    const data = await res.json();
    if (data.results?.[0]?.order?.id) {
      await closeOrder(verifiedUser, data.results[0].order.id);
    }
  });
});

// ─── Error Response Format ───────────────────────────────────────

test.describe('Batch Orders - Error Format', () => {
  test('batch-level error includes error field', async ({ verifiedUser }) => {
    // Missing orders field entirely
    const res = await verifiedUser.request.post(BATCH_API, {
      data: { turnstile_token: TEST_TURNSTILE_TOKEN },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data).toHaveProperty('error');
    expect(typeof data.error).toBe('string');
  });

  test('per-order errors include error field', async ({ verifiedUser }) => {
    const res = await createBatch(verifiedUser, [{ item_id: -1, markup: 110 }]);
    const data = await res.json();
    expect(data.results[0].success).toBe(false);
    expect(data.results[0]).toHaveProperty('error');
    expect(typeof data.results[0].error).toBe('string');
  });
});
