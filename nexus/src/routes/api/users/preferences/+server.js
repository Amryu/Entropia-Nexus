//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getAllPreferences, upsertPreference, isValidKey, validateDataSize } from '$lib/server/preferences.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * GET /api/users/preferences — Get all preferences for the logged-in user
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  try {
    const prefs = await getAllPreferences(user.id);
    // Return as { key: data } map for convenience
    const result = {};
    for (const pref of prefs) {
      result[pref.key] = pref.data;
    }
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error fetching preferences:', err);
    return getResponse({ error: 'Failed to fetch preferences' }, 500);
  }
}

/**
 * PUT /api/users/preferences — Upsert a single preference
 * Body: { key: string, data: object }
 */
export async function PUT({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);

  // Rate limit: 30 writes per minute per user
  const rateCheck = checkRateLimit(`pref:${user.id}`, 30, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const { key, data } = body;

  // Validate key
  if (!key || typeof key !== 'string') {
    return getResponse({ error: 'key is required and must be a string' }, 400);
  }
  if (!isValidKey(key)) {
    return getResponse({ error: 'Invalid preference key' }, 400);
  }

  // Validate data exists
  if (data === undefined || data === null) {
    return getResponse({ error: 'data is required' }, 400);
  }

  // Validate data size (20KB limit)
  if (!validateDataSize(data)) {
    return getResponse({ error: 'Data exceeds maximum size of 20KB' }, 400);
  }

  try {
    const result = await upsertPreference(user.id, key, data);
    return getResponse({ key: result.key, data: result.data, updated_at: result.updated_at }, 200);
  } catch (err) {
    if (err.message?.includes('Maximum preference keys')) {
      return getResponse({ error: err.message }, 400);
    }
    console.error('Error saving preference:', err);
    return getResponse({ error: 'Failed to save preference' }, 500);
  }
}
