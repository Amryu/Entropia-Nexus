// @ts-nocheck
/**
 * GET /api/oauth/authorizations — List apps the current user has authorized
 */
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { getUserAuthorizations } from '$lib/server/oauth.js';

export async function GET({ locals }) {
  const user = requireVerifiedAPI(locals);

  const authorizations = await getUserAuthorizations(BigInt(user.id));
  return getResponse(authorizations, 200);
}
