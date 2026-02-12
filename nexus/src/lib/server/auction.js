// @ts-nocheck
/**
 * Server-side auction logic — database operations, validation, state machine.
 */
import { pool } from './db.js';
import {
  getMinIncrement, getMinNextBid, calculateAuctionFee, isBuyoutOnly, getMaxDuration,
  ANTI_SNIPE_WINDOW_MS, ANTI_SNIPE_EXTENSION_MS, ANTI_SNIPE_MAX_EXTENSION_MS
} from '$lib/common/auctionUtils.js';

// Re-export utilities for API layer convenience
export {
  getMinIncrement, getMinNextBid, calculateAuctionFee, isBuyoutOnly, getMaxDuration
};

// ---------- Constants ----------

export const MAX_AUCTIONS_PER_USER = 20;
export const MAX_TITLE_LENGTH = 120;
export const MAX_DESCRIPTION_LENGTH = 2000;
export const MAX_STARTING_BID = 10000000;  // 10M PED
export const MAX_BUYOUT_PRICE = 10000000;
export const MIN_STARTING_BID = 0.01;

// Rate limit constants
export const RATE_LIMIT_CREATE_PER_HOUR = 5;
export const RATE_LIMIT_BID_PER_MIN = 10;
export const RATE_LIMIT_BUYOUT_PER_MIN = 5;
export const RATE_LIMIT_SETTLE_PER_MIN = 10;
export const RATE_LIMIT_ADMIN_PER_MIN = 20;

// ---------- Helpers ----------

function round2(value) {
  return Math.round(value * 100) / 100;
}

