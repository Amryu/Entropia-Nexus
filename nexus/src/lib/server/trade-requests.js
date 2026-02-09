//@ts-nocheck
import { pool } from './db.js';

// ---------- Trade Requests ----------

/**
 * Create a new trade request with items, or add items to an existing open request.
 * Respects the unique constraint: only 1 open request between any 2 users.
 */
export async function getOrCreateTradeRequest(requesterId, targetId, planet, items) {
  const reqId = Number(requesterId);
  const tgtId = Number(targetId);
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
      [reqId, tgtId]
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
        [reqId, tgtId, planet]
      );
      requestId = insertRes.rows[0].id;
      isNew = true;
    }

    // Insert all items
    for (const item of items) {
      await client.query(
        `INSERT INTO trade_request_items (trade_request_id, offer_id, item_id, item_name, quantity, markup, side)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [requestId, item.offer_id || null, item.item_id, item.item_name, item.quantity || 1, item.markup ?? null, item.side]
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
  const uid = Number(userId);
  const query = `
    SELECT
      tr.id, tr.requester_id, tr.target_id, tr.status, tr.planet,
      tr.discord_thread_id, tr.last_activity_at, tr.created_at, tr.closed_at,
      COUNT(tri.id)::int AS item_count,
      CASE
        WHEN tr.requester_id = $1 THEN tu.eu_name
        ELSE ru.eu_name
      END AS partner_name,
      CASE
        WHEN tr.requester_id = $1 THEN tr.target_id
        ELSE tr.requester_id
      END AS partner_id
    FROM trade_requests tr
    LEFT JOIN trade_request_items tri ON tri.trade_request_id = tr.id
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.requester_id = $1 OR tr.target_id = $1
    GROUP BY tr.id, ru.eu_name, tu.eu_name
    ORDER BY tr.created_at DESC
    LIMIT 50
  `;
  const { rows } = await pool.query(query, [uid]);
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
  const { rows } = await pool.query(query, [requestId, Number(userId)]);
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
      ru.eu_name AS requester_name, ru.discord_id AS requester_discord_id,
      tu.eu_name AS target_name, tu.discord_id AS target_discord_id
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

/**
 * Get all active offers by a specific user (public endpoint).
 */
export async function getUserPublicOffers(userId) {
  const uid = Number(userId);
  const query = `
    SELECT
      o.id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.bumped_at,
      CASE
        WHEN o.state = 'closed' THEN 'closed'
        WHEN o.bumped_at < NOW() - INTERVAL '30 days' THEN 'terminated'
        WHEN o.bumped_at < NOW() - INTERVAL '7 days' THEN 'expired'
        WHEN o.bumped_at < NOW() - INTERVAL '3 days' THEN 'stale'
        ELSE 'active'
      END AS computed_state,
      u.eu_name AS seller_name
    FROM trade_offers o
    LEFT JOIN users u ON u.id = o.user_id
    WHERE o.user_id = $1
      AND o.state != 'closed'
      AND o.bumped_at >= NOW() - INTERVAL '30 days'
    ORDER BY o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [uid]);
  return rows;
}
