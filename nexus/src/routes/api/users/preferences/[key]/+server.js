//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getPreference, deletePreference, isValidKey } from '$lib/server/preferences.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * GET /api/users/preferences/[key] — Get a single preference by key
 */
export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  const key = decodeURIComponent(params.key);
  if (!isValidKey(key)) {
    return getResponse({ error: 'Invalid preference key' }, 400);
  }

  try {
    const pref = await getPreference(user.id, key);
    if (!pref) {
      return getResponse({ key, data: null }, 200);
    }
    return getResponse({ key: pref.key, data: pref.data, updated_at: pref.updated_at }, 200);
  } catch (err) {
    console.error('Error fetching preference:', err);
    return getResponse({ error: 'Failed to fetch preference' }, 500);
  }
}

/**
 * DELETE /api/users/preferences/[key] — Delete a single preference
 */
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  // Rate limit: 30 writes per minute per user
  const rateCheck = checkRateLimit(`pref:${user.id}`, 30, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const key = decodeURIComponent(params.key);
  if (!isValidKey(key)) {
    return getResponse({ error: 'Invalid preference key' }, 400);
  }

  try {
    const deleted = await deletePreference(user.id, key);
    if (!deleted) {
      return getResponse({ error: 'Preference not found' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('Error deleting preference:', err);
    return getResponse({ error: 'Failed to delete preference' }, 500);
  }
}