function parseNumeric(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

// ---------- Audit Log ----------

/**
 * Insert an entry into the auction audit log.
 * @param {import('pg').PoolClient|null} client - DB client (null for pool query)
 * @param {string} auctionId
 * @param {number|null} userId
 * @param {string} action - auction_audit_action enum value
 * @param {object|null} details - JSONB details
 */
export async function insertAuditLog(client, auctionId, userId, action, details = null) {
  const q = `INSERT INTO auction_audit_log (auction_id, user_id, action, details) VALUES ($1, $2, $3, $4)`;
  const params = [auctionId, userId, action, details ? JSON.stringify(details) : null];
  if (client) {
    await client.query(q, params);
  } else {
    await pool.query(q, params);
  }
}

/**
 * Get audit log for an auction.
 * @param {string} auctionId
 * @returns {Promise<Array>}
 */
export async function getAuditLog(auctionId) {
  const { rows } = await pool.query(
    `SELECT al.*, u.eu_name AS user_name
     FROM auction_audit_log al
     LEFT JOIN users u ON u.id = al.user_id
     WHERE al.auction_id = $1
     ORDER BY al.created_at DESC`,
    [auctionId]
  );
  return rows;
}

// ---------- Disclaimers ----------

/**
 * Check if a user has accepted a disclaimer role.
 * @param {number} userId
 * @param {string} role - 'bidder' or 'seller'
 * @returns {Promise<boolean>}
 */
export async function hasAcceptedDisclaimer(userId, role) {
  const { rows } = await pool.query(
    `SELECT 1 FROM auction_disclaimers WHERE user_id = $1 AND role = $2`,
    [userId, role]
  );
  return rows.length > 0;
}

/**
 * Get all disclaimer statuses for a user.
 * @param {number} userId
 * @returns {Promise<{bidder: boolean, seller: boolean}>}
 */
export async function getDisclaimerStatus(userId) {
  const { rows } = await pool.query(
    `SELECT role FROM auction_disclaimers WHERE user_id = $1`,
    [userId]
  );
  const roles = rows.map(r => r.role);
  return { bidder: roles.includes('bidder'), seller: roles.includes('seller') };
}

/**
 * Accept a disclaimer for a user.
 * @param {number} userId
 * @param {string} role - 'bidder' or 'seller'
 */
export async function acceptDisclaimer(userId, role) {
  await pool.query(
    `INSERT INTO auction_disclaimers (user_id, role) VALUES ($1, $2)
     ON CONFLICT (user_id, role) DO NOTHING`,
    [userId, role]
  );
}

// ---------- Auction CRUD ----------

/**
 * Get auction by ID with seller info.
 * @param {string} auctionId
 * @returns {Promise<object|null>}
 */
export async function getAuction(auctionId) {
  const { rows } = await pool.query(
    `SELECT a.*,
       u.eu_name AS seller_name,
       u.avatar_url AS seller_avatar,
       is2.name AS item_set_name,
       is2.data AS item_set_data,
       is2.customized AS item_set_customized
     FROM auctions a
     LEFT JOIN users u ON u.id = a.seller_id
     LEFT JOIN item_sets is2 ON is2.id = a.item_set_id
     WHERE a.id = $1 AND a.deleted_at IS NULL`,
    [auctionId]
  );
  return rows[0] || null;
}

/**
 * List auctions with filters and pagination.
 * @param {object} opts
 * @param {string} [opts.status] - Filter by status
 * @param {string} [opts.search] - Search title
 * @param {string} [opts.sort] - Sort field (ends_at, created_at, current_bid, bid_count)
 * @param {string} [opts.order] - Sort order (asc, desc)
 * @param {number} [opts.limit]
 * @param {number} [opts.offset]
 * @returns {Promise<{auctions: Array, total: number}>}
 */
export async function listAuctions(opts = {}) {
  const {
    status = 'active',
    search,
    sort = 'ends_at',
    order = 'asc',
    limit = 24,
    offset = 0
  } = opts;

  const conditions = ['a.deleted_at IS NULL'];
  const params = [];
  let paramIdx = 1;

  // Status filter
  if (status === 'active') {
    conditions.push(`a.status IN ('active', 'frozen')`);
  } else if (status) {
    conditions.push(`a.status = $${paramIdx++}`);
    params.push(status);
  }

  // Search filter (escape LIKE special characters)
  if (search && typeof search === 'string') {
    const escaped = search.slice(0, 100).replace(/[%_\\]/g, '\\$&');
    conditions.push(`a.title ILIKE $${paramIdx++}`);
    params.push(`%${escaped}%`);
  }

  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

  // Sort
  const VALID_SORTS = ['ends_at', 'created_at', 'current_bid', 'bid_count', 'starting_bid'];
  const sortCol = VALID_SORTS.includes(sort) ? sort : 'ends_at';
  const sortOrder = order === 'desc' ? 'DESC' : 'ASC';
  const nullsOrder = sortOrder === 'ASC' ? 'NULLS LAST' : 'NULLS FIRST';

  // Count
  const countQuery = `SELECT COUNT(*) FROM auctions a ${where}`;
  const { rows: countRows } = await pool.query(countQuery, params);
  const total = parseInt(countRows[0].count, 10);

  // Fetch
  const limitVal = Math.min(Math.max(1, parseInt(limit, 10) || 24), 100);
  const offsetVal = Math.max(0, parseInt(offset, 10) || 0);

  const dataQuery = `
    SELECT a.*,
      u.eu_name AS seller_name,
      is2.name AS item_set_name,
      is2.data AS item_set_data,
      is2.customized AS item_set_customized
    FROM auctions a
    LEFT JOIN users u ON u.id = a.seller_id
    LEFT JOIN item_sets is2 ON is2.id = a.item_set_id
    ${where}
    ORDER BY a.${sortCol} ${sortOrder} ${nullsOrder}
    LIMIT $${paramIdx++} OFFSET $${paramIdx++}
  `;
  params.push(limitVal, offsetVal);

  const { rows } = await pool.query(dataQuery, params);
  return { auctions: rows, total };
}

/**
 * Get user's own auctions.
 * @param {number} userId
 * @returns {Promise<Array>}
 */
export async function getUserAuctions(userId) {
  const { rows } = await pool.query(
    `SELECT a.*,
       is2.name AS item_set_name,
       is2.data AS item_set_data,
       is2.customized AS item_set_customized
     FROM auctions a
     LEFT JOIN item_sets is2 ON is2.id = a.item_set_id
     WHERE a.seller_id = $1 AND a.deleted_at IS NULL
     ORDER BY a.created_at DESC`,
    [userId]
  );
  return rows;
}

/**
 * Get auctions user has bid on.
 * @param {number} userId
 * @returns {Promise<Array>}
 */
export async function getUserBids(userId) {
  const { rows } = await pool.query(
    `SELECT DISTINCT ON (a.id)
       a.*,
       u.eu_name AS seller_name,
       is2.name AS item_set_name,
       is2.data AS item_set_data,
       ab.amount AS my_bid,
       ab.status AS my_bid_status,
       ab.created_at AS my_bid_at
     FROM auction_bids ab
     JOIN auctions a ON a.id = ab.auction_id
     LEFT JOIN users u ON u.id = a.seller_id
     LEFT JOIN item_sets is2 ON is2.id = a.item_set_id
     WHERE ab.bidder_id = $1 AND a.deleted_at IS NULL
     ORDER BY a.id, ab.created_at DESC`,
    [userId]
  );
  return rows;
}

/**
 * Count active auctions for a user (for limits).
 * @param {number} userId
 * @returns {Promise<number>}
 */
export async function countUserActiveAuctions(userId) {
  const { rows } = await pool.query(
    `SELECT COUNT(*) FROM auctions
     WHERE seller_id = $1 AND status IN ('draft', 'active', 'frozen') AND deleted_at IS NULL`,
    [userId]
  );
  return parseInt(rows[0].count, 10);
}

// ---------- Validation ----------

/**
 * Sanitize auction title.
 * @param {any} value
 * @returns {string}
 */
export function sanitizeTitle(value) {
  if (typeof value !== 'string') return 'New Auction';
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_TITLE_LENGTH) : 'New Auction';
}

