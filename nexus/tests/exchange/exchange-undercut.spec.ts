import { test, expect } from '../fixtures/auth';
import { TIMEOUT_CACHE } from '../test-constants';

/**
 * Exchange Undercut Enforcement Tests
 *
 * Verifies that orders too close to the best existing offer are rejected (409).
 * Uses two different users so the "exclude own orders" logic is exercised.
 *
 * Item IDs used (real items from the Items table):
 * - 1000100 (Ambulimax Thigh Bone, Material, percent markup)
 * - 2000735 (Ecotron v.42e Prototype, Weapon, absolute markup)
 */

const API_BASE = '/api/market/exchange/orders';
const TEST_TURNSTILE_TOKEN = 'test';

async function createOrder(
  page: import('@playwright/test').Page,
  opts: {
    type?: string;
    item_id: number;
    quantity?: number;
    markup: number;
    planet?: string;
    details?: object;
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
      turnstile_token: TEST_TURNSTILE_TOKEN,
    },
  });
}

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

async function closeOrder(page: import('@playwright/test').Page, orderId: number) {
  return page.request.delete(`${API_BASE}/${orderId}`, {
    data: { turnstile_token: TEST_TURNSTILE_TOKEN },
  });
}

/** Clean up any stale orders in the test item range */
async function cleanupOrders(page: import('@playwright/test').Page, itemIds: number[]) {
  const res = await page.request.get(`${API_BASE}?include_closed=false`);
  if (!res.ok()) return;
  const orders = await res.json();
  if (!Array.isArray(orders)) return;
  for (const order of orders) {
    if (itemIds.includes(order.item_id) && order.state !== 'closed') {
      await closeOrder(page, order.id);
    }
  }
}

// Material item (percent markup): undercut = 2% × (markup - 100), min 0.01%
const MATERIAL_ID = 1000100;
// Weapon item (absolute markup): undercut = 2% × markup, min 0.01 PED
const WEAPON_ID = 2000735;

const TEST_ITEMS = [MATERIAL_ID, WEAPON_ID];

test.setTimeout(TIMEOUT_CACHE);

