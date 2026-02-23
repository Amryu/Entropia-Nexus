//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { countUserItemSets, createUserItemSet, getUserItemSets, getUserLoadoutById } from '$lib/server/db.js';
import { sanitizeItemSetData, getPayloadSizeBytes, MAX_ITEM_SET_BYTES, MAX_ITEM_SETS_PER_USER } from '$lib/server/itemSetUtils.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

function sanitizeName(value, fallback = 'New Item Set') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

export async function GET({ locals }) {
  const user = requireGrantAPI(locals, 'itemsets.read');

  try {
    const itemSets = await getUserItemSets(user.id);
    return getResponse(itemSets, 200);
  } catch (error) {
    console.error('Error fetching item sets:', error);
    return getResponse({ error: 'Failed to fetch item sets.' }, 500);
  }
}

export async function POST({ request, locals }) {
  const user = requireGrantAPI(locals, 'itemsets.manage');

  // Rate limit: 10 creates per minute
  const rateMinute = checkRateLimit(`itemset:create:${user.id}`, 10, 60_000);
  if (!rateMinute.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  // Rate limit: 30 creates per hour
  const rateHour = checkRateLimit(`itemset:create-h:${user.id}`, 30, 3_600_000);
  if (!rateHour.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  if (getPayloadSizeBytes(body) > MAX_ITEM_SET_BYTES) {
    return getResponse({ error: 'Payload exceeds 100KB limit.' }, 413);
  }

  try {
    const setCount = await countUserItemSets(user.id);
    if (setCount >= MAX_ITEM_SETS_PER_USER) {
      return getResponse({ error: `Item set limit reached (${MAX_ITEM_SETS_PER_USER}).` }, 403);
    }

    const sanitizedData = sanitizeItemSetData(body?.data);
    const name = sanitizeName(body?.name);

    if (getPayloadSizeBytes(sanitizedData) > MAX_ITEM_SET_BYTES) {
      return getResponse({ error: 'Item set data exceeds 100KB limit.' }, 413);
    }

    // Validate loadout_id if provided
    let loadoutId = null;
    if (body?.loadout_id) {
      const loadout = await getUserLoadoutById(user.id, body.loadout_id);
      if (!loadout) {
        return getResponse({ error: 'Loadout not found.' }, 404);
      }
      loadoutId = body.loadout_id;
    }

    const record = await createUserItemSet(user.id, name, sanitizedData, loadoutId);
    return getResponse(record, 201);
  } catch (error) {
    console.error('Error creating item set:', error);
    return getResponse({ error: 'Failed to create item set.' }, 500);
  }
}