/**
 * Sanitize auction description.
 * @param {any} value
 * @returns {string|null}
 */
export function sanitizeDescription(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_DESCRIPTION_LENGTH) : null;
}

/**
 * Validate auction create/edit input.
 * @param {object} body
 * @returns {{ error: string }|{ data: object }}
 */
export function validateAuctionInput(body) {
  const title = sanitizeTitle(body.title);
  const description = sanitizeDescription(body.description);

  // Starting bid
  const startingBid = parseNumeric(body.starting_bid);
  if (startingBid === null || startingBid < MIN_STARTING_BID || startingBid > MAX_STARTING_BID) {
    return { error: `Starting bid must be between ${MIN_STARTING_BID} and ${MAX_STARTING_BID} PED` };
  }

  // Buyout price (optional)
  let buyoutPrice = null;
  if (body.buyout_price != null && body.buyout_price !== '' && body.buyout_price !== false) {
    buyoutPrice = parseNumeric(body.buyout_price);
    if (buyoutPrice === null || buyoutPrice < startingBid || buyoutPrice > MAX_BUYOUT_PRICE) {
      return { error: 'Buyout price must be at least the starting bid' };
    }
  }

  // Duration
  const durationDays = parseInt(body.duration_days, 10);
  const maxDuration = getMaxDuration({ starting_bid: startingBid, buyout_price: buyoutPrice });
  if (!Number.isFinite(durationDays) || durationDays < 1 || durationDays > maxDuration) {
    return { error: `Duration must be between 1 and ${maxDuration} days` };
  }

  // Item set ID
  if (!body.item_set_id || typeof body.item_set_id !== 'string') {
    return { error: 'Item set is required' };
  }

  return {
    data: {
      title,
      description,
      starting_bid: round2(startingBid),
      buyout_price: buyoutPrice !== null ? round2(buyoutPrice) : null,
      duration_days: durationDays,
      item_set_id: body.item_set_id
    }
  };
}

