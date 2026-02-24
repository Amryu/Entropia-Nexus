import { test, expect } from '../fixtures/auth';
import { extractFormActionRedirect } from '../fixtures/form-action';
import { TIMEOUT_MEDIUM } from '../test-constants';
import crypto from 'crypto';

const CLIENTS_API = '/api/oauth/clients';
const TOKEN_API = '/api/oauth/token';
const REVOKE_API = '/api/oauth/revoke';
const USERINFO_API = '/api/oauth/userinfo';
const AUTHORIZATIONS_API = '/api/oauth/authorizations';
const REDIRECT_URI = 'https://example.com/callback';

/**
 * OAuth Token Lifecycle Tests
 *
 * Verifies:
 * 1. Token refresh with rotation
 * 2. Refresh token single-use enforcement
 * 3. Token revocation (access + refresh)
 * 4. Authorization management (list + revoke)
 * 5. Revocation endpoint RFC 7009 compliance
 */

function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString('hex');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

/** Create a client and perform full auth flow, returning tokens */
async function getTokens(page: import('@playwright/test').Page) {
  // Create client
  const clientRes = await page.request.post(CLIENTS_API, {
    data: {
      name: 'Token Lifecycle Test',
      redirect_uris: [REDIRECT_URI]
    }
  });
  expect(clientRes.status()).toBe(201);
  const { clientId, clientSecret } = await clientRes.json();

  // Get authorization code via form action
  const { verifier, challenge } = generatePKCE();
  const state = crypto.randomBytes(16).toString('hex');

  const authRes = await page.request.post('/oauth/authorize?/authorize', {
    form: {
      client_id: clientId,
      redirect_uri: REDIRECT_URI,
      scope: 'profile:read inventory:read',
      state,
      code_challenge: challenge
    },
    maxRedirects: 0
  });
  const location = await extractFormActionRedirect(authRes);
  const redirectUrl = new URL(location, 'https://example.com');
  const authCode = redirectUrl.searchParams.get('code')!;

  // Exchange code for tokens
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

test.describe('OAuth Token Refresh', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('can refresh access token with valid refresh token', async ({ verifiedUser }) => {
    const { clientId, clientSecret, access_token, refresh_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    // Refresh
    const refreshRes = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refresh_token,
        client_id: clientId,
        client_secret: clientSecret
      }).toString()
    });
    expect(refreshRes.status()).toBe(200);

    const newTokens = await refreshRes.json();
    expect(newTokens.access_token).toBeDefined();
    expect(newTokens.refresh_token).toBeDefined();
    expect(newTokens.token_type).toBe('Bearer');
    expect(newTokens.expires_in).toBe(3600);

    // New tokens should be different
    expect(newTokens.access_token).not.toBe(access_token);
    expect(newTokens.refresh_token).not.toBe(refresh_token);

    // New access token should work
    const userinfoRes = await verifiedUser.request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${newTokens.access_token}` }
    });
    expect(userinfoRes.status()).toBe(200);
  });

  test('old refresh token becomes invalid after use (single-use)', async ({ verifiedUser }) => {
    const { clientId, clientSecret, refresh_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    // First refresh - should succeed
    const firstRefresh = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refresh_token,
        client_id: clientId,
        client_secret: clientSecret
      }).toString()
    });
    expect(firstRefresh.status()).toBe(200);

    // Second use of the same refresh token - should fail (reuse detection)
    const secondRefresh = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refresh_token,
        client_id: clientId,
        client_secret: clientSecret
      }).toString()
    });
    expect(secondRefresh.status()).toBe(400);
    const data = await secondRefresh.json();
    expect(data.error).toBe('invalid_grant');
  });

  test('rejects refresh with wrong client_id', async ({ verifiedUser }) => {
    const { clientId, clientSecret, refresh_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refresh_token,
        client_id: '00000000-0000-0000-0000-000000000000',
        client_secret: clientSecret
      }).toString()
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_grant');
  });

  test('rejects refresh with invalid refresh token', async ({ verifiedUser }) => {
    const { clientId, clientSecret } = await getTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: 'completely_invalid_token',
        client_id: clientId,
        client_secret: clientSecret
      }).toString()
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_grant');
  });
});

test.describe('OAuth Token Revocation', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('can revoke access token', async ({ verifiedUser, request }) => {
    const { clientId, access_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    // Verify token works first (cookie-free context to test Bearer only)
    let res = await request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(200);

    // Revoke it
    const revokeRes = await verifiedUser.request.post(REVOKE_API, {
      data: { token: access_token }
    });
    expect(revokeRes.status()).toBe(200);

    // Token should no longer work (cookie-free to avoid session fallback)
    res = await request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(401);
  });

  test('can revoke refresh token', async ({ verifiedUser }) => {
    const { clientId, clientSecret, refresh_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    // Revoke the refresh token
    const revokeRes = await verifiedUser.request.post(REVOKE_API, {
      data: { token: refresh_token }
    });
    expect(revokeRes.status()).toBe(200);

    // Refresh should fail
    const refreshRes = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refresh_token,
        client_id: clientId,
        client_secret: clientSecret
      }).toString()
    });
    expect(refreshRes.status()).toBe(400);
  });

  test('revoke always returns 200 even for invalid tokens (RFC 7009)', async ({ page }) => {
    const res = await page.request.post(REVOKE_API, {
      data: { token: 'nonexistent_token_value' }
    });
    expect(res.status()).toBe(200);
  });

  test('revoke returns 400 when no token provided', async ({ page }) => {
    const res = await page.request.post(REVOKE_API, {
      data: {}
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
  });
});

test.describe('OAuth Authorization Management', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('can list authorized apps', async ({ verifiedUser }) => {
    // Create tokens (which creates an authorization)
    const { clientId } = await getTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.get(AUTHORIZATIONS_API);
    expect(res.status()).toBe(200);

    const auths = await res.json();
    expect(Array.isArray(auths)).toBe(true);
    expect(auths.length).toBeGreaterThanOrEqual(1);
    expect(auths[0].client_id).toBeDefined();
    expect(auths[0].name).toBeDefined();
    expect(auths[0].scopes).toBeDefined();
  });

  test('listing authorizations requires authentication', async ({ page }) => {
    const res = await page.request.get(AUTHORIZATIONS_API);
    expect(res.status()).toBe(401);
  });

  test('can revoke all tokens for an app', async ({ verifiedUser, request }) => {
    const { clientId, access_token } = await getTokens(verifiedUser);
    lastClientId = clientId;

    // Verify token works (cookie-free context to test Bearer only)
    let res = await request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(200);

    // Revoke all tokens for this client
    const revokeRes = await verifiedUser.request.delete(`${AUTHORIZATIONS_API}/${clientId}`);
    expect(revokeRes.status()).toBe(200);
    const data = await revokeRes.json();
    expect(data.revoked).toBe(true);

    // Token should no longer work (cookie-free to avoid session fallback)
    res = await request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    expect(res.status()).toBe(401);
  });
});

test.describe('OAuth Authorization Code Single-Use', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('authorization code cannot be used twice', async ({ verifiedUser }) => {
    // Create client
    const clientRes = await verifiedUser.request.post(CLIENTS_API, {
      data: { name: 'Code Reuse Test', redirect_uris: [REDIRECT_URI] }
    });
    const { clientId, clientSecret } = await clientRes.json();
    lastClientId = clientId;

    // Get authorization code
    const { verifier, challenge } = generatePKCE();
    const authRes = await verifiedUser.request.post('/oauth/authorize?/authorize', {
      form: {
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: 'test',
        code_challenge: challenge
      },
      maxRedirects: 0
    });
    const location = await extractFormActionRedirect(authRes);
    const redirectUrl = new URL(location, 'https://example.com');
    const authCode = redirectUrl.searchParams.get('code')!;

    // First exchange - should succeed
    const firstExchange = await verifiedUser.request.post(TOKEN_API, {
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
    expect(firstExchange.status()).toBe(200);

    // Second exchange with same code - should fail
    const secondExchange = await verifiedUser.request.post(TOKEN_API, {
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
    expect(secondExchange.status()).toBe(400);
    const data = await secondExchange.json();
    expect(data.error).toBe('invalid_grant');
  });
});