test.describe('Exchange Undercut Enforcement', () => {
  test.describe.configure({ mode: 'serial' });

  let user1Page: import('@playwright/test').Page;
  let user2Page: import('@playwright/test').Page;

  test.beforeAll(async ({ browser }) => {
    // Create two separate authenticated contexts (verified1 and verified2)
    const ctx1 = await browser.newContext();
    user1Page = await ctx1.newPage();
    await user1Page.goto('/');
    await user1Page.request.post('/api/test/login', { data: { userId: 'verified1' } });

    const ctx2 = await browser.newContext();
    user2Page = await ctx2.newPage();
    await user2Page.goto('/');
    await user2Page.request.post('/api/test/login', { data: { userId: 'verified2' } });

    // Clean up any stale orders from previous runs
    await cleanupOrders(user1Page, TEST_ITEMS);
    await cleanupOrders(user2Page, TEST_ITEMS);
  });

  test.afterAll(async () => {
    // Clean up all test orders
    await cleanupOrders(user1Page, TEST_ITEMS);
    await cleanupOrders(user2Page, TEST_ITEMS);
    await user1Page.context().close();
    await user2Page.context().close();
  });

  // ─── Percent Markup (Materials) ─────────────────────────────────

  test('rejects sell order matching best sell (percent markup)', async () => {
    // User1 creates sell at 150%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 tries to sell at same markup 150% → should be rejected
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r2.status()).toBe(409);
    const data = await r2.json();
    expect(data.error).toContain('undercut');

    await closeOrder(user1Page, order1.id);
  });

  test('rejects sell order within undercut threshold (percent markup)', async () => {
    // User1 creates sell at 150%
    // Undercut amount = 2% × (150 - 100) = 1%, so threshold = 149%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 tries to sell at 149.50% → within (149, 150], should be rejected
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, markup: 149.50 });
    expect(r2.status()).toBe(409);

    await closeOrder(user1Page, order1.id);
  });

  test('allows sell order that properly undercuts (percent markup)', async () => {
    // User1 creates sell at 150%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 sells at 149% (exactly at threshold) → should be allowed
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, markup: 149 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    await closeOrder(user1Page, order1.id);
    await closeOrder(user2Page, order2.id);
  });

  test('allows sell order worse than best (percent markup)', async () => {
    // User1 creates sell at 150%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 sells at 160% (worse price) → should be allowed
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, markup: 160 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    await closeOrder(user1Page, order1.id);
    await closeOrder(user2Page, order2.id);
  });

  // ─── Absolute Markup (Weapons) ──────────────────────────────────

  test('rejects sell order matching best sell (absolute markup)', async () => {
    // User1 creates sell at +10 PED
    const r1 = await createOrder(user1Page, { item_id: WEAPON_ID, markup: 10 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 tries to sell at same +10 PED → rejected
    const r2 = await createOrder(user2Page, { item_id: WEAPON_ID, markup: 10 });
    expect(r2.status()).toBe(409);
    const data = await r2.json();
    expect(data.error).toContain('undercut');

    await closeOrder(user1Page, order1.id);
  });

  test('allows sell order that properly undercuts (absolute markup)', async () => {
    // User1 creates sell at +10 PED
    // Undercut = 2% × 10 = 0.20 PED, threshold = 9.80
    const r1 = await createOrder(user1Page, { item_id: WEAPON_ID, markup: 10 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 sells at +9.80 PED (at threshold) → allowed
    const r2 = await createOrder(user2Page, { item_id: WEAPON_ID, markup: 9.80 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    await closeOrder(user1Page, order1.id);
    await closeOrder(user2Page, order2.id);
  });

  // ─── Buy Orders ─────────────────────────────────────────────────

  test('rejects buy order matching best buy (percent markup)', async () => {
    // User1 creates buy at 130%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, type: 'BUY', markup: 130 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 tries to buy at same 130% → rejected
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, type: 'BUY', markup: 130 });
    expect(r2.status()).toBe(409);
    const data = await r2.json();
    expect(data.error).toContain('outbid');

    await closeOrder(user1Page, order1.id);
  });

  test('allows buy order that properly outbids (percent markup)', async () => {
    // User1 creates buy at 130%
    // Outbid amount = 2% × (130 - 100) = 0.60%, threshold = 130.60%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, type: 'BUY', markup: 130 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 buys at 130.60% (at threshold) → allowed
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, type: 'BUY', markup: 130.60 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    await closeOrder(user1Page, order1.id);
    await closeOrder(user2Page, order2.id);
  });

  // ─── Own Orders (should NOT block) ──────────────────────────────

  test('own orders do not block new orders at same markup', async () => {
    // User1 creates sell at 150%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User1 creates another sell at 150% → allowed (own orders excluded)
    const r2 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    await closeOrder(user1Page, order1.id);
    await closeOrder(user1Page, order2.id);
  });

  // ─── No Existing Orders ─────────────────────────────────────────

  test('allows any markup when no competing orders exist', async () => {
    // No existing orders for this item — any markup is fine
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 100 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    await closeOrder(user1Page, order1.id);
  });

  // ─── Edit Orders ────────────────────────────────────────────────

  test('rejects edit that brings markup into forbidden zone', async () => {
    // User1 creates sell at 150%
    const r1 = await createOrder(user1Page, { item_id: MATERIAL_ID, markup: 150 });
    expect(r1.status()).toBe(201);
    const order1 = await r1.json();

    // User2 creates sell at 160% (allowed, worse price)
    const r2 = await createOrder(user2Page, { item_id: MATERIAL_ID, markup: 160 });
    expect(r2.status()).toBe(201);
    const order2 = await r2.json();

    // User2 tries to edit to 150% → rejected (matches best)
    const editRes = await editOrder(user2Page, order2.id, { markup: 150 });
    expect(editRes.status()).toBe(409);

    await closeOrder(user1Page, order1.id);
    await closeOrder(user2Page, order2.id);
  });
});
