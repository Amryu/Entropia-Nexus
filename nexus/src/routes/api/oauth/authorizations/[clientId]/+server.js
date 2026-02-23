// @ts-nocheck
/**
 * DELETE /api/oauth/authorizations/[clientId] — Revoke authorization for an app
 */
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { revokeAllClientUserTokens } from '$lib/server/oauth.js';

export async function DELETE({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  await revokeAllClientUserTokens(params.clientId, BigInt(user.id));
  return getResponse({ revoked: true }, 200);
}
