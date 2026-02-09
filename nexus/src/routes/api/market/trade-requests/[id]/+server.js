//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getTradeRequest } from '$lib/server/trade-requests.js';

/**
 * GET /api/market/trade-requests/[id] — Get a single trade request with items
 * Only the requester or target can view it.
 */
export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  const requestId = parseInt(params.id, 10);
  if (!Number.isFinite(requestId) || requestId <= 0) {
    return getResponse({ error: 'Invalid request ID' }, 400);
  }

  try {
    const tradeRequest = await getTradeRequest(requestId);
    if (!tradeRequest) {
      return getResponse({ error: 'Trade request not found' }, 404);
    }

    // Only requester, target, or admin can view
    const userId = String(user.id);
    const isParty = userId === String(tradeRequest.requester_id) || userId === String(tradeRequest.target_id);
    const isAdmin = user.grants?.includes('admin.panel') || user.administrator;
    if (!isParty && !isAdmin) {
      return getResponse({ error: 'Not authorized' }, 403);
    }

    return getResponse(tradeRequest, 200);
  } catch (err) {
    console.error('Error fetching trade request:', err);
    return getResponse({ error: 'Failed to fetch trade request' }, 500);
  }
}