// ---------- Create ----------

/**
 * Create a new auction (draft status).
 * @param {number} userId
 * @param {object} data - Validated auction data
 * @returns {Promise<object>} Created auction
 */
export async function createAuction(userId, data) {
  const { rows } = await pool.query(
    `INSERT INTO auctions (seller_id, item_set_id, title, description, starting_bid, buyout_price, duration_days)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     RETURNING *`,
    [userId, data.item_set_id, data.title, data.description, data.starting_bid, data.buyout_price, data.duration_days]
  );
  return rows[0];
}

// ---------- Update (draft only) ----------

/**
 * Update a draft auction.
 * @param {string} auctionId
 * @param {number} userId
 * @param {object} data - Validated auction data
 * @returns {Promise<object|null>}
 */
export async function updateAuction(auctionId, userId, data) {
  const { rows } = await pool.query(
    `UPDATE auctions SET
       title = $3, description = $4, starting_bid = $5,
       buyout_price = $6, duration_days = $7,
       item_set_id = $8, updated_at = NOW()
     WHERE id = $1 AND seller_id = $2 AND status = 'draft' AND deleted_at IS NULL
     RETURNING *`,
    [auctionId, userId, data.title, data.description, data.starting_bid, data.buyout_price, data.duration_days, data.item_set_id]
  );
  return rows[0] || null;
}

// ---------- Activate ----------

/**
 * Activate a draft auction (transitions to active, sets timing).
 * @param {string} auctionId
 * @param {number} userId
 * @returns {Promise<object|null>}
 */
export async function activateAuction(auctionId, userId) {
  const { rows } = await pool.query(
    `UPDATE auctions SET
       status = 'active',
       starts_at = NOW(),
       ends_at = NOW() + (duration_days || ' days')::INTERVAL,
       original_ends_at = NOW() + (duration_days || ' days')::INTERVAL,
       updated_at = NOW()
     WHERE id = $1 AND seller_id = $2 AND status = 'draft' AND deleted_at IS NULL
     RETURNING *`,
    [auctionId, userId]
  );
  return rows[0] || null;
}

// ---------- Cancel (seller) ----------

/**
 * Cancel an auction (seller, only if no bids).
 * @param {string} auctionId
 * @param {number} userId
 * @returns {Promise<object|null>}
 */
