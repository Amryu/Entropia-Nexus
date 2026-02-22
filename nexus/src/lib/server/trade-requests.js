//@ts-nocheck
import { pool } from './db.js';

import { isPercentMarkupType, isLimitedByName, isStackableType, CONDITION_TYPES } from '$lib/common/itemTypes.js';
import { resolveItemDataByItemId } from '$lib/server/item-type-cache.js';

function getMarkupType(typeInfo, itemName) {
  if (typeInfo && typeof typeInfo === 'object') {
    return isPercentMarkupType(typeInfo.type, itemName, typeInfo.subType) ? 'percent' : 'absolute';
  }
  return isPercentMarkupType(typeInfo, itemName) ? 'percent' : 'absolute';
}

/**
 * Compute per-unit TT value for a trade request item.
 * Mirrors orderUtils.ts getUnitTT() / getMaxTT() logic.
 */
function computeUnitTT(itemData, itemName, offer) {
  if (!itemData) return null;
  const { type, item } = itemData;
  if (!type) return null;

  const isLimited = isLimitedByName(itemName);
  const isBP = type === 'Blueprint';

  // (L) blueprints: always 0.01 PED per unit (DB stores 1.00 for all BPs)
  if (isBP && isLimited) return 0.01;

  // Non-L blueprints: TT = QR/100
  if (isBP) {
    const qr = Number(offer?.details?.QualityRating) || 0;
    return qr > 0 ? qr / 100 : null;
  }

  // Condition items (non-stackable): prefer CurrentTT from offer details
  if (!isStackableType(type, itemName) && CONDITION_TYPES.has(type)) {
    const ct = Number(offer?.details?.CurrentTT);
    if (!isNaN(ct) && ct > 0) return ct;
  }

  // Default: MaxTT from item database
  const maxTT = item?.Properties?.Economy?.MaxTT
    ?? item?.Properties?.Economy?.Value
    ?? item?.MaxTT ?? item?.Value ?? null;
  if (maxTT != null) return Number(maxTT);

  // Pets: NutrioCapacity fallback
  if (type === 'Pet') {
    const nutrio = item?.Properties?.NutrioCapacity;
    return nutrio != null ? nutrio / 100 : null;
  }

  return null;
}

// ---------- Trade Requests ----------

/**
 * Create a new trade request with items, or add items to an existing open request.
 * Respects the unique constraint: only 1 open request between any 2 users.
 */
