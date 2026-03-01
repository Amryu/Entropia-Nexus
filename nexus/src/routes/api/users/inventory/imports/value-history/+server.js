//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getValueHistory } from '$lib/server/inventory.js';
import { requireGrantAPI } from '$lib/server/auth.js';

/**
 * GET /api/users/inventory/imports/value-history — Portfolio value over time
 */
export async function GET({ url, locals }) {
  const user = requireGrantAPI(locals, 'inventory.read');
  const sinceParam = url.searchParams.get('since');
  const since = sinceParam ? new Date(sinceParam) : null;
  if (since && isNaN(since.getTime())) return getResponse({ error: 'Invalid since date' }, 400);

  try {
    const history = await getValueHistory(user.id, since);
    return getResponse(history, 200);
  } catch (err) {
    console.error('Error fetching value history:', err);
    return getResponse({ error: 'Failed to fetch value history' }, 500);
  }
}
