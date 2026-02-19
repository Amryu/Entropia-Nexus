//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getValueHistory } from '$lib/server/inventory.js';

/**
 * GET /api/users/inventory/imports/value-history — Portfolio value over time
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const history = await getValueHistory(user.id);
    return getResponse(history, 200);
  } catch (err) {
    console.error('Error fetching value history:', err);
    return getResponse({ error: 'Failed to fetch value history' }, 500);
  }
}
