// @ts-nocheck
import { redirect, error } from '@sveltejs/kit';
import { requireLogin } from '$lib/server/auth.js';
import { getClient, getScopeDefinitions, validateScopes, createAuthorizationCode } from '$lib/server/oauth.js';
import { resolveUserGrants } from '$lib/server/grants.js';

export async function load({ url, locals }) {
  const user = requireLogin(locals, `/oauth/authorize?${url.searchParams.toString()}`);

  const clientId = url.searchParams.get('client_id');
  const redirectUri = url.searchParams.get('redirect_uri');
  const scope = url.searchParams.get('scope');
  const state = url.searchParams.get('state');
  const codeChallenge = url.searchParams.get('code_challenge');
  const codeChallengeMethod = url.searchParams.get('code_challenge_method');
  const responseType = url.searchParams.get('response_type');

  // Validate all required params
  if (responseType !== 'code' || !clientId || !redirectUri || !scope || !state || !codeChallenge || codeChallengeMethod !== 'S256') {
    throw error(400, 'Invalid OAuth authorization request. Missing or invalid parameters.');
  }

  if (!user.verified) {
    throw error(403, 'You must be a verified user to authorize applications.');
  }

  const client = await getClient(clientId);
  if (!client) {
    throw error(400, 'Unknown application.');
  }

  if (!client.redirect_uris.includes(redirectUri)) {
    throw error(400, 'Invalid redirect URI.');
  }

  const requestedScopes = scope.split(' ').filter(Boolean);
  const definitions = await getScopeDefinitions();

  // Resolve user grants to determine which scopes are available
  const userGrants = await resolveUserGrants(BigInt(user.id));
  const effectiveScopes = await validateScopes(requestedScopes, userGrants);

  // Build scope display info
  const scopeInfo = requestedScopes.map(s => {
    const def = definitions.get(s);
    return {
      key: s,
      description: def?.description || s,
      available: effectiveScopes.includes(s),
      isWrite: s.endsWith(':write')
    };
  });

  return {
    client: {
      id: client.id,
      name: client.name,
      description: client.description,
      website_url: client.website_url
    },
    scopeInfo,
    requestedScopes,
    effectiveScopes,
    redirectUri,
    state,
    codeChallenge,
    codeChallengeMethod
  };
}

export const actions = {
  authorize: async ({ request, locals, url }) => {
    const user = requireLogin(locals, url.pathname);
    if (!user.verified) throw error(403, 'Verified account required.');

    const formData = await request.formData();
    const clientId = formData.get('client_id');
    const redirectUri = formData.get('redirect_uri');
    const scope = formData.get('scope');
    const state = formData.get('state');
    const codeChallenge = formData.get('code_challenge');

    if (!clientId || !redirectUri || !scope || !state || !codeChallenge) {
      throw error(400, 'Missing required parameters.');
    }

    const client = await getClient(clientId);
    if (!client || !client.redirect_uris.includes(redirectUri)) {
      throw error(400, 'Invalid client or redirect URI.');
    }

    const requestedScopes = scope.split(' ').filter(Boolean);
    const userGrants = await resolveUserGrants(BigInt(user.id));
    const effectiveScopes = await validateScopes(requestedScopes, userGrants);

    if (effectiveScopes.length === 0) {
      throw error(403, 'No valid scopes could be granted.');
    }

    const rawCode = await createAuthorizationCode(
      clientId,
      BigInt(user.id),
      redirectUri,
      effectiveScopes,
      codeChallenge
    );

    const redirectUrl = new URL(redirectUri);
    redirectUrl.searchParams.set('code', rawCode);
    redirectUrl.searchParams.set('state', state);

    throw redirect(302, redirectUrl.toString());
  },

  deny: async ({ request }) => {
    const formData = await request.formData();
    const redirectUri = formData.get('redirect_uri');
    const state = formData.get('state');

    if (!redirectUri) throw error(400, 'Missing redirect_uri.');

    const redirectUrl = new URL(redirectUri);
    redirectUrl.searchParams.set('error', 'access_denied');
    redirectUrl.searchParams.set('error_description', 'The user denied the authorization request.');
    if (state) redirectUrl.searchParams.set('state', state);

    throw redirect(302, redirectUrl.toString());
  }
};