export async function cancelAuction(auctionId, userId) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND seller_id = $2 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId, userId]
    );
    const auction = rows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return null;
    }

    if (auction.status !== 'draft' && auction.status !== 'active') {
      await client.query('ROLLBACK');
      return { error: 'Can only cancel draft or active auctions' };
    }

    if (auction.bid_count > 0) {
      await client.query('ROLLBACK');
      return { error: 'Cannot cancel an auction with bids. Contact an admin if needed.' };
    }

    const { rows: updated } = await client.query(
      `UPDATE auctions SET status = 'cancelled', updated_at = NOW() WHERE id = $1 RETURNING *`,
      [auctionId]
    );

    await insertAuditLog(client, auctionId, userId, 'cancelled_by_seller', null);
    await client.query('COMMIT');
    return updated[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Delete (soft, draft only) ----------

/**
 * Soft-delete a draft auction.
 * @param {string} auctionId
 * @param {number} userId
 * @returns {Promise<boolean>}
 */
export async function deleteAuction(auctionId, userId) {
  const { rowCount } = await pool.query(
    `UPDATE auctions SET deleted_at = NOW() WHERE id = $1 AND seller_id = $2 AND status = 'draft' AND deleted_at IS NULL`,
    [auctionId, userId]
  );
  return rowCount > 0;
}

// ---------- Bidding ----------

/**
 * Get bid history for an auction.
 * @param {string} auctionId
 * @returns {Promise<Array>}
 */
export async function getBidHistory(auctionId) {
  const { rows } = await pool.query(
    `SELECT ab.*, u.eu_name AS bidder_name
     FROM auction_bids ab
     LEFT JOIN users u ON u.id = ab.bidder_id
     WHERE ab.auction_id = $1
     ORDER BY ab.created_at DESC`,
    [auctionId]
  );
  return rows;
}

/**
 * Place a bid on an auction. Uses transaction with FOR UPDATE locking.
 * @param {string} auctionId
 * @param {number} bidderId
 * @param {number} amount
 * @returns {Promise<{bid: object, auction: object}|{error: string}>}
 */
export async function placeBid(auctionId, bidderId, amount) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Lock auction row
    const { rows: auctionRows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId]
    );
    const auction = auctionRows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found' };
    }

    if (auction.status !== 'active') {
      await client.query('ROLLBACK');
      return { error: 'Auction is not active' };
    }

    // Check auction hasn't ended
    if (new Date(auction.ends_at) <= new Date()) {
      await client.query('ROLLBACK');
      return { error: 'Auction has ended' };
    }

    // Cannot bid on own auction
    if (String(auction.seller_id) === String(bidderId)) {
      await client.query('ROLLBACK');
      return { error: 'Cannot bid on your own auction' };
    }

    // Buyout-only auctions don't accept bids
    if (isBuyoutOnly(auction)) {
      await client.query('ROLLBACK');
      return { error: 'This is a buyout-only listing. Use the Buy Now option.' };
    }

    // Validate bid amount
    const bidAmount = round2(amount);
    const hasBids = auction.bid_count > 0;
    const minBid = getMinNextBid(
      parseFloat(hasBids ? auction.current_bid : auction.starting_bid),
      hasBids
    );

    if (bidAmount < minBid) {
      await client.query('ROLLBACK');
      return { error: `Minimum bid is ${minBid.toFixed(2)} PED` };
    }

    // If there's a buyout price, bid cannot exceed it
    if (auction.buyout_price !== null && bidAmount >= parseFloat(auction.buyout_price)) {
      await client.query('ROLLBACK');
      return { error: `Bid exceeds buyout price. Use Buy Now for ${parseFloat(auction.buyout_price).toFixed(2)} PED instead.` };
    }

    // Mark previous active bid as outbid
    if (hasBids) {
      await client.query(
        `UPDATE auction_bids SET status = 'outbid'
         WHERE auction_id = $1 AND status = 'active'`,
        [auctionId]
      );
    }

    // Insert new bid
    const { rows: bidRows } = await client.query(
      `INSERT INTO auction_bids (auction_id, bidder_id, amount) VALUES ($1, $2, $3) RETURNING *`,
      [auctionId, bidderId, bidAmount]
    );
    const bid = bidRows[0];

    // Update auction
    const updateParts = [
      `current_bid = $2`,
      `current_bidder = $3`,
      `bid_count = bid_count + 1`,
      `updated_at = NOW()`
    ];
    const updateParams = [auctionId, bidAmount, bidderId];

    // Anti-sniping: reset to 5 minutes if bid is within last 5 minutes
    const now = new Date();
    const endsAt = new Date(auction.ends_at);
    const originalEndsAt = new Date(auction.original_ends_at);
    const timeLeft = endsAt.getTime() - now.getTime();

    if (timeLeft < ANTI_SNIPE_WINDOW_MS && timeLeft > 0) {
      const maxEnd = originalEndsAt.getTime() + ANTI_SNIPE_MAX_EXTENSION_MS;
      const newEnd = Math.min(now.getTime() + ANTI_SNIPE_EXTENSION_MS, maxEnd);
      if (newEnd > endsAt.getTime()) {
        updateParts.push(`ends_at = to_timestamp($${updateParams.length + 1})`);
        updateParams.push(newEnd / 1000);
      }
    }

    const { rows: updatedAuction } = await client.query(
      `UPDATE auctions SET ${updateParts.join(', ')} WHERE id = $1 RETURNING *`,
      updateParams
    );

    // Audit log
    await insertAuditLog(client, auctionId, bidderId, 'bid_placed', {
      amount: bidAmount,
      bid_id: bid.id,
      previous_bid: auction.current_bid ? parseFloat(auction.current_bid) : null,
      previous_bidder: auction.current_bidder
    });

    await client.query('COMMIT');
    return { bid, auction: updatedAuction[0] };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Buyout ----------

