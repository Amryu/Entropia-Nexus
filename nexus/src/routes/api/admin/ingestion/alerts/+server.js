//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getAlerts } from '$lib/server/ingestion.js';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20'), 100);
  const days = url.searchParams.get('days');
  const periodDays = { '1': 1, '7': 7, '30': 30, '90': 90 }[days] ?? null;

  try {
    const result = await getAlerts(page, limit, periodDays);
    return getResponse(result, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get alerts:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
