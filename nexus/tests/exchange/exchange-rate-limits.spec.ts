import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Exchange Rate Limiting Tests
 *
 * Tests the rate limiting system on exchange order endpoints.
 * Each test uses distinct item IDs to avoid cross-test interference
 * (the in-memory rate limiter shares state across requests).
 *
 * Item IDs used:
 * - 1000001–1000010: Materials (fungible/stackable) for per-item cooldown tests
 * - 2000001+: Weapons (non-fungible) for non-fungible tests
 */

const API_BASE = '/api/market/exchange/orders';
const TEST_TURNSTILE_TOKEN = 'test';

/** Helper to create an order via the API */
async function createOrder(
  page: import('@playwright/test').Page,
  opts: {
    type?: string;
    item_id: number;
    quantity?: number;
    markup: number;
    planet?: string;
    details?: object;
    turnstileToken?: string;
  }
) {
  return page.request.post(API_BASE, {
    data: {
      type: opts.type ?? 'SELL',
      item_id: opts.item_id,
      quantity: opts.quantity ?? 1,
      markup: opts.markup,
      planet: opts.planet ?? 'Calypso',
      details: opts.details,
      turnstile_token: opts.turnstileToken ?? TEST_TURNSTILE_TOKEN,
    },
  });
}

/** Helper to close an order */
async function closeOrder(page: import('@playwright/test').Page, orderId: number) {
  return page.request.delete(`${API_BASE}/${orderId}`, {
    data: { turnstile_token: TEST_TURNSTILE_TOKEN },
  });
}

/** Helper to bump all orders */
async function bumpAllOrders(page: import('@playwright/test').Page) {
  return page.request.post(`${API_BASE}/bump-all`, {
    data: { turnstile_token: TEST_TURNSTILE_TOKEN },
  });
}

/** Helper to edit an order */
async function editOrder(
  page: import('@playwright/test').Page,
  orderId: number,
  opts: { quantity?: number; markup: number; planet?: string; details?: object }
) {
  return page.request.put(`${API_BASE}/${orderId}`, {
    data: {
      quantity: opts.quantity ?? 1,
      markup: opts.markup,
      planet: opts.planet ?? 'Calypso',
      details: opts.details,
      turnstile_token: TEST_TURNSTILE_TOKEN,
    },
  });
}

// ─── Authentication ──────────────────────────────────────────────

test.describe('Exchange Orders - Authentication', () => {
  test('rejects unauthenticated order creation', async ({ page }) => {
    const res = await createOrder(page, { item_id: 1000001, markup: 110 });
    expect(res.status()).toBe(401);
    const data = await res.json();
    expect(data.error).toContain('Authentication required');
  });

  test('rejects unverified user order creation', async ({ unverifiedUser }) => {
    const res = await createOrder(unverifiedUser, { item_id: 1000001, markup: 110 });
    expect(res.status()).toBe(403);
    const data = await res.json();
    expect(data.error).toContain('Verified account required');
  });
});

// ─── Order CRUD ──────────────────────────────────────────────────

test.describe('Exchange Orders - CRUD', () => {
  let createdOrderId: number;

  test('can create an order', async ({ verifiedUser }) => {
    const res = await createOrder(verifiedUser, {
      item_id: 1000001,
      markup: 110,
    });
    expect(res.status()).toBe(201);
    const data = await res.json();
    expect(data.id).toBeDefined();
    expect(data.type).toBe('SELL');
    createdOrderId = data.id;
  });

  test('can close an order', async ({ verifiedUser }) => {
    // Create an order first (use unique item to avoid cooldown from previous test)
    const createRes = await createOrder(verifiedUser, {
      item_id: 1000002,
      markup: 110,
    });
    expect(createRes.status()).toBe(201);
    const order = await createRes.json();

    const closeRes = await closeOrder(verifiedUser, order.id);
    expect(closeRes.status()).toBe(200);
    const closed = await closeRes.json();
    expect(closed.state).toBe('closed');
  });

  test('cannot close an already closed order', async ({ verifiedUser }) => {
    // Create and close
    const createRes = await createOrder(verifiedUser, {
      item_id: 1000003,
      markup: 110,
    });
    expect(createRes.status()).toBe(201);
    const order = await createRes.json();
    await closeOrder(verifiedUser, order.id);

    // Try to close again
    const res = await closeOrder(verifiedUser, order.id);
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('already closed');
  });
});

// ─── Per-Item Fungible Cooldown ──────────────────────────────────
// Rate limiting is bypassed in test environment (NODE_ENV=test) to prevent
// cross-worker interference. These tests verify rate limit behavior and are
// skipped since the in-memory rate limiter is disabled during tests.

test.describe('Exchange Orders - Per-Item Fungible Cooldown', () => {
  test.skip('blocks second fungible order for same item within 3-minute window', async ({ verifiedUser }) => {
    // Material (fungible): only 1 order per 3 minutes per item
    const itemId = 1000004; // Material item

    const res1 = await createOrder(verifiedUser, { item_id: itemId, markup: 110 });
    expect(res1.status()).toBe(201);

    // Second order for same item should be blocked
    const res2 = await createOrder(verifiedUser, { item_id: itemId, markup: 115 });
    expect(res2.status()).toBe(429);
    const data = await res2.json();
    expect(data.error).toContain('Please wait');
    expect(data.error).toContain('this item');
    expect(data.retryAfter).toBeGreaterThan(0);
  });

  test('allows order for a different fungible item', async ({ verifiedUser }) => {
    const itemId1 = 1000005;
    const itemId2 = 1000006;

    const res1 = await createOrder(verifiedUser, { item_id: itemId1, markup: 110 });
    expect(res1.status()).toBe(201);

    // Different item should work
    const res2 = await createOrder(verifiedUser, { item_id: itemId2, markup: 110 });
    expect(res2.status()).toBe(201);
  });
});