/**
 * Buy out an auction immediately.
 * @param {string} auctionId
 * @param {number} buyerId
 * @returns {Promise<{auction: object}|{error: string}>}
 */
export async function buyoutAuction(auctionId, buyerId) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows: auctionRows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId]
    );
    const auction = auctionRows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found' };
    }

    if (auction.status !== 'active') {
      await client.query('ROLLBACK');
      return { error: 'Auction is not active' };
    }

    if (auction.buyout_price === null) {
      await client.query('ROLLBACK');
      return { error: 'This auction does not have a buyout option' };
    }

    if (new Date(auction.ends_at) <= new Date()) {
      await client.query('ROLLBACK');
      return { error: 'Auction has ended' };
    }

    if (String(auction.seller_id) === String(buyerId)) {
      await client.query('ROLLBACK');
      return { error: 'Cannot buy out your own auction' };
    }

    const buyoutAmount = parseFloat(auction.buyout_price);

    // Mark any active bid as outbid
    if (auction.bid_count > 0) {
      await client.query(
        `UPDATE auction_bids SET status = 'outbid'
         WHERE auction_id = $1 AND status = 'active'`,
        [auctionId]
      );
    }

    // Insert buyout as a bid
    const { rows: bidRows } = await client.query(
      `INSERT INTO auction_bids (auction_id, bidder_id, amount, status)
       VALUES ($1, $2, $3, 'won') RETURNING *`,
      [auctionId, buyerId, buyoutAmount]
    );

    // End the auction immediately
    const fee = calculateAuctionFee(buyoutAmount);
    const { rows: updated } = await client.query(
      `UPDATE auctions SET
         status = 'ended',
         current_bid = $2,
         current_bidder = $3,
         bid_count = bid_count + 1,
         fee = $4,
         ends_at = NOW(),
         updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [auctionId, buyoutAmount, buyerId, fee]
    );

    await insertAuditLog(client, auctionId, buyerId, 'buyout', {
      amount: buyoutAmount,
      fee,
      bid_id: bidRows[0].id
    });

    await client.query('COMMIT');
    return { auction: updated[0] };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Settle ----------

/**
 * Settle an ended auction (seller confirms completion).
 * @param {string} auctionId
 * @param {number} userId - Must be the seller
 * @returns {Promise<object|{error: string}>}
 */
export async function settleAuction(auctionId, userId) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND seller_id = $2 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId, userId]
    );
    const auction = rows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found' };
    }

    if (auction.status !== 'ended') {
      await client.query('ROLLBACK');
      return { error: 'Auction must be ended before settling' };
    }

    // Mark winning bid
    await client.query(
      `UPDATE auction_bids SET status = 'won'
       WHERE auction_id = $1 AND bidder_id = $2 AND status = 'active'`,
      [auctionId, auction.current_bidder]
    );

    // Calculate final fee
    const finalBid = parseFloat(auction.current_bid);
    const fee = calculateAuctionFee(finalBid);

    const { rows: updated } = await client.query(
      `UPDATE auctions SET status = 'settled', fee = $2, settled_at = NOW(), updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [auctionId, fee]
    );

    await insertAuditLog(client, auctionId, userId, 'settled', {
      final_bid: finalBid,
      fee,
      winner: auction.current_bidder
    });

    await client.query('COMMIT');
    return updated[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- End expired auctions (cron/check) ----------

/** Minimum interval between endExpiredAuctions runs (30 seconds) */
const END_EXPIRED_DEBOUNCE_MS = 30_000;
let lastEndExpiredRun = 0;

/**
 * End auctions that have passed their end time.
 * Call this periodically or on auction access.
 * Debounced to run at most once per 30 seconds.
 * @returns {Promise<number>} Number of auctions ended
 */
export async function endExpiredAuctions() {
  const now = Date.now();
  if (now - lastEndExpiredRun < END_EXPIRED_DEBOUNCE_MS) return 0;
  lastEndExpiredRun = now;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `UPDATE auctions SET
         status = 'ended',
         updated_at = NOW()
       WHERE status = 'active' AND ends_at <= NOW() AND deleted_at IS NULL
       RETURNING id, current_bid, current_bidder`
    );

    // Set fee and log each ended auction within the transaction
    for (const auction of rows) {
      const fee = auction.current_bid ? calculateAuctionFee(parseFloat(auction.current_bid)) : 0;
      await client.query(
        `UPDATE auctions SET fee = $2 WHERE id = $1`,
        [auction.id, fee]
      );
      await insertAuditLog(client, auction.id, null, 'ended', {
        final_bid: auction.current_bid ? parseFloat(auction.current_bid) : null,
        winner: auction.current_bidder,
        fee
      });
    }

    await client.query('COMMIT');
    return rows.length;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Admin: Freeze ----------

/**
 * Freeze an active auction (admin only).
 * @param {string} auctionId
 * @param {number} adminId
 * @param {string} reason
 * @returns {Promise<object|{error: string}>}
 */
export async function freezeAuction(auctionId, adminId, reason) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `UPDATE auctions SET
         status = 'frozen',
         frozen_at = NOW(),
         updated_at = NOW()
       WHERE id = $1 AND status = 'active' AND deleted_at IS NULL
       RETURNING *`,
      [auctionId]
    );
    if (!rows[0]) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found or not active' };
    }

    await insertAuditLog(client, auctionId, adminId, 'frozen', { reason });
    await client.query('COMMIT');
    return rows[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Unfreeze a frozen auction (admin only). Extends end time by frozen duration.
 * @param {string} auctionId
 * @param {number} adminId
 * @param {string} reason
 * @returns {Promise<object|{error: string}>}
 */
export async function unfreezeAuction(auctionId, adminId, reason) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND status = 'frozen' AND deleted_at IS NULL FOR UPDATE`,
      [auctionId]
    );
    const auction = rows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found or not frozen' };
    }

    // Calculate how long it was frozen
    const frozenAt = new Date(auction.frozen_at);
    const frozenDuration = Date.now() - frozenAt.getTime();
    const newEndsAt = new Date(new Date(auction.ends_at).getTime() + frozenDuration);

    const { rows: updated } = await client.query(
      `UPDATE auctions SET
         status = 'active',
         ends_at = $2,
         frozen_at = NULL,
         updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [auctionId, newEndsAt.toISOString()]
    );

    await insertAuditLog(client, auctionId, adminId, 'unfrozen', {
      reason,
      frozen_duration_ms: frozenDuration,
      new_ends_at: newEndsAt.toISOString()
    });

    await client.query('COMMIT');
    return updated[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Admin: Cancel ----------

/**
 * Force cancel an auction (admin only, any state).
 * @param {string} auctionId
 * @param {number} adminId
 * @param {string} reason
 * @returns {Promise<object|{error: string}>}
 */
export async function adminCancelAuction(auctionId, adminId, reason) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId]
    );
    const auction = rows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found' };
    }

    if (auction.status === 'settled' || auction.status === 'cancelled') {
      await client.query('ROLLBACK');
      return { error: `Auction is already ${auction.status}` };
    }

    // Mark all active bids as rolled back
    await client.query(
      `UPDATE auction_bids SET status = 'rolled_back'
       WHERE auction_id = $1 AND status IN ('active', 'outbid')`,
      [auctionId]
    );

    const { rows: updated } = await client.query(
      `UPDATE auctions SET
         status = 'cancelled',
         updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [auctionId]
    );

    await insertAuditLog(client, auctionId, adminId, 'cancelled_by_admin', {
      reason,
      previous_status: auction.status,
      bid_count: auction.bid_count,
      current_bid: auction.current_bid ? parseFloat(auction.current_bid) : null
    });

    await client.query('COMMIT');
    return updated[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ---------- Admin: Rollback ----------

/**
 * Rollback bids to a specific point in history (admin only).
 * @param {string} auctionId
 * @param {number} adminId
 * @param {string|null} targetBidId - Bid to rollback TO (keep this bid, remove later ones). Null = remove all bids.
 * @param {string} reason
 * @returns {Promise<object|{error: string}>}
 */
export async function rollbackBids(auctionId, adminId, targetBidId, reason) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    const { rows: auctionRows } = await client.query(
      `SELECT * FROM auctions WHERE id = $1 AND deleted_at IS NULL FOR UPDATE`,
      [auctionId]
    );
    const auction = auctionRows[0];
    if (!auction) {
      await client.query('ROLLBACK');
      return { error: 'Auction not found' };
    }

    if (auction.status === 'settled' || auction.status === 'cancelled') {
      await client.query('ROLLBACK');
      return { error: `Cannot rollback bids on a ${auction.status} auction` };
    }

    let newCurrentBid = null;
    let newCurrentBidder = null;
    let newBidCount = 0;
    let rolledBackIds = [];

    if (targetBidId) {
      // Rollback to a specific bid
      const { rows: targetRows } = await client.query(
        `SELECT * FROM auction_bids WHERE id = $1 AND auction_id = $2`,
        [targetBidId, auctionId]
      );
      const targetBid = targetRows[0];
      if (!targetBid) {
        await client.query('ROLLBACK');
        return { error: 'Target bid not found' };
      }

      // Mark all bids AFTER the target as rolled back
      const { rows: rolledBack } = await client.query(
        `UPDATE auction_bids SET status = 'rolled_back'
         WHERE auction_id = $1 AND created_at > $2 AND status != 'rolled_back'
         RETURNING id`,
        [auctionId, targetBid.created_at]
      );
      rolledBackIds = rolledBack.map(r => r.id);

      // Make the target bid active
      await client.query(
        `UPDATE auction_bids SET status = 'active' WHERE id = $1`,
        [targetBidId]
      );

      newCurrentBid = parseFloat(targetBid.amount);
      newCurrentBidder = targetBid.bidder_id;

      // Count remaining non-rolled-back bids
      const { rows: countRows } = await client.query(
        `SELECT COUNT(*) FROM auction_bids
         WHERE auction_id = $1 AND status != 'rolled_back'`,
        [auctionId]
      );
      newBidCount = parseInt(countRows[0].count, 10);
    } else {
      // Remove ALL bids
      const { rows: rolledBack } = await client.query(
        `UPDATE auction_bids SET status = 'rolled_back'
         WHERE auction_id = $1 AND status != 'rolled_back'
         RETURNING id`,
        [auctionId]
      );
      rolledBackIds = rolledBack.map(r => r.id);
    }

    // Update auction state
    const { rows: updated } = await client.query(
      `UPDATE auctions SET
         current_bid = $2,
         current_bidder = $3,
         bid_count = $4,
         updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [auctionId, newCurrentBid, newCurrentBidder, newBidCount]
    );

    await insertAuditLog(client, auctionId, adminId, 'bid_rolled_back', {
      reason,
      target_bid_id: targetBidId,
      rolled_back_bid_ids: rolledBackIds,
      new_current_bid: newCurrentBid,
      new_bid_count: newBidCount
    });

    await client.query('COMMIT');
    return updated[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
