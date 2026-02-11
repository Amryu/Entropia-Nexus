//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserItemSetById, updateUserItemSet, deleteUserItemSet } from '$lib/server/db.js';
import { sanitizeItemSetData, getPayloadSizeBytes, MAX_ITEM_SET_BYTES } from '$lib/server/itemSetUtils.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

function sanitizeName(value, fallback = 'New Item Set') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const record = await getUserItemSetById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Item set not found.' }, 404);
    }
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error fetching item set:', error);
    return getResponse({ error: 'Failed to fetch item set.' }, 500);
  }
}

export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  // Rate limit: 30 updates per minute
  const rateCheck = checkRateLimit(`itemset:update:${user.id}`, 30, 60_000);
  if (!rateCheck.allowed) {
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
    const existing = await getUserItemSetById(user.id, params.id);
    if (!existing) {
      return getResponse({ error: 'Item set not found.' }, 404);
    }

    const sanitizedData = sanitizeItemSetData(body?.data ?? existing.data);
    const name = sanitizeName(body?.name ?? existing.name);

    if (getPayloadSizeBytes(sanitizedData) > MAX_ITEM_SET_BYTES) {
      return getResponse({ error: 'Item set data exceeds 100KB limit.' }, 413);
    }

    const record = await updateUserItemSet(user.id, params.id, name, sanitizedData);
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error updating item set:', error);
    return getResponse({ error: 'Failed to update item set.' }, 500);
  }
}

export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  // Rate limit: 10 deletes per minute
  const rateCheck = checkRateLimit(`itemset:delete:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  try {
    const record = await getUserItemSetById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Item set not found.' }, 404);
    }

    await deleteUserItemSet(user.id, params.id);
    return getResponse({ success: true }, 200);
  } catch (error) {
    console.error('Error deleting item set:', error);
    return getResponse({ error: 'Failed to delete item set.' }, 500);
  }
}
