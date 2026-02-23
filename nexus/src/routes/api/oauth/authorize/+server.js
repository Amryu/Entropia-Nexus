// @ts-nocheck
/**
 * GET /api/oauth/authorize — OAuth 2.0 Authorization endpoint.
 * Validates parameters and redirects to the consent page.
 */
import { getClient, getScopeDefinitions } from '$lib/server/oauth.js';

export async function GET({ url, locals }) {
  const responseType = url.searchParams.get('response_type');
  const clientId = url.searchParams.get('client_id');
  const redirectUri = url.searchParams.get('redirect_uri');
  const scope = url.searchParams.get('scope');
  const state = url.searchParams.get('state');
  const codeChallenge = url.searchParams.get('code_challenge');
  const codeChallengeMethod = url.searchParams.get('code_challenge_method');

  // Validate required parameters
  if (responseType !== 'code') {
    return errorResponse('unsupported_response_type', 'Only response_type=code is supported.', redirectUri, state);
  }
  if (!clientId) {
    return new Response(JSON.stringify({ error: 'invalid_request', error_description: 'client_id is required.' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }
  if (!redirectUri) {
    return new Response(JSON.stringify({ error: 'invalid_request', error_description: 'redirect_uri is required.' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }
  if (!scope) {
    return errorResponse('invalid_request', 'scope is required.', redirectUri, state);
  }
  if (!state) {
    return errorResponse('invalid_request', 'state is required for CSRF protection.', redirectUri, state);
  }
  if (!codeChallenge || codeChallengeMethod !== 'S256') {
    return errorResponse('invalid_request', 'PKCE is required. Provide code_challenge with code_challenge_method=S256.', redirectUri, state);
  }

  // Validate client
  const client = await getClient(clientId);
  if (!client) {
    return new Response(JSON.stringify({ error: 'invalid_client', error_description: 'Unknown client_id.' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  // Validate redirect URI (exact match)
  if (!client.redirect_uris.includes(redirectUri)) {
    return new Response(JSON.stringify({ error: 'invalid_request', error_description: 'redirect_uri does not match any registered URIs.' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  }

  // Validate scopes
  const requestedScopes = scope.split(' ').filter(Boolean);
  const definitions = await getScopeDefinitions();
  const invalidScopes = requestedScopes.filter(s => !definitions.has(s));
  if (invalidScopes.length > 0) {
    return errorResponse('invalid_scope', `Unknown scopes: ${invalidScopes.join(', ')}`, redirectUri, state);
  }

  // If user not logged in, redirect to login with return URL
  if (!locals.session?.user) {
    const returnUrl = `/oauth/authorize?${url.searchParams.toString()}`;
    return new Response(null, {
      status: 302,
      headers: { Location: `/discord/login?redirect=${encodeURIComponent(returnUrl)}` }
    });
  }

  // Redirect to consent page (preserves all query params)
  return new Response(null, {
    status: 302,
    headers: { Location: `/oauth/authorize?${url.searchParams.toString()}` }
  });
}

/**
 * Build an OAuth error redirect response.
 */
function errorResponse(error, description, redirectUri, state) {
  if (redirectUri) {
    const url = new URL(redirectUri);
    url.searchParams.set('error', error);
    url.searchParams.set('error_description', description);
    if (state) url.searchParams.set('state', state);
    return new Response(null, { status: 302, headers: { Location: url.toString() } });
  }
  return new Response(JSON.stringify({ error, error_description: description }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' }
  });
}
