// @ts-nocheck
/**
 * POST /api/oauth/revoke — OAuth 2.0 Token Revocation (RFC 7009).
 * Always returns 200 regardless of whether the token existed.
 */
import { revokeToken } from '$lib/server/oauth.js';

export async function POST({ request }) {
  let params;
  const contentType = request.headers.get('content-type') || '';
  if (contentType.includes('application/x-www-form-urlencoded')) {
    const text = await request.text();
    params = new URLSearchParams(text);
  } else if (contentType.includes('application/json')) {
    const json = await request.json();
    params = new URLSearchParams(json);
  } else {
    return new Response(JSON.stringify({ error: 'invalid_request' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const token = params.get('token');
  if (!token) {
    return new Response(JSON.stringify({ error: 'invalid_request', error_description: 'token is required.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    await revokeToken(token);
  } catch (err) {
    // Per RFC 7009, always return 200 even on errors
    console.error('[oauth] Error during token revocation:', err);
  }

  return new Response(null, { status: 200 });
}
