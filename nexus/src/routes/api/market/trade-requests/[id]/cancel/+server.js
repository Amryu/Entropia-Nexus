//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { cancelTradeRequest } from '$lib/server/trade-requests.js';
import { isOAuthRequest } from '$lib/server/auth.js';

/**
 * POST /api/market/trade-requests/[id]/cancel — Cancel a trade request
 * Only the requester or target can cancel.
 */
export async function POST({ params, locals }) {
  if (isOAuthRequest(locals)) return getResponse({ error: 'This endpoint is not available via the OAuth API' }, 403);

  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  const requestId = parseInt(params.id, 10);
  if (!Number.isFinite(requestId) || requestId <= 0) {
    return getResponse({ error: 'Invalid request ID' }, 400);
  }

  try {
    const result = await cancelTradeRequest(requestId, user.id);
    if (!result) {
      return getResponse({ error: 'Trade request not found or already closed' }, 404);
    }
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error cancelling trade request:', err);
    return getResponse({ error: 'Failed to cancel trade request' }, 500);
  }
}
