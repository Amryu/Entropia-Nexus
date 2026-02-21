// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch, url }) {
  const query = url.searchParams.get('q') || '';

  if (query.length < 2) {
    return { query, results: [] };
  }

  const results = await apiCall(fetch, `/search/detailed?query=${encodeURIComponent(query)}&fuzzy=true`);

  return { query, results: results || [] };
}
