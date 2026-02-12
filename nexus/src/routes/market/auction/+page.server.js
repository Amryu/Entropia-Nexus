// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch, url }) {
  const status = url.searchParams.get('status') || 'active';
  const search = url.searchParams.get('search') || '';
  const sort = url.searchParams.get('sort') || 'ends_at';
  const order = url.searchParams.get('order') || 'asc';
  const page = parseInt(url.searchParams.get('page') || '1', 10);
  const limit = 24;
  const offset = (page - 1) * limit;

  const params = new URLSearchParams({ status, sort, order, limit: String(limit), offset: String(offset) });
  if (search) params.set('search', search);

  const result = await apiCall(fetch, `/api/auction?${params}`);

  return {
    auctions: result?.auctions || [],
    total: result?.total || 0,
    filters: { status, search, sort, order, page },
    limit
  };
}
