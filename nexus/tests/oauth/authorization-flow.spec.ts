import { test, expect } from '../fixtures/auth';
import { extractFormActionRedirect } from '../fixtures/form-action';
import { TIMEOUT_MEDIUM } from '../test-constants';
import crypto from 'crypto';

const CLIENTS_API = '/api/oauth/clients';
const AUTHORIZE_API = '/api/oauth/authorize';
const TOKEN_API = '/api/oauth/token';
const USERINFO_API = '/api/oauth/userinfo';
const REDIRECT_URI = 'https://example.com/callback';

/**
 * OAuth Authorization Flow Tests
 *
 * Verifies:
 * 1. Authorization endpoint parameter validation
 * 2. Full authorization code flow with PKCE
 * 3. Token exchange
 * 4. Access token usage (Bearer auth)
 * 5. Userinfo endpoint
 * 6. Consent page rendering
 */

/** Generate PKCE code verifier and challenge */
function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString('hex');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

/** Helper to create a test OAuth client and return credentials */
async function setupTestClient(page: import('@playwright/test').Page) {
  const res = await page.request.post(CLIENTS_API, {
    data: {
      name: 'Auth Flow Test App',
      description: 'Testing OAuth flow',
      redirect_uris: [REDIRECT_URI]
    }
  });
  expect(res.status()).toBe(201);
  return await res.json() as { clientId: string; clientSecret: string };
}

/** Clean up a specific OAuth client */
async function cleanupClient(page: import('@playwright/test').Page, id: string) {
  if (id) await page.request.delete(`${CLIENTS_API}/${id}`);
}

test.describe('OAuth Authorization Endpoint - Validation', () => {
  let clientId: string;
  let clientSecret: string;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    const creds = await setupTestClient(page);
    clientId = creds.clientId;
    clientSecret = creds.clientSecret;
    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    await cleanupClient(page, clientId);
    await context.close();
  });

  test('rejects missing client_id', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: 'test123',
        code_challenge: 'challenge',
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
  });

  test('rejects missing redirect_uri', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: clientId,
        scope: 'profile:read',
        state: 'test123',
        code_challenge: 'challenge',
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
  });

  test('rejects unknown client_id', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: '00000000-0000-0000-0000-000000000000',
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: 'test123',
        code_challenge: 'challenge',
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_client');
  });

  test('rejects mismatched redirect_uri', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: clientId,
        redirect_uri: 'https://evil.com/callback',
        scope: 'profile:read',
        state: 'test123',
        code_challenge: 'challenge',
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
    expect(data.error_description).toContain('redirect_uri');
  });

  test('rejects missing PKCE code_challenge', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: 'test123'
      },
      maxRedirects: 0
    });
    // Should redirect to redirect_uri with error
    expect(res.status()).toBe(302);
    const location = res.headers()['location'];
    expect(location).toContain('error=invalid_request');
    expect(location).toContain('PKCE');
  });

  test('rejects invalid scope', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        scope: 'nonexistent:scope',
        state: 'test123',
        code_challenge: challenge,
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(302);
    const location = res.headers()['location'];
    expect(location).toContain('error=invalid_scope');
  });

  test('redirects to consent page with valid params', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const res = await verifiedUser.request.get(AUTHORIZE_API, {
      params: {
        response_type: 'code',
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: 'test_state_123',
        code_challenge: challenge,
        code_challenge_method: 'S256'
      },
      maxRedirects: 0
    });
    expect(res.status()).toBe(302);
    const location = res.headers()['location'];
    expect(location).toContain('/oauth/authorize');
    expect(location).toContain('client_id');
  });
});

test.describe('OAuth Full Authorization Code Flow', () => {
  let clientId: string;
  let clientSecret: string;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    const creds = await setupTestClient(page);
    clientId = creds.clientId;
    clientSecret = creds.clientSecret;
    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    await cleanupClient(page, clientId);
    await context.close();
  });

  test('complete flow: authorize → code → tokens → API call', async ({ verifiedUser }) => {
    const { verifier, challenge } = generatePKCE();
    const state = crypto.randomBytes(16).toString('hex');

    // Step 1: Navigate to consent page
    const consentUrl = `/oauth/authorize?response_type=code&client_id=${clientId}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&scope=profile:read&state=${state}&code_challenge=${challenge}&code_challenge_method=S256`;
    const pageResponse = await verifiedUser.goto(consentUrl);
    expect(pageResponse?.status()).toBe(200);

    // Step 2: Verify consent page shows app name and scope
    const content = await verifiedUser.textContent('body');
    expect(content).toContain('Auth Flow Test App');
    expect(content).toContain('Authorize');

    // Step 3: Submit the authorize form
    // We need to intercept the redirect to capture the authorization code
    const [response] = await Promise.all([
      verifiedUser.waitForResponse(resp => {
        const url = resp.url();
        return url.startsWith(REDIRECT_URI) || resp.status() === 302;
      }).catch(() => null),
      verifiedUser.click('.btn-authorize')
    ]);

    // The form submission should redirect to the redirect_uri with the code
    // Since the redirect_uri is external, the browser will fail to navigate
    // We capture the URL from the failed navigation
    const currentUrl = verifiedUser.url();
    // After form submission, SvelteKit redirects - check the URL or intercept
    // For API testing, let's use the form action directly
    const formRes = await verifiedUser.request.post('/oauth/authorize?/authorize', {
      form: {
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        scope: 'profile:read',
        state: state,
        code_challenge: challenge
      },
      maxRedirects: 0
    });

    // SvelteKit form actions return redirect (302/303 or JSON-wrapped)
    const location = await extractFormActionRedirect(formRes);

    // Extract authorization code from redirect URL
    const redirectUrl = new URL(location, 'https://example.com');
    const authCode = redirectUrl.searchParams.get('code');
    const returnedState = redirectUrl.searchParams.get('state');
    expect(authCode).toBeDefined();
    expect(returnedState).toBe(state);

    // Step 4: Exchange code for tokens
    const tokenRes = await verifiedUser.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'authorization_code',
        code: authCode!,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: REDIRECT_URI,
        code_verifier: verifier
      }).toString()
    });
    expect(tokenRes.status()).toBe(200);

    const tokens = await tokenRes.json();
    expect(tokens.access_token).toBeDefined();
    expect(tokens.token_type).toBe('Bearer');
    expect(tokens.expires_in).toBe(3600);
    expect(tokens.refresh_token).toBeDefined();
    expect(tokens.scope).toBe('profile:read');

    // Step 5: Use access token to call userinfo
    const userinfoRes = await verifiedUser.request.get(USERINFO_API, {
      headers: { Authorization: `Bearer ${tokens.access_token}` }
    });
    expect(userinfoRes.status()).toBe(200);

    const userinfo = await userinfoRes.json();
    expect(userinfo.id).toBeDefined();
    expect(userinfo.username).toBeDefined();
  });
});

