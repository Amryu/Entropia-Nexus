// @ts-nocheck
/**
 * POST /api/oauth/clients/[id]/rotate-secret — Generate a new client secret
 */
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { rotateClientSecret } from '$lib/server/oauth.js';

export async function POST({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  let newSecret;
  try {
    newSecret = await rotateClientSecret(params.id, BigInt(user.id));
  } catch (err) {
    if (err.message?.includes('public client')) {
      return getResponse({ error: 'Cannot rotate secret for a public client.' }, 400);
    }
    throw err;
  }

  if (!newSecret) {
    return getResponse({ error: 'Client not found' }, 404);
  }

  return getResponse({ clientSecret: newSecret }, 200);
}