export async function getOrCreateTradeRequest(requesterId, targetId, planet, items, fetch) {
  // Pass IDs as strings — Number() loses precision for bigint Discord snowflakes
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Check for existing open request between these two users (direction-independent)
    const existingRes = await client.query(
      `SELECT id, status, discord_thread_id
       FROM trade_requests
       WHERE LEAST(requester_id, target_id) = LEAST($1::bigint, $2::bigint)
         AND GREATEST(requester_id, target_id) = GREATEST($1::bigint, $2::bigint)
         AND status IN ('pending', 'active')
       FOR UPDATE`,
      [requesterId, targetId]
    );

    let requestId;
    let isNew = false;

    if (existingRes.rows.length > 0) {
      // Add to existing request
      requestId = existingRes.rows[0].id;
      await client.query(
        `UPDATE trade_requests SET last_activity_at = NOW() WHERE id = $1`,
        [requestId]
      );
    } else {
      // Create new request
      const insertRes = await client.query(
        `INSERT INTO trade_requests (requester_id, target_id, planet)
         VALUES ($1, $2, $3)
         RETURNING id`,
        [requesterId, targetId, planet]
      );
      requestId = insertRes.rows[0].id;
      isNew = true;
    }

    // Validate quantities against offer min_quantity for items referencing an offer
    const offerIds = items.map(i => i.offer_id).filter(Boolean);
    const offerMap = {};
    if (offerIds.length > 0) {
      const offerRes = await client.query(
        `SELECT id, min_quantity, quantity, details FROM trade_offers WHERE id = ANY($1)`,
        [offerIds]
      );
      for (const row of offerRes.rows) offerMap[row.id] = row;
    }
    for (const item of items) {
      if (!item.offer_id) continue;
      const offer = offerMap[item.offer_id];
      if (!offer) continue;
      const qty = item.quantity || 1;
      const minQty = offer.min_quantity || 1;
      if (qty < minQty) {
        throw Object.assign(
          new Error(`Quantity ${qty} is below the offer minimum of ${minQty}`),
          { status: 400 }
        );
      }
      if (qty > offer.quantity) {
        throw Object.assign(
          new Error(`Quantity ${qty} exceeds the offer's available quantity of ${offer.quantity}`),
          { status: 400 }
        );
      }
    }

    // Resolve item data for markup formatting and TT computation
    const itemIds = [...new Set(items.map(i => i.item_id).filter(Boolean))];
    const dataMap = await resolveItemDataByItemId(itemIds, fetch);

    // Insert all items
    for (const item of items) {
      const itemData = dataMap[item.item_id];
      const markupType = getMarkupType(itemData, item.item_name);
      const offer = item.offer_id ? offerMap[item.offer_id] : null;
      const unitTT = computeUnitTT(itemData, item.item_name, offer);
      await client.query(
        `INSERT INTO trade_request_items (trade_request_id, offer_id, item_id, item_name, quantity, markup, side, markup_type, unit_tt)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
        [requestId, item.offer_id || null, item.item_id, item.item_name, item.quantity || 1, item.markup ?? null, item.side, markupType, unitTT]
      );
    }

    await client.query('COMMIT');
    return { id: requestId, isNew };
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

/**
 * Get all trade requests for a user (as requester or target), with item counts.
 */
export async function getUserTradeRequests(userId) {
  const query = `
    SELECT
      tr.id, tr.requester_id, tr.target_id, tr.status, tr.planet,
      tr.discord_thread_id, tr.last_activity_at, tr.created_at, tr.closed_at,
      COUNT(tri.id)::int AS item_count,
      CASE
        WHEN tr.requester_id = $1::bigint THEN tu.eu_name
        ELSE ru.eu_name
      END AS partner_name,
      CASE
        WHEN tr.requester_id = $1::bigint THEN tr.target_id
        ELSE tr.requester_id
      END AS partner_id
    FROM trade_requests tr
    LEFT JOIN trade_request_items tri ON tri.trade_request_id = tr.id
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.requester_id = $1::bigint OR tr.target_id = $1::bigint
    GROUP BY tr.id, ru.eu_name, tu.eu_name
    ORDER BY tr.created_at DESC
    LIMIT 50
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

/**
 * Get a single trade request with all its items.
 */
export async function getTradeRequest(requestId) {
  const reqQuery = `
    SELECT
      tr.*,
      ru.eu_name AS requester_name,
      tu.eu_name AS target_name
    FROM trade_requests tr
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.id = $1
  `;
  const { rows: reqRows } = await pool.query(reqQuery, [requestId]);
  if (reqRows.length === 0) return null;

  const itemsQuery = `
    SELECT * FROM trade_request_items
    WHERE trade_request_id = $1
    ORDER BY added_at ASC
  `;
  const { rows: itemRows } = await pool.query(itemsQuery, [requestId]);

  return { ...reqRows[0], items: itemRows };
}

/**
 * Cancel a trade request. Only the requester or target can cancel.
 */
export async function cancelTradeRequest(requestId, userId) {
  const query = `
    UPDATE trade_requests
    SET status = 'cancelled', closed_at = NOW()
    WHERE id = $1
      AND (requester_id = $2 OR target_id = $2)
      AND status IN ('pending', 'active')
    RETURNING id, status, discord_thread_id
  `;
  const { rows } = await pool.query(query, [requestId, userId]);
  return rows[0] || null;
}

/**
 * Update trade request status (used by bot).
 */
export async function updateTradeRequestStatus(requestId, status) {
  const closedAt = ['completed', 'cancelled', 'expired'].includes(status) ? 'NOW()' : 'NULL';
  const query = `
    UPDATE trade_requests
    SET status = $2, closed_at = ${closedAt}
    WHERE id = $1
    RETURNING id, status, discord_thread_id
  `;
  const { rows } = await pool.query(query, [requestId, status]);
  return rows[0] || null;
}

/**
 * Set Discord thread ID and activate request (used by bot after thread creation).
 */
export async function setTradeRequestThread(requestId, threadId) {
  const query = `
    UPDATE trade_requests
    SET discord_thread_id = $2, status = 'active', last_activity_at = NOW()
    WHERE id = $1
    RETURNING id
  `;
  const { rows } = await pool.query(query, [requestId, threadId]);
  return rows[0] || null;
}

/**
 * Update last_activity_at and reset warning (called when Discord message detected in thread).
 */
export async function updateLastActivity(requestId) {
  const query = `
    UPDATE trade_requests
    SET last_activity_at = NOW(), warning_sent = FALSE
    WHERE id = $1 AND status = 'active'
  `;
  await pool.query(query, [requestId]);
}

/**
 * Get pending trade requests waiting for bot to create threads.
 */
export async function getPendingTradeRequests() {
  const query = `
    SELECT
      tr.*,
      ru.eu_name AS requester_name, tr.requester_id AS requester_discord_id,
      tu.eu_name AS target_name, tr.target_id AS target_discord_id
    FROM trade_requests tr
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.status = 'pending'
    ORDER BY tr.created_at ASC
  `;
  const { rows } = await pool.query(query);
  return rows;
}

/**
 * Get items for a trade request (for bot announcements).
 */
export async function getTradeRequestItems(requestId) {
  const query = `
    SELECT * FROM trade_request_items
    WHERE trade_request_id = $1
    ORDER BY added_at ASC
  `;
  const { rows } = await pool.query(query, [requestId]);
  return rows;
}

/**
 * Get active trade requests that should receive an inactivity warning
 * (last_activity > 18h ago, warning not yet sent).
 */
export async function getWarnableTradeRequests() {
  const query = `
    SELECT tr.*, tr.discord_thread_id
    FROM trade_requests tr
    WHERE tr.status = 'active'
      AND tr.warning_sent = FALSE
      AND tr.last_activity_at < NOW() - INTERVAL '18 hours'
  `;
  const { rows } = await pool.query(query);
  return rows;
}

/**
 * Mark warning as sent for a trade request.
 */
export async function markWarningSent(requestId) {
  await pool.query(
    `UPDATE trade_requests SET warning_sent = TRUE WHERE id = $1`,
    [requestId]
  );
}

/**
 * Get active trade requests that should be expired
 * (last_activity > 24h ago).
 */
export async function getExpirableTradeRequests() {
  const query = `
    SELECT tr.*, tr.discord_thread_id
    FROM trade_requests tr
    WHERE tr.status = 'active'
      AND tr.last_activity_at < NOW() - INTERVAL '24 hours'
  `;
  const { rows } = await pool.query(query);
  return rows;
}

/**
 * Find a trade request by its Discord thread ID (for activity tracking).
 */
export async function findTradeRequestByThread(threadId) {
  const query = `
    SELECT id, status FROM trade_requests
    WHERE discord_thread_id = $1 AND status = 'active'
  `;
  const { rows } = await pool.query(query, [threadId]);
  return rows[0] || null;
}

