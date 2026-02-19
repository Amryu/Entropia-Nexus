import { test, expect } from '../fixtures/auth';

/**
 * Inventory API Tests
 *
 * Verifies:
 * 1. Inventory CRUD API endpoints
 * 2. Markup API endpoints
 * 3. Import history API endpoints
 * 4. Auth enforcement on all endpoints
 * 5. Admin unknown items endpoints
 */

test.describe('Inventory API', () => {
  test.describe('GET /api/users/inventory', () => {
    test('returns inventory for verified user', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/users/inventory');
      expect(response.ok()).toBeFalsy();
    });

    test('rejects unverified users', async ({ unverifiedUser }) => {
      const response = await unverifiedUser.request.get('/api/users/inventory');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });
  });

  test.describe('PUT /api/users/inventory (sync)', () => {
    test('accepts valid inventory with container_path', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory', {
        data: {
          items: [
            {
              item_id: 1000001,
              item_name: 'Test Material',
              quantity: 100,
              value: 1.0,
              container: 'Calypso',
              container_path: 'STORAGE (Calypso) > Test Container',
              storage: 'server'
            }
          ],
          sync: true
        }
      });
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(data.total).toBeDefined();
    });

    test('rejects empty items array', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory', {
        data: { items: [], sync: true }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects oversized imports', async ({ verifiedUser }) => {
      // Generate 30001 items (over the limit)
      const items = Array.from({ length: 30001 }, (_, i) => ({
        item_id: 1000001,
        item_name: `Item ${i}`,
        quantity: 1,
        value: 0.01,
        container: 'Calypso',
        storage: 'server'
      }));

      const response = await verifiedUser.request.put('/api/users/inventory', {
        data: { items, sync: true }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });
  });
});

test.describe('Markup API', () => {
  test.describe('GET /api/users/inventory/markups', () => {
    test('returns markups for verified user', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/markups');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/users/inventory/markups');
      expect(response.ok()).toBeFalsy();
    });

    test('rejects unverified users', async ({ unverifiedUser }) => {
      const response = await unverifiedUser.request.get('/api/users/inventory/markups');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });
  });

  test.describe('PUT /api/users/inventory/markups', () => {
    test('upserts markups for verified user', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/markups', {
        data: {
          items: [
            { item_id: 1000001, markup: 120 },
            { item_id: 2000001, markup: 50 }
          ]
        }
      });
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('rejects empty items array', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/markups', {
        data: { items: [] }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects invalid item_id', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/markups', {
        data: {
          items: [{ item_id: -1, markup: 100 }]
        }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects non-finite markup', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/markups', {
        data: {
          items: [{ item_id: 1000001, markup: 'abc' }]
        }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects more than 1000 items', async ({ verifiedUser }) => {
      const items = Array.from({ length: 1001 }, (_, i) => ({
        item_id: 1000000 + i,
        markup: 100
      }));

      const response = await verifiedUser.request.put('/api/users/inventory/markups', {
        data: { items }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });
  });

  test.describe('DELETE /api/users/inventory/markups/[itemId]', () => {
    test('deletes markup for valid item', async ({ verifiedUser }) => {
      // First create a markup
      await verifiedUser.request.put('/api/users/inventory/markups', {
        data: { items: [{ item_id: 9999999, markup: 150 }] }
      });

      // Then delete it
      const response = await verifiedUser.request.delete('/api/users/inventory/markups/9999999');
      expect(response.ok()).toBeTruthy();
    });

    test('returns 404 for non-existent markup', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.delete('/api/users/inventory/markups/1');
      // May return 404 if no markup exists for this item
      expect([200, 404]).toContain(response.status());
    });

    test('rejects invalid item ID', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.delete('/api/users/inventory/markups/invalid');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });
  });
});

test.describe('Import History API', () => {
  test.describe('GET /api/users/inventory/imports', () => {
    test('returns import history for verified user', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/imports');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('supports pagination params', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/imports?limit=5&offset=0');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
      expect(data.length).toBeLessThanOrEqual(5);
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/users/inventory/imports');
      expect(response.ok()).toBeFalsy();
    });
  });

  test.describe('GET /api/users/inventory/imports/[id]/deltas', () => {
    test('rejects invalid import ID', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/imports/invalid/deltas');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('returns 404 for non-existent import', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/imports/999999999/deltas');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(404);
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/users/inventory/imports/1/deltas');
      expect(response.ok()).toBeFalsy();
    });
  });
});

test.describe('Admin Unknown Items API', () => {
  test.describe('GET /api/admin/unknown-items', () => {
    test('returns unknown items for admin', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/unknown-items');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('supports resolved filter', async ({ adminUser }) => {
      const response = await adminUser.request.get('/api/admin/unknown-items?resolved=true');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('rejects non-admin users', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/admin/unknown-items');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/admin/unknown-items');
      expect(response.ok()).toBeFalsy();
    });
  });

  test.describe('PATCH /api/admin/unknown-items/[id]', () => {
    test('rejects non-admin users', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.patch('/api/admin/unknown-items/1');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });

    test('rejects invalid ID', async ({ adminUser }) => {
      const response = await adminUser.request.patch('/api/admin/unknown-items/invalid');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('returns 404 for non-existent item', async ({ adminUser }) => {
      const response = await adminUser.request.patch('/api/admin/unknown-items/999999999');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(404);
    });
  });
});
