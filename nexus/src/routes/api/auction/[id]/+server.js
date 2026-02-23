// @ts-nocheck
/**
 * GET    /api/auction/[id] — Auction detail with bid history (public)
 * PUT    /api/auction/[id] — Edit draft or activate auction (owner)
 * DELETE /api/auction/[id] — Cancel auction (owner, no bids) or soft-delete draft
 */
import { getResponse } from '$lib/util.js';
import {
  getAuction, getBidHistory, updateAuction, activateAuction, cancelAuction,
  deleteAuction, validateAuctionInput, insertAuditLog, endExpiredAuctions
} from '$lib/server/auction.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

export async function GET({ params }) {
  try {
    // End any expired auctions on access
    await endExpiredAuctions();

    const auction = await getAuction(params.id);
    if (!auction) return getResponse({ error: 'Auction not found' }, 404);

    const bids = await getBidHistory(params.id);
    return getResponse({ ...auction, bids }, 200);
  } catch (err) {
    console.error('Error fetching auction:', err);
    return getResponse({ error: 'Failed to fetch auction' }, 500);
  }
}

export async function PUT({ params, request, locals }) {
  const user = requireGrantAPI(locals, 'auction.manage');

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  try {
    // Check ownership
    const auction = await getAuction(params.id);
    if (!auction) return getResponse({ error: 'Auction not found' }, 404);
    if (String(auction.seller_id) !== String(user.id)) {
      return getResponse({ error: 'Not your auction' }, 403);
    }

    // Activate action
    if (body.action === 'activate') {
      if (auction.status !== 'draft') {
        return getResponse({ error: 'Can only activate draft auctions' }, 400);
      }

      // Verify item set has items
      const { rows: sets } = await pool.query(
        `SELECT data FROM item_sets WHERE id = $1 AND user_id = $2`,
        [auction.item_set_id, user.id]
      );
      if (!sets[0]) return getResponse({ error: 'Item set not found' }, 400);
      const items = sets[0].data?.items;
      if (!items || items.length === 0) {
        return getResponse({ error: 'Item set must have at least one item' }, 400);
      }

      const activated = await activateAuction(params.id, user.id);
      if (!activated) return getResponse({ error: 'Failed to activate auction' }, 400);

      await insertAuditLog(null, params.id, user.id, 'activated', {
        starts_at: activated.starts_at,
        ends_at: activated.ends_at
      });
      return getResponse(activated, 200);
    }

    // Edit draft
    if (auction.status !== 'draft') {
      return getResponse({ error: 'Can only edit draft auctions' }, 400);
    }

    const validation = validateAuctionInput(body);
    if (validation.error) return getResponse({ error: validation.error }, 400);

    // Verify item set belongs to user
    const { rows: sets } = await pool.query(
      `SELECT id FROM item_sets WHERE id = $1 AND user_id = $2`,
      [validation.data.item_set_id, user.id]
    );
    if (sets.length === 0) {
      return getResponse({ error: 'Item set not found or not yours' }, 400);
    }

    const updated = await updateAuction(params.id, user.id, validation.data);
    if (!updated) return getResponse({ error: 'Failed to update auction' }, 400);

    await insertAuditLog(null, params.id, user.id, 'edited', {
      changes: validation.data
    });
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating auction:', err);
    return getResponse({ error: 'Failed to update auction' }, 500);
  }
}

export async function DELETE({ params, locals }) {
  const user = requireGrantAPI(locals, 'auction.manage');

  try {
    const auction = await getAuction(params.id);
    if (!auction) return getResponse({ error: 'Auction not found' }, 404);
    if (String(auction.seller_id) !== String(user.id)) {
      return getResponse({ error: 'Not your auction' }, 403);
    }

    // Draft: soft delete
    if (auction.status === 'draft') {
      const deleted = await deleteAuction(params.id, user.id);
      if (!deleted) return getResponse({ error: 'Failed to delete auction' }, 400);
      return getResponse({ success: true }, 200);
    }

    // Active with no bids: cancel
    const result = await cancelAuction(params.id, user.id);
    if (!result) return getResponse({ error: 'Auction not found' }, 404);
    if (result.error) return getResponse({ error: result.error }, 400);

    return getResponse(result, 200);
  } catch (err) {
    console.error('Error deleting auction:', err);
    return getResponse({ error: 'Failed to delete auction' }, 500);
  }
}
