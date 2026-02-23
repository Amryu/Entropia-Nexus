// @ts-nocheck
/**
 * GET  /api/auction/disclaimer — Check disclaimer status (verified)
 * POST /api/auction/disclaimer — Accept a disclaimer (verified)
 */
import { getResponse } from '$lib/util.js';
import { isOAuthRequest } from '$lib/server/auth.js';
import { getDisclaimerStatus, acceptDisclaimer } from '$lib/server/auction.js';

const VALID_ROLES = ['bidder', 'seller'];

export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const status = await getDisclaimerStatus(user.id);
    return getResponse(status, 200);
  } catch (err) {
    console.error('Error checking disclaimer status:', err);
    return getResponse({ error: 'Failed to check disclaimer status' }, 500);
  }
}

export async function POST({ request, locals }) {
  // Disclaimers must be accepted through the web UI — block OAuth
  if (isOAuthRequest(locals)) return getResponse({ error: 'Disclaimers must be accepted through the web interface' }, 403);

  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const role = body.role;
  if (!VALID_ROLES.includes(role)) {
    return getResponse({ error: 'Invalid role. Must be "bidder" or "seller".' }, 400);
  }

  try {
    await acceptDisclaimer(user.id, role);
    return getResponse({ success: true, role }, 200);
  } catch (err) {
    console.error('Error accepting disclaimer:', err);
    return getResponse({ error: 'Failed to accept disclaimer' }, 500);
  }
}
