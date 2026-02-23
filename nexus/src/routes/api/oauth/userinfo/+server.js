// @ts-nocheck
/**
 * GET /api/oauth/userinfo — Returns user profile data.
 * Requires profile:read scope via OAuth Bearer token.
 */
import { getResponse } from '$lib/util.js';

export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  // Check for profile:read scope if OAuth request
  if (locals.isOAuth && !locals.oauthScopes?.includes('profile:read')) {
    return getResponse({ error: 'Insufficient scope. Requires profile:read.' }, 403);
  }

  return getResponse({
    id: String(user.id),
    username: user.username,
    global_name: user.global_name,
    discriminator: user.discriminator,
    avatar: user.avatar,
    eu_name: user.eu_name,
    verified: user.verified
  }, 200);
}
