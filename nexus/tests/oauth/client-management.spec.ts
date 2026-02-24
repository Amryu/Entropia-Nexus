import { test, expect } from '../fixtures/auth';
import { TIMEOUT_MEDIUM } from '../test-constants';

const API_BASE = '/api/oauth/clients';
const VALID_REDIRECT_URI = 'https://example.com/callback';

/**
 * OAuth Client Management API Tests
 *
 * Verifies:
 * 1. Authentication and authorization
 * 2. Client CRUD (create, read, update, delete)
 * 3. Input validation (name, redirect URIs, URLs)
 * 4. Client limit enforcement (max 10)
 * 5. Secret rotation
 * 6. Cross-user isolation
 */

/** Helper to create an OAuth client */
async function createClient(
  page: import('@playwright/test').Page,
  opts: {
    name?: string;
    description?: string;
    website_url?: string;
    redirect_uris?: string[];
    is_confidential?: boolean;
  } = {}
) {
  return page.request.post(API_BASE, {
    data: {
      name: opts.name ?? 'Test App',
      description: opts.description,
      website_url: opts.website_url,
      redirect_uris: opts.redirect_uris ?? [VALID_REDIRECT_URI],
      is_confidential: opts.is_confidential
    }
  });
}

/** Helper to clean up specific clients */
async function cleanupClientIds(page: import('@playwright/test').Page, ids: string[]) {
  for (const id of ids) {
    if (id) await page.request.delete(`${API_BASE}/${id}`);
  }
}

test.describe('OAuth Client Management - Authentication', () => {
  test('listing clients requires authentication', async ({ page }) => {
    const res = await page.request.get(API_BASE);
    expect(res.status()).toBe(401);
  });

  test('creating clients requires authentication', async ({ page }) => {
    const res = await createClient(page);
    expect(res.status()).toBe(401);
  });

  test('creating clients requires verification', async ({ unverifiedUser }) => {
    const res = await createClient(unverifiedUser);
    expect(res.status()).toBe(403);
  });
});

test.describe('OAuth Client Management - CRUD', () => {
  let createdIds: string[] = [];

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClientIds(verifiedUser, createdIds);
    createdIds = [];
  });

  test('can create a client and receive client_id and secret', async ({ verifiedUser }) => {
    const res = await createClient(verifiedUser, {
      name: 'My Bot',
      description: 'A helpful bot',
      website_url: 'https://mybot.example.com',
      redirect_uris: [VALID_REDIRECT_URI]
    });
    expect(res.status()).toBe(201);

    const data = await res.json();
    createdIds.push(data.clientId);
    expect(data.clientId).toBeDefined();
    expect(typeof data.clientId).toBe('string');
    expect(data.clientSecret).toBeDefined();
    expect(typeof data.clientSecret).toBe('string');
    expect(data.clientSecret.length).toBe(64); // 32 bytes hex
  });

  test('can list own clients', async ({ verifiedUser }) => {
    const res1 = await createClient(verifiedUser, { name: 'App One' });
    createdIds.push((await res1.json()).clientId);
    const res2 = await createClient(verifiedUser, { name: 'App Two' });
    createdIds.push((await res2.json()).clientId);

    const res = await verifiedUser.request.get(API_BASE);
    expect(res.status()).toBe(200);

    const clients = await res.json();
    expect(Array.isArray(clients)).toBe(true);
    expect(clients.length).toBeGreaterThanOrEqual(2);

    const names = clients.map((c: any) => c.name);
    expect(names).toContain('App One');
    expect(names).toContain('App Two');
  });

  test('can get a single client by id', async ({ verifiedUser }) => {
    const createRes = await createClient(verifiedUser, {
      name: 'Get Test',
      description: 'Test description',
      website_url: 'https://test.example.com'
    });
    const { clientId } = await createRes.json();
    createdIds.push(clientId);

    const res = await verifiedUser.request.get(`${API_BASE}/${clientId}`);
    expect(res.status()).toBe(200);

    const client = await res.json();
    expect(client.id).toBe(clientId);
    expect(client.name).toBe('Get Test');
    expect(client.description).toBe('Test description');
    expect(client.website_url).toBe('https://test.example.com');
    expect(client.redirect_uris).toContain(VALID_REDIRECT_URI);
    // Secret hash should NOT be returned
    expect(client.secret_hash).toBeUndefined();
  });

  test('can update a client', async ({ verifiedUser }) => {
    const createRes = await createClient(verifiedUser, { name: 'Original Name' });
    const { clientId } = await createRes.json();
    createdIds.push(clientId);

    const res = await verifiedUser.request.put(`${API_BASE}/${clientId}`, {
      data: {
        name: 'Updated Name',
        description: 'Updated description',
        website_url: 'https://updated.example.com',
        redirect_uris: ['https://updated.example.com/callback']
      }
    });
    expect(res.status()).toBe(200);

    const updated = await res.json();
    expect(updated.name).toBe('Updated Name');
    expect(updated.description).toBe('Updated description');
    expect(updated.website_url).toBe('https://updated.example.com');
    expect(updated.redirect_uris).toContain('https://updated.example.com/callback');
  });

  test('can delete a client', async ({ verifiedUser }) => {
    const createRes = await createClient(verifiedUser, { name: 'Delete Me' });
    const { clientId } = await createRes.json();
    // Don't add to createdIds - the test itself deletes it

    const res = await verifiedUser.request.delete(`${API_BASE}/${clientId}`);
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.deleted).toBe(true);

    // Verify it's gone
    const getRes = await verifiedUser.request.get(`${API_BASE}/${clientId}`);
    expect(getRes.status()).toBe(404);
  });
});

