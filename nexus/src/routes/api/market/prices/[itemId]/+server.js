//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getItemPriceHistory, getItemPriceSummaries } from '$lib/server/db.js';

const MAX_LIMIT = 2000;
const DEFAULT_LIMIT = 500;

const MS_48H = 48 * 60 * 60 * 1000;
const MS_30D = 30 * 24 * 60 * 60 * 1000;
const MS_365D = 365 * 24 * 60 * 60 * 1000;

/**
 * Determine the best granularity based on the requested time range.
 */
function autoGranularity(from, to) {
  const range = to.getTime() - from.getTime();
  if (range <= MS_48H) return 'raw';
  if (range <= MS_30D) return 'hour';
  if (range <= MS_365D) return 'day';
  return 'week';
}

export async function GET({ params, url }) {
  const itemId = parseInt(params.itemId, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  const fromParam = url.searchParams.get('from');
  const toParam = url.searchParams.get('to');
  const granularity = url.searchParams.get('granularity') || 'auto';
  const source = url.searchParams.has('source') ? url.searchParams.get('source') || null : undefined;
  const limitParam = parseInt(url.searchParams.get('limit'), 10);
  const limit = Number.isFinite(limitParam) ? Math.min(Math.max(1, limitParam), MAX_LIMIT) : DEFAULT_LIMIT;

  const validGranularities = ['raw', 'hour', 'day', 'week', 'auto'];
  if (!validGranularities.includes(granularity)) {
    return getResponse({ error: `Invalid granularity. Must be one of: ${validGranularities.join(', ')}` }, 400);
  }

  const now = new Date();
  const from = fromParam ? new Date(fromParam) : new Date(now.getTime() - MS_30D);
  const to = toParam ? new Date(toParam) : now;

  if (isNaN(from.getTime()) || isNaN(to.getTime())) {
    return getResponse({ error: 'Invalid date format for from/to' }, 400);
  }

  const resolvedGranularity = granularity === 'auto' ? autoGranularity(from, to) : granularity;

  try {
    if (resolvedGranularity === 'raw') {
      const rows = await getItemPriceHistory(itemId, { from, to, source, limit });
      return getResponse({
        item_id: itemId,
        granularity: 'raw',
        from: from.toISOString(),
        to: to.toISOString(),
        data: rows.map(r => ({
          timestamp: r.recorded_at,
          price: parseFloat(r.price_value),
          quantity: r.quantity
        }))
      }, 200);
    }

    const rows = await getItemPriceSummaries(itemId, {
      periodType: resolvedGranularity,
      from,
      to,
      source,
      limit
    });

    return getResponse({
      item_id: itemId,
      granularity: resolvedGranularity,
      from: from.toISOString(),
      to: to.toISOString(),
      data: rows.map(r => ({
        timestamp: r.period_start,
        min: parseFloat(r.price_min),
        max: parseFloat(r.price_max),
        avg: parseFloat(r.price_avg),
        p5: r.price_p5 != null ? parseFloat(r.price_p5) : null,
        median: r.price_median != null ? parseFloat(r.price_median) : null,
        p95: r.price_p95 != null ? parseFloat(r.price_p95) : null,
        wap: r.price_wap != null ? parseFloat(r.price_wap) : null,
        volume: r.volume != null ? parseInt(r.volume, 10) : null,
        sample_count: r.sample_count
      }))
    }, 200);
  } catch (error) {
    console.error('Error fetching item price history:', error);
    return getResponse({ error: 'Failed to fetch price history' }, 500);
  }
}
