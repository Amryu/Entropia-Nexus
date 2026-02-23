// @ts-nocheck
/**
 * POST /api/oauth/clients/[id]/rotate-secret — Generate a new client secret
 */
import { getResponse } from '$lib/util.js';
import { requireVerified } from '$lib/server/auth.js';
import { rotateClientSecret } from '$lib/server/oauth.js';

export async function POST({ params, locals }) {
  const user = requireVerified(locals);

  const newSecret = await rotateClientSecret(params.id, BigInt(user.id));
  if (!newSecret) {
    return getResponse({ error: 'Client not found' }, 404);
  }

  return getResponse({ clientSecret: newSecret }, 200);
}