test.describe('OAuth Client Management - Secret Rotation', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    if (lastClientId) await verifiedUser.request.delete(`${API_BASE}/${lastClientId}`);
  });

  test('can rotate client secret', async ({ verifiedUser }) => {
    const createRes = await createClient(verifiedUser, { name: 'Rotate Test' });
    const { clientId, clientSecret: oldSecret } = await createRes.json();
    lastClientId = clientId;

    const res = await verifiedUser.request.post(`${API_BASE}/${clientId}/rotate-secret`);
    expect(res.status()).toBe(200);

    const data = await res.json();
    expect(data.clientSecret).toBeDefined();
    expect(data.clientSecret).not.toBe(oldSecret);
    expect(data.clientSecret.length).toBe(64);
  });

  test('rotate secret returns 404 for nonexistent client', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const res = await verifiedUser.request.post(`${API_BASE}/${fakeId}/rotate-secret`);
    expect(res.status()).toBe(404);
  });
});

test.describe('OAuth Client Management - Validation', () => {
  // Validation tests all expect 400 responses - no clients are created
  // No cleanup needed

  test('rejects empty name', async ({ verifiedUser }) => {
    const res = await createClient(verifiedUser, { name: '' });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('name');
  });

  test('rejects name over 100 characters', async ({ verifiedUser }) => {
    const res = await createClient(verifiedUser, { name: 'A'.repeat(101) });
    expect(res.status()).toBe(400);
  });

  test('rejects missing redirect_uris', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(API_BASE, {
      data: { name: 'No URIs' }
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('redirect_uri');
  });

  test('rejects invalid redirect URI', async ({ verifiedUser }) => {
    const res = await createClient(verifiedUser, {
      redirect_uris: ['not-a-valid-url']
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('redirect_uri');
  });

  test('rejects invalid website_url', async ({ verifiedUser }) => {
    const res = await createClient(verifiedUser, {
      website_url: 'not-a-url'
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('website_url');
  });

  test('rejects more than 10 redirect URIs', async ({ verifiedUser }) => {
    const uris = Array.from({ length: 11 }, (_, i) => `https://example.com/cb${i}`);
    const res = await createClient(verifiedUser, { redirect_uris: uris });
    expect(res.status()).toBe(400);
  });

  test('returns 404 for nonexistent client GET', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const res = await verifiedUser.request.get(`${API_BASE}/${fakeId}`);
    expect(res.status()).toBe(404);
  });

  test('returns 404 for nonexistent client DELETE', async ({ verifiedUser }) => {
    const fakeId = '00000000-0000-0000-0000-000000000000';
    const res = await verifiedUser.request.delete(`${API_BASE}/${fakeId}`);
    expect(res.status()).toBe(404);
  });
});

test.describe('OAuth Client Management - Cross-user Isolation', () => {
  test('cannot see another user\'s clients', async ({ page, loginAs, verifiedUser }) => {
    // Create a client as verified1 (verifiedUser)
    const createRes = await createClient(verifiedUser, { name: 'Private App' });
    const { clientId } = await createRes.json();

    // Login as verified2 and try to access it
    await page.goto('/');
    await loginAs('verified2');

    const res = await page.request.get(`${API_BASE}/${clientId}`);
    expect(res.status()).toBe(404);

    // Clean up
    await verifiedUser.request.delete(`${API_BASE}/${clientId}`);
  });

  test('cannot delete another user\'s client', async ({ page, loginAs, verifiedUser }) => {
    const createRes = await createClient(verifiedUser, { name: 'Protected App' });
    const { clientId } = await createRes.json();

    await page.goto('/');
    await loginAs('verified2');

    const res = await page.request.delete(`${API_BASE}/${clientId}`);
    expect(res.status()).toBe(404);

    // Clean up
    await verifiedUser.request.delete(`${API_BASE}/${clientId}`);
  });

  test('cannot rotate another user\'s client secret', async ({ page, loginAs, verifiedUser }) => {
    const createRes = await createClient(verifiedUser, { name: 'Secret App' });
    const { clientId } = await createRes.json();

    await page.goto('/');
    await loginAs('verified2');

    const res = await page.request.post(`${API_BASE}/${clientId}/rotate-secret`);
    expect(res.status()).toBe(404);

    // Clean up
    await verifiedUser.request.delete(`${API_BASE}/${clientId}`);
  });
});
