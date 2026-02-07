//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getLatestItemPrices } from '$lib/server/db.js';

const MAX_ITEMS = 100;

export async function GET({ url }) {
  const itemsParam = url.searchParams.get('items');
  if (!itemsParam) {
    return getResponse({ error: 'Missing required parameter: items' }, 400);
  }

  const itemIds = itemsParam.split(',').map(s => parseInt(s.trim(), 10)).filter(Number.isFinite);
  if (itemIds.length === 0) {
    return getResponse({ error: 'No valid item IDs provided' }, 400);
  }
  if (itemIds.length > MAX_ITEMS) {
    return getResponse({ error: `Maximum ${MAX_ITEMS} items per request` }, 400);
  }

  const source = url.searchParams.has('source') ? url.searchParams.get('source') || null : undefined;

  try {
    const prices = await getLatestItemPrices(itemIds, source);
    return getResponse({ prices }, 200);
  } catch (error) {
    console.error('Error fetching latest item prices:', error);
    return getResponse({ error: 'Failed to fetch latest prices' }, 500);
  }
}
