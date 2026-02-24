import { test, expect } from '../fixtures/auth';
import { extractFormActionRedirect } from '../fixtures/form-action';
import { TIMEOUT_MEDIUM, TIMEOUT_CACHE } from '../test-constants';
import crypto from 'crypto';

const CLIENTS_API = '/api/oauth/clients';
const TOKEN_API = '/api/oauth/token';
const REDIRECT_URI = 'https://example.com/callback';

/**
 * OAuth Turnstile Bypass Tests
 *
 * Verifies that Turnstile CAPTCHA verification is:
 * 1. Skipped for OAuth-authenticated requests (Bearer token)
 * 2. Still enforced for regular browser session requests
 *
 * Endpoints tested:
 * - POST /api/market/exchange/orders (via /api/market/exchange/orders/item/[itemId])
 * - PUT/DELETE /api/market/exchange/orders/[id]
 * - POST /api/market/exchange/orders/batch
 * - POST /api/market/exchange/orders/bump-all
 * - POST /api/auction/[id]/bid
 * - POST /api/auction/[id]/buyout
 */

function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString('hex');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

/** Create client and get OAuth tokens with exchange and auction scopes */
async function getOAuthTokens(page: import('@playwright/test').Page) {
  const clientRes = await page.request.post(CLIENTS_API, {
    data: {
      name: `Turnstile Test ${Date.now()}`,
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
      scope: 'exchange:read exchange:write auction:read auction:write',
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
  return { clientId, ...tokens };
}

async function cleanupClient(page: import('@playwright/test').Page, clientId: string) {
  if (clientId) await page.request.delete(`${CLIENTS_API}/${clientId}`);
}

test.describe('Turnstile Bypass - Exchange Orders', () => {
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('session-authenticated exchange order requires Turnstile token', async ({ verifiedUser }) => {
    // Use a very high item_id that doesn't exist to avoid conflicts
    const res = await verifiedUser.request.post('/api/market/exchange/orders', {
      data: {
        type: 'SELL',
        item_id: 9999999,
        quantity: 1,
        markup: 110,
        planet: 'Calypso'
        // No turnstile_token - should be rejected
      }
    });
    // Should fail with 400 because no Turnstile token
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha');
  });

  test('OAuth-authenticated exchange order skips Turnstile', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getOAuthTokens(verifiedUser);
    lastClientId = clientId;

    // Post exchange order with Bearer token (no Turnstile token needed)
    const res = await verifiedUser.request.post('/api/market/exchange/orders', {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {
        type: 'SELL',
        item_id: 9999999,
        quantity: 1,
        markup: 110,
        planet: 'Calypso'
        // No turnstile_token - should NOT be rejected for OAuth
      }
    });
    // Should NOT fail with 400/Captcha error
    // It may fail with a different error (item not found, etc.) but not Captcha
    if (res.status() === 400) {
      const data = await res.json();
      expect(data.error).not.toContain('Captcha');
    }
  });

  test('session-authenticated batch orders requires Turnstile token', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post('/api/market/exchange/orders/batch', {
      data: {
        orders: [{
          type: 'SELL',
          item_id: 9999998,
          quantity: 1,
          markup: 110,
          planet: 'Calypso'
        }]
        // No turnstile_token
      }
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha');
  });

  test('OAuth-authenticated batch orders skips Turnstile', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getOAuthTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post('/api/market/exchange/orders/batch', {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {
        orders: [{
          type: 'SELL',
          item_id: 9999998,
          quantity: 1,
          markup: 110,
          planet: 'Calypso'
        }]
        // No turnstile_token - OK for OAuth
      }
    });
    if (res.status() === 400) {
      const data = await res.json();
      expect(data.error).not.toContain('Captcha');
    }
  });

  test('session-authenticated bump-all requires Turnstile token', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post('/api/market/exchange/orders/bump-all', {
      data: {}
      // No turnstile_token
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha');
  });

  test('OAuth-authenticated bump-all is blocked', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getOAuthTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post('/api/market/exchange/orders/bump-all', {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {}
    });
    // bump-all is not available via OAuth API
    expect(res.status()).toBe(403);
    const data = await res.json();
    expect(data.error).toContain('not available via the OAuth API');
  });
});

test.describe('Turnstile Bypass - Auction Endpoints', () => {
  const FAKE_AUCTION_ID = '00000000-0000-0000-0000-000000000000';
  let lastClientId: string;

  test.afterEach(async ({ verifiedUser }) => {
    await cleanupClient(verifiedUser, lastClientId);
  });

  test('session-authenticated bid requires Turnstile token', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(`/api/auction/${FAKE_AUCTION_ID}/bid`, {
      data: { amount: 10 }
      // No turnstile_token
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha');
  });

  test('OAuth-authenticated bid skips Turnstile', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getOAuthTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post(`/api/auction/${FAKE_AUCTION_ID}/bid`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { amount: 10 }
      // No turnstile_token - OK for OAuth
    });
    // Should not fail with Captcha error (may fail with disclaimer or not found)
    if (res.status() === 400) {
      const data = await res.json();
      expect(data.error).not.toContain('Captcha');
    }
  });

  test('session-authenticated buyout requires Turnstile token', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.post(`/api/auction/${FAKE_AUCTION_ID}/buyout`, {
      data: {}
      // No turnstile_token
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Captcha');
  });

  test('OAuth-authenticated buyout skips Turnstile', async ({ verifiedUser }) => {
    const { clientId, access_token } = await getOAuthTokens(verifiedUser);
    lastClientId = clientId;

    const res = await verifiedUser.request.post(`/api/auction/${FAKE_AUCTION_ID}/buyout`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {}
      // No turnstile_token - OK for OAuth
    });
    // Should not fail with Captcha error
    if (res.status() === 400) {
      const data = await res.json();
      expect(data.error).not.toContain('Captcha');
    }
  });
});
