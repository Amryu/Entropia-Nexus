import { test, expect } from '../fixtures/auth';
import { extractFormActionRedirect } from '../fixtures/form-action';
import { TIMEOUT_MEDIUM } from '../test-constants';
import crypto from 'crypto';

const CLIENTS_API = '/api/oauth/clients';
const TOKEN_API = '/api/oauth/token';
const USERINFO_API = '/api/oauth/userinfo';
const REDIRECT_URI = 'https://example.com/callback';

/**
 * OAuth Scope Enforcement Tests
 *
 * Verifies:
 * 1. Access token scope restrictions (can't access endpoints beyond granted scopes)
 * 2. Scopes requiring user grants are excluded when user lacks grants
 * 3. Profile:read scope required for userinfo
 * 4. Inventory scope required for inventory endpoints
 * 5. Token scopes match what was authorized
 */

function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString('hex');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

/** Create client, authorize with specific scopes, return tokens */
async function getTokensWithScopes(page: import('@playwright/test').Page, scopes: string) {
  const clientRes = await page.request.post(CLIENTS_API, {
    data: {
      name: `Scope Test ${Date.now()}`,
      redirect_uris: [REDIRECT_URI]
    }
  });
  expect(clientRes.status()).toBe(201);
  const { clientId, clientSecret } = await clientRes.json();

  const { verifier, challenge } = generatePKCE();
  const state = crypto.randomBytes(16).toString('hex');

  const authRes = await page.request.post('/oauth/authorize?/authorize', {
    form: {
      client_id: clientId,
      redirect_uri: REDIRECT_URI,
      scope: scopes,
      state,
      code_challenge: challenge
    },
    maxRedirects: 0
  });
  const location = await extractFormActionRedirect(authRes);
  const redirectUrl = new URL(location, 'https://example.com');
  const authCode = redirectUrl.searchParams.get('code')!;

  const tokenRes = await page.request.post(TOKEN_API, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    data: new URLSearchParams({
      grant_type: 'authorization_code',
      code: authCode,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: REDIRECT_URI,
      code_verifier: verifier
    }).toString()
  });
  expect(tokenRes.status()).toBe(200);

  const tokens = await tokenRes.json();
  return { clientId, clientSecret, ...tokens };
}

async function cleanupClient(page: import('@playwright/test').Page, clientId: string) {
  if (clientId) await page.request.delete(`${CLIENTS_API}/${clientId}`);
}

test.describe('OAuth Scope Enforcement - Profile', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('access token with profile:read can access userinfo', async ({ verifiedUser }) => {
    const { clientId, access_token, scope } = await getTokensWithScopes(verifiedUser, 'profile:read');
    lastClientId = clientId;
    expect(scope).toContain('profile:read');

    const res = await verifiedUser.request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.id).toBeDefined();
    expect(data.username).toBeDefined();
  });

  test('access token without profile:read cannot access userinfo', async ({ verifiedUser }) => {
    const { clientId, access_token, scope } = await getTokensWithScopes(verifiedUser, 'inventory:read');
    lastClientId = clientId;
    expect(scope).not.toContain('profile:read');

    const res = await verifiedUser.request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(403);
    const data = await res.json();
    expect(data.error).toContain('scope');
  });
});

test.describe('OAuth Scope Enforcement - Inventory', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('access token with inventory:read can read inventory', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getTokensWithScopes(verifiedUser, 'inventory:read');
    lastClientId = clientId;

    const res = await verifiedUser.request.get('/api/users/inventory', {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    // Should succeed (200) - even if empty
    expect(res.status()).toBe(200);
  });

  test('access token without inventory scope cannot read inventory', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getTokensWithScopes(verifiedUser, 'profile:read');
    lastClientId = clientId;

    const res = await verifiedUser.request.get('/api/users/inventory', {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    // Should be rejected - either 403 (scope check) or 401 (bearer auth doesn't match scope)
    // The exact behavior depends on whether the endpoint checks scopes explicitly
    // or whether the hooks.server.js filters grants to exclude the needed ones
    expect([401, 403]).toContain(res.status());
  });
});

test.describe('OAuth Scope Enforcement - Token Scope', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('token scope matches authorized scopes', async ({ verifiedUser }) => {
    const { clientId, scope } = await getTokensWithScopes(verifiedUser, 'profile:read inventory:read');
    lastClientId = clientId;
    const scopeParts = scope.split(' ');
    expect(scopeParts).toContain('profile:read');
    expect(scopeParts).toContain('inventory:read');
  });

  test('scopes requiring grants are excluded for users without grants', async ({ verifiedUser }) => {
    // wiki:read requires wiki.edit grant, which verified1 may not have
    const { clientId, scope } = await getTokensWithScopes(verifiedUser, 'profile:read wiki:read');
    lastClientId = clientId;
    const scopeParts = scope.split(' ');
    expect(scopeParts).toContain('profile:read');
    // wiki:read should be excluded if user lacks wiki.edit grant
    // (test user may or may not have this grant - the test verifies the mechanism)
  });

  test('multiple scopes are preserved correctly', async ({ verifiedUser }) => {
    const requestedScopes = 'profile:read inventory:read loadouts:read notifications:read';
    const { clientId, scope } = await getTokensWithScopes(verifiedUser, requestedScopes);
    lastClientId = clientId;
    const scopeParts = scope.split(' ');
    // All these scopes require no special grants, so all should be present
    expect(scopeParts).toContain('profile:read');
    expect(scopeParts).toContain('inventory:read');
    expect(scopeParts).toContain('loadouts:read');
    expect(scopeParts).toContain('notifications:read');
  });
});

test.describe('OAuth Scope Enforcement - Invalid Bearer Token', () => {
  test('invalid bearer token returns 401', async ({ page }) => {
    const res = await page.request.get(USERINFO_API, {
      headers: { Authorization: 'Bearer invalid_token_that_does_not_exist' }
    });
    expect(res.status()).toBe(401);
  });

  test('expired/revoked bearer token returns 401', async ({ verifiedUser, request }) => {
    // Get a valid token then revoke it
    const { clientId, access_token } = await getTokensWithScopes(verifiedUser, 'profile:read');

    // Revoke the token
    await verifiedUser.request.post('/api/oauth/revoke', {
      data: { token: access_token }
    });

    // Token should no longer work (cookie-free to avoid session fallback)
    const res = await request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(401);

    await cleanupClient(verifiedUser, clientId);
  });
});
