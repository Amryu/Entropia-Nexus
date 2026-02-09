//@ts-nocheck
import { pool } from './db.js';

// Staleness thresholds (days)
const STALE_DAYS = 3;
const EXPIRED_DAYS = 7;
const TERMINATED_DAYS = 30;
const MAX_OFFERS_PER_SIDE = 50;

/**
 * SQL fragment that computes the effective state from bumped_at.
 * The DB `state` column stores 'closed' explicitly; all other states are derived on read.
 */
const COMPUTED_STATE_SQL = `
  CASE
    WHEN state = 'closed' THEN 'closed'
    WHEN bumped_at < NOW() - INTERVAL '${TERMINATED_DAYS} days' THEN 'terminated'
    WHEN bumped_at < NOW() - INTERVAL '${EXPIRED_DAYS} days' THEN 'expired'
    WHEN bumped_at < NOW() - INTERVAL '${STALE_DAYS} days' THEN 'stale'
    ELSE 'active'
  END
`;

// ---------- Offers ----------

/**
 * Get order book for an item (buy + sell offers visible to everyone).
 * Only returns non-closed, non-terminated offers.
 */
export async function getOrderBook(itemId) {
  const query = `
    SELECT
      o.id, o.user_id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.created, o.updated, o.bumped_at,
      ${COMPUTED_STATE_SQL} AS computed_state,
      u.eu_name AS seller_name
    FROM trade_offers o
    LEFT JOIN users u ON u.id = o.user_id
    WHERE o.item_id = $1
      AND o.state != 'closed'
      AND o.bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    ORDER BY o.type, o.markup ASC, o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [itemId]);
  return rows;
}

/**
 * Get all offers for a user (My Offers view).
 */
export async function getUserOffers(userId) {
  const query = `
    SELECT
      o.id, o.user_id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.created, o.updated, o.bumped_at,
      o.state,
      ${COMPUTED_STATE_SQL} AS computed_state
    FROM trade_offers o
    WHERE o.user_id = $1
      AND o.state != 'closed'
    ORDER BY o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

/**
 * Count a user's active (non-closed, non-terminated) offers on a given side.
 */
export async function countUserOffersBySide(userId, type) {
  const query = `
    SELECT COUNT(*) AS count
    FROM trade_offers
    WHERE user_id = $1
      AND type = $2
      AND state NOT IN ('closed')
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
  `;
  const { rows } = await pool.query(query, [userId, type]);
  return parseInt(rows[0].count, 10);
}

/**
 * Create a new offer.
 */
export async function createOffer({ userId, type, itemId, quantity, minQuantity, markup, planet, details }) {
  const query = `
    INSERT INTO trade_offers (user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW(), NOW(), 'active')
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [
    userId, type, itemId, quantity, minQuantity ?? null, markup, planet, details ? JSON.stringify(details) : null
  ]);
  return rows[0];
}

/**
 * Get a single offer by ID.
 */
export async function getOfferById(offerId) {
  const query = `
    SELECT
      id, user_id, type, item_id, quantity, min_quantity,
      markup, planet, details, created, updated, bumped_at, state,
      ${COMPUTED_STATE_SQL} AS computed_state
    FROM trade_offers
    WHERE id = $1
  `;
  const { rows } = await pool.query(query, [offerId]);
  return rows[0] || null;
}

/**
 * Update an existing offer (edit). Resets bumped_at.
 */
export async function updateOffer(offerId, { quantity, minQuantity, markup, planet, details }) {
  const query = `
    UPDATE trade_offers
    SET quantity = $2, min_quantity = $3, markup = $4, planet = $5, details = $6,
        updated = NOW(), bumped_at = NOW(), state = 'active'
    WHERE id = $1
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [
    offerId, quantity, minQuantity ?? null, markup, planet, details ? JSON.stringify(details) : null
  ]);
  return rows[0] || null;
}

/**
 * Close an offer (soft delete).
 */
export async function closeOffer(offerId) {
  const query = `
    UPDATE trade_offers
    SET state = 'closed', updated = NOW()
    WHERE id = $1
    RETURNING id
  `;
  const { rows } = await pool.query(query, [offerId]);
  return rows[0] || null;
}

/**
 * Bump an offer (reset bumped_at to now).
 */
export async function bumpOffer(offerId) {
  const query = `
    UPDATE trade_offers
    SET bumped_at = NOW(), updated = NOW(), state = 'active'
    WHERE id = $1
      AND state != 'closed'
    RETURNING id, bumped_at, state
  `;
  const { rows } = await pool.query(query, [offerId]);
  return rows[0] || null;
}

// ---------- Exchange Prices ----------

/**
 * Get exchange-derived price data for an item from active offers.
 */
export async function getExchangePrices(itemId) {
  const query = `
    SELECT
      type,
      COUNT(*) AS offer_count,
      MIN(markup) AS best_markup,
      MAX(markup) AS worst_markup,
      SUM(quantity) AS total_volume
    FROM trade_offers
    WHERE item_id = $1
      AND state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${EXPIRED_DAYS} days'
    GROUP BY type
  `;
  const { rows } = await pool.query(query, [itemId]);
  const result = { buy: null, sell: null };
  for (const row of rows) {
    const side = row.type === 'BUY' ? 'buy' : 'sell';
    result[side] = {
      offer_count: parseInt(row.offer_count, 10),
      best_markup: parseFloat(row.best_markup),
      worst_markup: parseFloat(row.worst_markup),
      total_volume: parseInt(row.total_volume, 10)
    };
  }
  return result;
}

/**
 * Get offer counts per item for all active (non-closed, non-terminated) offers.
 * Returns a Map of itemId -> { buys, sells }.
 */
export async function getAllOfferCounts() {
  const query = `
    SELECT item_id, type, COUNT(*) AS cnt
    FROM trade_offers
    WHERE state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    GROUP BY item_id, type
  `;
  const { rows } = await pool.query(query);
  const counts = new Map();
  for (const row of rows) {
    const id = row.item_id;
    if (!counts.has(id)) counts.set(id, { buys: 0, sells: 0 });
    const entry = counts.get(id);
    if (row.type === 'BUY') entry.buys = parseInt(row.cnt, 10);
    else entry.sells = parseInt(row.cnt, 10);
  }
  return counts;
}

const PLANETS = [
  'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia',
  'Next Island', 'Monria', 'Toulan', 'Other',
];

export { MAX_OFFERS_PER_SIDE, PLANETS };
