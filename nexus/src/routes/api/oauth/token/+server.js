// @ts-nocheck
/**
 * POST /api/oauth/token — OAuth 2.0 Token endpoint.
 * Supports grant_type=authorization_code and grant_type=refresh_token.
 */
import { exchangeAuthorizationCode, refreshAccessToken } from '$lib/server/oauth.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

export async function POST({ request }) {
  // OAuth spec requires application/x-www-form-urlencoded
  let params;
  const contentType = request.headers.get('content-type') || '';
  if (contentType.includes('application/x-www-form-urlencoded')) {
    const text = await request.text();
    params = new URLSearchParams(text);
  } else if (contentType.includes('application/json')) {
    // Also support JSON for developer convenience
    const json = await request.json();
    params = new URLSearchParams(json);
  } else {
    return tokenError('invalid_request', 'Content-Type must be application/x-www-form-urlencoded or application/json.');
  }

  // Rate limit per client_id: 20 requests per minute
  const clientId = params.get('client_id') || 'unknown';
  const rateCheck = checkRateLimit(`oauth:token:${clientId}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return tokenError('rate_limited', 'Too many token requests. Please try again later.');
  }

  const grantType = params.get('grant_type');

  if (grantType === 'authorization_code') {
    return handleAuthorizationCode(params);
  } else if (grantType === 'refresh_token') {
    return handleRefreshToken(params);
  } else {
    return tokenError('unsupported_grant_type', 'Supported: authorization_code, refresh_token.');
  }
}

async function handleAuthorizationCode(params) {
  const code = params.get('code');
  const clientId = params.get('client_id');
  const clientSecret = params.get('client_secret') || null;
  const redirectUri = params.get('redirect_uri');
  const codeVerifier = params.get('code_verifier');

  if (!code || !clientId || !redirectUri || !codeVerifier) {
    return tokenError('invalid_request', 'code, client_id, redirect_uri, and code_verifier are required.');
  }

  const result = await exchangeAuthorizationCode(code, clientId, clientSecret, redirectUri, codeVerifier);
  if (!result) {
    return tokenError('invalid_grant', 'Invalid or expired authorization code, or PKCE verification failed.');
  }

  return tokenResponse(result);
}

async function handleRefreshToken(params) {
  const refreshToken = params.get('refresh_token');
  const clientId = params.get('client_id');
  const clientSecret = params.get('client_secret') || null;

  if (!refreshToken || !clientId) {
    return tokenError('invalid_request', 'refresh_token and client_id are required.');
  }

  const result = await refreshAccessToken(refreshToken, clientId, clientSecret);
  if (!result) {
    return tokenError('invalid_grant', 'Invalid, expired, or already used refresh token.');
  }

  return tokenResponse(result);
}

function tokenResponse(result) {
  return new Response(JSON.stringify({
    access_token: result.accessToken,
    token_type: 'Bearer',
    expires_in: result.expiresIn,
    refresh_token: result.refreshToken,
    scope: result.scope
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
      'Pragma': 'no-cache'
    }
  });
}

function tokenError(error, description) {
  return new Response(JSON.stringify({
    error,
    error_description: description
  }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' }
  });
}
