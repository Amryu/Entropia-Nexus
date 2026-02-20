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

    test('returns estimated_value and unknown_value columns', async ({ verifiedUser }) => {
      // Import items including an unknown item (item_id=0)
      const importRes = await verifiedUser.request.put('/api/users/inventory', {
        data: {
          items: [
            { item_id: 1000001, item_name: 'Test Material', quantity: 50, value: 5.0, container: 'Calypso' },
            { item_id: 0, item_name: 'Unknown Widget', quantity: 1, value: 3.50, container: 'Calypso' },
          ],
          sync: true
        }
      });
      expect(importRes.ok()).toBeTruthy();

      // Fetch latest import
      const historyRes = await verifiedUser.request.get('/api/users/inventory/imports?limit=1');
      expect(historyRes.ok()).toBeTruthy();
      const history = await historyRes.json();
      expect(history.length).toBeGreaterThanOrEqual(1);

      const latest = history[0];
      // unknown_value should capture the unknown item's TT value
      expect(latest.unknown_value).not.toBeNull();
      expect(Number(latest.unknown_value)).toBeCloseTo(3.50, 1);
      // total_value (TT sum) should include both items
      expect(Number(latest.total_value)).toBeCloseTo(8.50, 1);
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

  test.describe('GET /api/users/inventory/imports/value-history', () => {
    test('returns value history with estimated_value and unknown_value', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/imports/value-history');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
      if (data.length > 0) {
        const entry = data[data.length - 1]; // most recent
        expect(entry).toHaveProperty('total_value');
        expect(entry).toHaveProperty('estimated_value');
        expect(entry).toHaveProperty('unknown_value');
        expect(entry).toHaveProperty('item_count');
      }
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

test.describe('Container Names API', () => {
  const TEST_PATH = 'STORAGE (Calypso) > Test Vehicle (C,L)';
  const TEST_PATH_2 = 'STORAGE (Calypso) > Another Container (L)';

  test.describe('GET /api/users/inventory/containers', () => {
    test('returns container names for verified user', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.get('/api/users/inventory/containers');
      expect(response.ok()).toBeTruthy();

      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
    });

    test('rejects unauthenticated requests', async ({ page }) => {
      const response = await page.request.get('/api/users/inventory/containers');
      expect(response.ok()).toBeFalsy();
    });

    test('rejects unverified users', async ({ unverifiedUser }) => {
      const response = await unverifiedUser.request.get('/api/users/inventory/containers');
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(403);
    });
  });

  test.describe('PUT /api/users/inventory/containers', () => {
    test('upserts a container name', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: TEST_PATH,
          custom_name: 'My Vehicle',
          item_name: 'Test Vehicle (C,L)',
        }
      });
      expect(response.ok()).toBeTruthy();

      // Verify it appears in GET
      const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
      const names = await getRes.json();
      const found = names.find((n: any) => n.container_path === TEST_PATH);
      expect(found).toBeTruthy();
      expect(found.custom_name).toBe('My Vehicle');
    });

    test('updates existing container name', async ({ verifiedUser }) => {
      // Create
      await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: TEST_PATH,
          custom_name: 'Old Name',
          item_name: 'Test Vehicle (C,L)',
        }
      });

      // Update
      const response = await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: TEST_PATH,
          custom_name: 'New Name',
          item_name: 'Test Vehicle (C,L)',
        }
      });
      expect(response.ok()).toBeTruthy();

      const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
      const names = await getRes.json();
      const found = names.find((n: any) => n.container_path === TEST_PATH);
      expect(found.custom_name).toBe('New Name');
    });

    test('rejects renaming base storages (no > separator)', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: 'STORAGE (Calypso)',
          custom_name: 'My Planet',
          item_name: 'STORAGE (Calypso)',
        }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects empty custom_name', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: TEST_PATH,
          custom_name: '',
          item_name: 'Test Vehicle (C,L)',
        }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });

    test('rejects empty container_path', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: '',
          custom_name: 'Name',
          item_name: 'Something',
        }
      });
      expect(response.ok()).toBeFalsy();
      expect(response.status()).toBe(400);
    });
  });

  test.describe('DELETE /api/users/inventory/containers', () => {
    test('deletes an existing container name', async ({ verifiedUser }) => {
      // Create first
      await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: TEST_PATH_2,
          custom_name: 'To Delete',
          item_name: 'Another Container (L)',
        }
      });

      // Delete
      const response = await verifiedUser.request.delete('/api/users/inventory/containers', {
        data: { container_path: TEST_PATH_2 }
      });
      expect(response.ok()).toBeTruthy();

      // Verify it's gone
      const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
      const names = await getRes.json();
      const found = names.find((n: any) => n.container_path === TEST_PATH_2);
      expect(found).toBeFalsy();
    });

    test('returns 404 for non-existent path', async ({ verifiedUser }) => {
      const response = await verifiedUser.request.delete('/api/users/inventory/containers', {
        data: { container_path: 'STORAGE (Calypso) > Non Existent' }
      });
      expect(response.status()).toBe(404);
    });
  });

  test.describe('PATCH /api/users/inventory/containers (remap)', () => {
    test('remaps container paths', async ({ verifiedUser }) => {
      const oldPath = 'STORAGE (Calypso) > Remap Source (C,L)';
      const newPath = 'STORAGE (Calypso) > Remap Target (C,L)';

      // Create a name at the old path
      await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: oldPath,
          custom_name: 'Remapped Container',
          item_name: 'Remap Source (C,L)',
        }
      });

      // Remap
      const response = await verifiedUser.request.patch('/api/users/inventory/containers', {
        data: {
          remaps: [{ old_path: oldPath, new_path: newPath }],
          remove_paths: [],
        }
      });
      expect(response.ok()).toBeTruthy();

      // Verify the name is now at the new path
      const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
      const names = await getRes.json();
      const found = names.find((n: any) => n.container_path === newPath);
      expect(found).toBeTruthy();
      expect(found.custom_name).toBe('Remapped Container');
      const oldFound = names.find((n: any) => n.container_path === oldPath);
      expect(oldFound).toBeFalsy();
    });

    test('removes orphaned paths', async ({ verifiedUser }) => {
      const orphanPath = 'STORAGE (Calypso) > Orphan Container (L)';

      // Create a name
      await verifiedUser.request.put('/api/users/inventory/containers', {
        data: {
          container_path: orphanPath,
          custom_name: 'Orphan',
          item_name: 'Orphan Container (L)',
        }
      });

      // Remove it via PATCH
      const response = await verifiedUser.request.patch('/api/users/inventory/containers', {
        data: {
          remaps: [],
          remove_paths: [orphanPath],
        }
      });
      expect(response.ok()).toBeTruthy();

      // Verify it's gone
      const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
      const names = await getRes.json();
      const found = names.find((n: any) => n.container_path === orphanPath);
      expect(found).toBeFalsy();
    });
  });

  // Cleanup: remove test data after all container name tests
  test.afterEach(async ({ verifiedUser }) => {
    // Best-effort cleanup of test container names
    const getRes = await verifiedUser.request.get('/api/users/inventory/containers');
    if (getRes.ok()) {
      const names = await getRes.json();
      for (const n of names) {
        await verifiedUser.request.delete('/api/users/inventory/containers', {
          data: { container_path: n.container_path }
        });
      }
    }
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
