//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { insertItemPrices } from '$lib/server/db.js';

const MAX_PRICES_PER_REQUEST = 1000;
const MAX_SOURCE_LENGTH = 100;

export async function POST({ request, locals }) {
  const user = locals.session?.realUser || locals.session?.user;

  if (!user) {
    return getResponse({ error: 'Not authenticated' }, 401);
  }
  if (!user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'Only administrators can ingest price data' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body' }, 400);
  }

  if (!Array.isArray(body?.prices) || body.prices.length === 0) {
    return getResponse({ error: 'Body must contain a non-empty prices array' }, 400);
  }
  if (body.prices.length > MAX_PRICES_PER_REQUEST) {
    return getResponse({ error: `Maximum ${MAX_PRICES_PER_REQUEST} prices per request` }, 400);
  }

  const now = new Date();
  const validated = [];

  for (let i = 0; i < body.prices.length; i++) {
    const p = body.prices[i];

    const itemId = parseInt(p.item_id, 10);
    if (!Number.isFinite(itemId) || itemId <= 0) {
      return getResponse({ error: `prices[${i}].item_id must be a positive integer` }, 400);
    }

    const priceValue = parseFloat(p.price_value);
    if (!Number.isFinite(priceValue) || priceValue < 0) {
      return getResponse({ error: `prices[${i}].price_value must be a non-negative number` }, 400);
    }

    const quantity = p.quantity !== undefined ? parseInt(p.quantity, 10) : 1;
    if (!Number.isFinite(quantity) || quantity < 1) {
      return getResponse({ error: `prices[${i}].quantity must be a positive integer` }, 400);
    }

    let source = p.source !== undefined ? p.source : null;
    if (source !== null) {
      if (typeof source !== 'string' || source.length > MAX_SOURCE_LENGTH) {
        return getResponse({ error: `prices[${i}].source must be a string of max ${MAX_SOURCE_LENGTH} characters` }, 400);
      }
      source = source.trim() || null;
    }

    let recordedAt = p.recorded_at ? new Date(p.recorded_at) : null;
    if (recordedAt && isNaN(recordedAt.getTime())) {
      return getResponse({ error: `prices[${i}].recorded_at is not a valid date` }, 400);
    }
    if (recordedAt && recordedAt.getTime() > now.getTime() + 60000) {
      return getResponse({ error: `prices[${i}].recorded_at cannot be in the future` }, 400);
    }

    validated.push({
      item_id: itemId,
      price_value: priceValue,
      quantity,
      source,
      recorded_at: recordedAt
    });
  }

  try {
    await insertItemPrices(validated);
    return getResponse({ inserted: validated.length }, 201);
  } catch (error) {
    console.error('Error inserting item prices:', error);
    return getResponse({ error: 'Failed to insert price data' }, 500);
  }
}
