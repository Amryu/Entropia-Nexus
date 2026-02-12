// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  requireVerified(locals, url.pathname);

  const result = await apiCall(fetch, '/api/auction/my');

  return {
    auctions: result?.auctions || [],
    bids: result?.bids || []
  };
}
