import { test, expect } from '@playwright/test';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

const API_BASE = 'http://dev.entropianexus.com:3100';

/**
 * ClassId E2E Tests
 *
 * Verifies:
 * 1. ClassId field present in all entity responses (string or null)
 * 2. ClassId lookup via C-prefix (e.g., /weapons/C12345)
 * 3. Case-insensitivity of C-prefix
 * 4. 404 for unknown ClassId
 * 5. ClassId in Items composite endpoint
 */

// Endpoints that should include ClassId in their responses
const ENTITY_ENDPOINTS = [
  '/weapons', '/armors', '/materials', '/blueprints', '/vehicles',
  '/clothings', '/consumables', '/capsules', '/pets', '/strongboxes',
  '/armorsets', '/medicaltools', '/misctools', '/refiners', '/scanners',
  '/finders', '/excavators', '/blueprintbooks', '/medicalchips',
  '/teleportationchips', '/effectchips', '/weaponamplifiers',
  '/weaponvisionattachments', '/absorbers', '/finderamplifiers',
  '/armorplatings', '/enhancers', '/mindforce', '/furniture',
  '/decorations', '/storagecontainers', '/signs',
  '/mobs', '/skills', '/professions',
];

test.describe('ClassId - Field Presence', () => {
  for (const endpoint of ENTITY_ENDPOINTS) {
    test(`${endpoint}: responses include ClassId field`, async ({ request }) => {
      const response = await request.get(`${API_BASE}${endpoint}`, { timeout: TIMEOUT_LONG });
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);

      if (data.length === 0) {
        test.skip();
        return;
      }

      // Every entity should have a ClassId property (string or null)
      const first = data[0];
      expect(first).toHaveProperty('ClassId');
      expect(first.ClassId === null || typeof first.ClassId === 'string').toBe(true);

      // Verify ClassId comes after Id in the response structure
      const keys = Object.keys(first);
      const idIdx = keys.indexOf('Id');
      const classIdIdx = keys.indexOf('ClassId');
      expect(idIdx).toBeGreaterThanOrEqual(0);
      expect(classIdIdx).toBeGreaterThan(idIdx);
    });
  }
});

test.describe('ClassId - Items Composite Endpoint', () => {
  test('/items: responses include ClassId field', async ({ request }) => {
    const response = await request.get(`${API_BASE}/items`, { timeout: TIMEOUT_LONG });
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);

    if (data.length === 0) {
      test.skip();
      return;
    }

    const first = data[0];
    expect(first).toHaveProperty('ClassId');
    expect(first.ClassId === null || typeof first.ClassId === 'string').toBe(true);
  });
});

test.describe('ClassId - Lookup by C-prefix', () => {
  test('returns 404 for non-existent ClassId', async ({ request }) => {
    const response = await request.get(`${API_BASE}/weapons/C99999999999`, { timeout: TIMEOUT_MEDIUM });
    expect(response.status()).toBe(404);
  });

  test('case-insensitive: lowercase c prefix returns 404 for non-existent', async ({ request }) => {
    const response = await request.get(`${API_BASE}/weapons/c99999999999`, { timeout: TIMEOUT_MEDIUM });
    expect(response.status()).toBe(404);
  });

  test('ClassId lookup returns matching entity when ClassId exists', async ({ request }) => {
    // Find an entity that has a ClassId
    const listResponse = await request.get(`${API_BASE}/weapons`, { timeout: TIMEOUT_LONG });
    expect(listResponse.status()).toBe(200);
    const weapons = await listResponse.json();

    const withClassId = weapons.find((w: { ClassId: string | null }) => w.ClassId !== null);
    if (!withClassId) {
      test.skip();
      return;
    }

    // Look up by ClassId with C prefix
    const lookupResponse = await request.get(`${API_BASE}/weapons/C${withClassId.ClassId}`, { timeout: TIMEOUT_MEDIUM });
    expect(lookupResponse.status()).toBe(200);
    const result = await lookupResponse.json();

    expect(result.Id).toBe(withClassId.Id);
    expect(result.Name).toBe(withClassId.Name);
    expect(result.ClassId).toBe(withClassId.ClassId);
  });

  test('ClassId lookup is case-insensitive', async ({ request }) => {
    const listResponse = await request.get(`${API_BASE}/mobs`, { timeout: TIMEOUT_LONG });
    expect(listResponse.status()).toBe(200);
    const mobs = await listResponse.json();

    const withClassId = mobs.find((m: { ClassId: string | null }) => m.ClassId !== null);
    if (!withClassId) {
      test.skip();
      return;
    }

    // Uppercase C
    const upper = await request.get(`${API_BASE}/mobs/C${withClassId.ClassId}`, { timeout: TIMEOUT_MEDIUM });
    expect(upper.status()).toBe(200);
    const upperResult = await upper.json();

    // Lowercase c
    const lower = await request.get(`${API_BASE}/mobs/c${withClassId.ClassId}`, { timeout: TIMEOUT_MEDIUM });
    expect(lower.status()).toBe(200);
    const lowerResult = await lower.json();

    expect(upperResult.Id).toBe(lowerResult.Id);
    expect(upperResult.Name).toBe(lowerResult.Name);
  });
});

test.describe('ClassId - Single Entity Endpoint', () => {
  // Test a few representative endpoints for single-entity ClassId field
  const SINGLE_ENDPOINTS = [
    { collection: '/weapons', label: 'Weapon' },
    { collection: '/mobs', label: 'Mob' },
    { collection: '/skills', label: 'Skill' },
    { collection: '/professions', label: 'Profession' },
  ];

  for (const { collection, label } of SINGLE_ENDPOINTS) {
    test(`${label}: single entity response includes ClassId`, async ({ request }) => {
      const listResponse = await request.get(`${API_BASE}${collection}`, { timeout: TIMEOUT_LONG });
      expect(listResponse.status()).toBe(200);
      const items = await listResponse.json();

      if (items.length === 0) {
        test.skip();
        return;
      }

      // Look up first entity by Id
      const firstId = items[0].Id;
      const singleResponse = await request.get(`${API_BASE}${collection}/${firstId}`, { timeout: TIMEOUT_MEDIUM });
      expect(singleResponse.status()).toBe(200);
      const single = await singleResponse.json();

      expect(single).toHaveProperty('ClassId');
      expect(single.ClassId === null || typeof single.ClassId === 'string').toBe(true);
      // ClassId should match between list and detail
      expect(single.ClassId).toBe(items[0].ClassId);
    });
  }
});