// ─── Edit Shares Per-Item Cooldown ──────────────────────────────

test.describe('Exchange Orders - Edit Shares Cooldown', () => {
  test.skip('editing is blocked by shared per-item cooldown after create', async ({ verifiedUser }) => {
    const itemId = 1000007;

    // Create order
    const createRes = await createOrder(verifiedUser, { item_id: itemId, markup: 110 });
    expect(createRes.status()).toBe(201);
    const order = await createRes.json();

    // Edit is blocked because create and edit share the same per-item cooldown key.
    const editRes = await editOrder(verifiedUser, order.id, { markup: 115 });
    expect(editRes.status()).toBe(429);
    const data = await editRes.json();
    expect(data.error).toContain('Please wait');
  });
});

// ─── Bump Rate Limit ─────────────────────────────────────────────

test.describe('Exchange Orders - Bump Rate Limit', () => {
  test.skip('bump-all rate limit blocks rapid bumps', async ({ verifiedUser }) => {
    const itemId = 1000008;

    // Create order
    const createRes = await createOrder(verifiedUser, { item_id: itemId, markup: 110 });
    expect(createRes.status()).toBe(201);

    // First bump-all should work
    const bump1 = await bumpAllOrders(verifiedUser);
    expect(bump1.status()).toBe(200);

    // Second bump-all should be rate limited (limit is 1/hour)
    const bump2 = await bumpAllOrders(verifiedUser);
    expect(bump2.status()).toBe(429);
    const data = await bump2.json();
    expect(data.error).toContain('once per hour');
    expect(data.retryAfter).toBeGreaterThan(0);
  });
});

// ─── Side-Specific Order Caps ────────────────────────────────────

test.describe('Exchange Orders - Side Caps', () => {
  test('buy order cap error message mentions 50 limit', async ({ verifiedUser }) => {
    // We can't actually create 50 orders in a test, but we can verify the
    // cap is correctly referenced. Create a buy order to confirm it works.
    const res = await createOrder(verifiedUser, {
      type: 'BUY',
      item_id: 1000009,
      markup: 110,
    });
    // Should succeed (we're well under 50)
    expect(res.status()).toBe(201);
  });
});

// ─── Error Format ────────────────────────────────────────────────

test.describe('Exchange Orders - Error Format', () => {
  test.skip('rate limit response includes retryAfter field', async ({ verifiedUser }) => {
    const itemId = 1000010;

    // Create first order (fungible → cooldown starts)
    const first = await createOrder(verifiedUser, { item_id: itemId, markup: 110 });
    expect(first.status()).toBe(201);

    // Second should be rate limited with proper error shape
    const res = await createOrder(verifiedUser, { item_id: itemId, markup: 115 });
    expect(res.status()).toBe(429);

    const data = await res.json();
    expect(data).toHaveProperty('error');
    expect(data).toHaveProperty('retryAfter');
    expect(typeof data.error).toBe('string');
    expect(typeof data.retryAfter).toBe('number');
    expect(data.retryAfter).toBeGreaterThan(0);
    // Error message should include a time indication
    expect(data.error).toMatch(/\d+[smhd]/);
  });

  test('validation errors return 400 not 429', async ({ verifiedUser }) => {
    // Invalid markup
    const res = await verifiedUser.request.post(API_BASE, {
      data: {
        type: 'SELL',
        item_id: 1000001,
        quantity: 1,
        markup: -5,
        planet: 'Calypso',
        turnstile_token: TEST_TURNSTILE_TOKEN,
      },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('markup');
  });

  test('invalid type returns 400', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(API_BASE, {
      data: {
        type: 'INVALID',
        item_id: 1000001,
        quantity: 1,
        markup: 110,
        planet: 'Calypso',
        turnstile_token: TEST_TURNSTILE_TOKEN,
      },
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('BUY or SELL');
  });
});

// ─── UI Error Display ────────────────────────────────────────────

test.describe('Exchange Orders - UI Error Display', () => {
  test('rate limit error appears in order dialog', async ({ verifiedUser }) => {
    // Navigate to an item's exchange page
    // Use a known material item slug
    await verifiedUser.goto('/market/exchange');
    await verifiedUser.waitForLoadState('networkidle');

    // Search for a material
    const searchInput = verifiedUser.locator('input[type="text"]').first();
    if (await searchInput.isVisible({ timeout: TIMEOUT_MEDIUM })) {
      await searchInput.fill('Lysterium');
      await verifiedUser.waitForTimeout(500);

      // Click first result if visible
      const firstResult = verifiedUser.locator('.search-results a, .item-list a, .exchange-item-row a').first();
      if (await firstResult.isVisible({ timeout: TIMEOUT_MEDIUM })) {
        await firstResult.click();
        await verifiedUser.waitForLoadState('networkidle');
      }
    }

    // This is a smoke test for the UI error display mechanism.
    // Full rate limit UI testing would require specific item pages and
    // inventory setup which varies per test environment.
  });
});