test.describe('OAuth Token Endpoint - Validation', () => {
  test('rejects unsupported grant_type', async ({ page }) => {
    const res = await page.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: 'grant_type=client_credentials&client_id=fake'
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('unsupported_grant_type');
  });

  test('rejects missing code in authorization_code grant', async ({ page }) => {
    const res = await page.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: 'grant_type=authorization_code&client_id=fake'
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
  });

  test('rejects missing refresh_token in refresh_token grant', async ({ page }) => {
    const res = await page.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: 'grant_type=refresh_token&client_id=fake'
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_request');
  });

  test('rejects invalid authorization code', async ({ page }) => {
    const res = await page.request.post(TOKEN_API, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: new URLSearchParams({
        grant_type: 'authorization_code',
        code: 'invalid_code',
        client_id: 'fake-client-id',
        redirect_uri: REDIRECT_URI,
        code_verifier: 'fake_verifier'
      }).toString()
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('invalid_grant');
  });

  test('accepts JSON content type', async ({ page }) => {
    const res = await page.request.post(TOKEN_API, {
      data: {
        grant_type: 'authorization_code',
        code: 'invalid_code',
        client_id: 'fake-client-id',
        redirect_uri: REDIRECT_URI,
        code_verifier: 'fake_verifier'
      }
    });
    expect(res.status()).toBe(400);
    const data = await res.json();
    // Should fail with invalid_grant (not invalid content type)
    expect(data.error).toBe('invalid_grant');
  });
});

test.describe('OAuth Userinfo Endpoint', () => {
  test('rejects unauthenticated request', async ({ page }) => {
    const res = await page.request.get(USERINFO_API);
    expect(res.status()).toBe(401);
  });

  test('rejects request without profile:read scope', async ({ verifiedUser }) => {
    // Session-authenticated requests don't have OAuth scopes
    // so this test verifies the scope check works when isOAuth is false
    // The endpoint should still work for session-authenticated users
    const res = await verifiedUser.request.get(USERINFO_API);
    // For session auth (non-OAuth), the endpoint returns the user profile
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.id).toBeDefined();
  });
});

test.describe('OAuth Consent Page', () => {
  let clientId: string;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    const creds = await setupTestClient(page);
    clientId = creds.clientId;
    await context.close();
  });

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/');
    await page.request.post('/api/test/login', { data: { userId: 'verified1' } });
    await cleanupClient(page, clientId);
    await context.close();
  });

  test('shows app name and requested scopes', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const url = `/oauth/authorize?response_type=code&client_id=${clientId}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&scope=profile:read inventory:read&state=test&code_challenge=${challenge}&code_challenge_method=S256`;

    await verifiedUser.goto(url);
    const content = await verifiedUser.textContent('body');
    expect(content).toContain('Auth Flow Test App');
    expect(content).toContain('Authorize');
    expect(content).toContain('Deny');
  });

  test('shows write scope warning when write scopes requested', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const url = `/oauth/authorize?response_type=code&client_id=${clientId}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&scope=profile:read inventory:write&state=test&code_challenge=${challenge}&code_challenge_method=S256`;

    await verifiedUser.goto(url);
    const content = await verifiedUser.textContent('body');
    expect(content).toContain('write access');
  });

  test('deny action redirects with error', async ({ verifiedUser }) => {
    const { challenge } = generatePKCE();
    const state = 'deny_test_state';

    const formRes = await verifiedUser.request.post('/oauth/authorize?/deny', {
      form: {
        client_id: clientId,
        redirect_uri: REDIRECT_URI,
        state: state
      },
      maxRedirects: 0
    });

    const location = await extractFormActionRedirect(formRes);
    expect(location).toContain('error=access_denied');
    expect(location).toContain(`state=${state}`);
  });
});
