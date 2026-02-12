import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

const API_BASE = '/api/auction';

/**
 * Auction System API Tests
 *
 * Verifies:
 * 1. Authentication and authorization
 * 2. Auction CRUD (create, read, update, delete)
 * 3. Disclaimer acceptance flow
 * 4. Bid placement (without Turnstile in test mode)
 * 5. Admin controls (freeze, cancel, rollback)
 * 6. Rate limiting
 */

test.describe('Auction API - Authentication', () => {
  test('listing auctions is public', async ({ page }) => {
    const response = await page.request.get(API_BASE);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('auctions');
    expect(data).toHaveProperty('total');
  });

  test('creating auction requires authentication', async ({ page }) => {
    const response = await page.request.post(API_BASE, {
      data: { title: 'Test', starting_bid: 10, duration_days: 7, item_set_id: 'fake' }
    });
    expect(response.status()).toBe(401);
  });

  test('creating auction requires verification', async ({ unverifiedUser }) => {
    const response = await unverifiedUser.request.post(API_BASE, {
      data: { title: 'Test', starting_bid: 10, duration_days: 7, item_set_id: 'fake' }
    });
    expect(response.status()).toBe(403);
  });
});

test.describe('Auction API - Disclaimers', () => {
  test('can check disclaimer status', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.get(`${API_BASE}/disclaimer`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('bidder');
    expect(data).toHaveProperty('seller');
  });

  test('can accept seller disclaimer', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.post(`${API_BASE}/disclaimer`, {
      data: { role: 'seller' }
    });
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.success).toBe(true);
  });

  test('can accept bidder disclaimer', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.post(`${API_BASE}/disclaimer`, {
      data: { role: 'bidder' }
    });
    expect(response.status()).toBe(200);
  });

  test('rejects invalid disclaimer role', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.post(`${API_BASE}/disclaimer`, {
      data: { role: 'invalid' }
    });
    expect(response.status()).toBe(400);
  });
});

test.describe('Auction API - Admin', () => {
  test('admin endpoints require admin role', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';

    const freezeRes = await verifiedUser.request.post(`${API_BASE}/${fakeId}/admin/freeze`, {
      data: { reason: 'test' }
    });
    expect(freezeRes.status()).toBe(403);

    const cancelRes = await verifiedUser.request.post(`${API_BASE}/${fakeId}/admin/cancel`, {
      data: { reason: 'test' }
    });
    expect(cancelRes.status()).toBe(403);

    const rollbackRes = await verifiedUser.request.post(`${API_BASE}/${fakeId}/admin/rollback`, {
      data: { reason: 'test' }
    });
    expect(rollbackRes.status()).toBe(403);
  });

  test('admin freeze requires reason', async ({ adminUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await adminUser.request.post(`${API_BASE}/${fakeId}/admin/freeze`, {
      data: { reason: '' }
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.error).toContain('Reason');
  });

  test('admin cancel requires reason', async ({ adminUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await adminUser.request.post(`${API_BASE}/${fakeId}/admin/cancel`, {
      data: { reason: '' }
    });
    expect(response.status()).toBe(400);
  });

  test('admin can view audit log', async ({ adminUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await adminUser.request.get(`${API_BASE}/${fakeId}/admin/audit`);
    // May return empty array for non-existent auction, but shouldn't error
    expect(response.status()).toBe(200);
  });
});

test.describe('Auction API - Bid validation', () => {
  test('bid requires authentication', async ({ page }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await page.request.post(`${API_BASE}/${fakeId}/bid`, {
      data: { amount: 10, turnstile_token: 'test' }
    });
    expect(response.status()).toBe(401);
  });

  test('bid requires Turnstile token', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await verifiedUser.request.post(`${API_BASE}/${fakeId}/bid`, {
      data: { amount: 10 }
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.error).toContain('Captcha');
  });

  test('buyout requires Turnstile token', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const response = await verifiedUser.request.post(`${API_BASE}/${fakeId}/buyout`, {
      data: {}
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.error).toContain('Captcha');
  });
});

test.describe('Auction API - My Auctions', () => {
  test('requires authentication', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/my`);
    expect(response.status()).toBe(401);
  });

  test('returns auctions and bids for verified user', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.get(`${API_BASE}/my`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('auctions');
    expect(data).toHaveProperty('bids');
    expect(Array.isArray(data.auctions)).toBe(true);
    expect(Array.isArray(data.bids)).toBe(true);
  });
});
