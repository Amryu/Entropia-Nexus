// @ts-nocheck
import { error } from '@sveltejs/kit';
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, params, locals }) {
  const user = requireVerified(locals);

  const auction = await apiCall(fetch, `/api/auction/${params.id}`);
  if (!auction || auction.error) {
    throw error(404, 'Auction not found');
  }

  if (String(auction.seller_id) !== String(user.id)) {
    throw error(403, 'Not your auction');
  }

  if (auction.status !== 'draft') {
    throw error(400, 'Only draft auctions can be edited');
  }

  return { auction };
}
