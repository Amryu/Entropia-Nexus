// @ts-nocheck
import crypto from 'crypto';
import { pool, startTransaction } from './db.js';
import { resolveUserGrants } from './grants.js';

// --- Constants ---

const GLOBAL_CONFIRM_THRESHOLD = 5;
const TIMESTAMP_WINDOW_MS = 60_000; // ±60 seconds for matching
const TRADE_SLOT_WINDOW_MS = 10_000; // ±10 seconds for trade slot conflicts
const VALID_GLOBAL_TYPES = new Set(['kill', 'team_kill', 'deposit', 'craft', 'rare_item']);
const MAX_BATCH_SIZE = 500;
const MAX_EVENT_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

// --- Content Hashing ---

/**
 * Compute a deterministic SHA-256 hash for a global event.
 * Uses pipe-delimited canonical fields (type, player, target, value, unit, location, hof, ath).
 */
export function computeGlobalContentHash(event) {
  const parts = [
    event.type,
    event.player,
    event.target,
    String(event.value),
    event.unit || 'PED',
    event.location || '',
    event.hof ? '1' : '0',
    event.ath ? '1' : '0',
  ];
  return crypto.createHash('sha256').update(parts.join('|')).digest('hex');
}

/**
 * Compute a deterministic SHA-256 hash for a trade message.
 * Uses pipe-delimited canonical fields (channel, username, message).
 */
export function computeTradeContentHash(msg) {
  const parts = [
    msg.channel,
    msg.username,
    msg.message,
  ];
  return crypto.createHash('sha256').update(parts.join('|')).digest('hex');
}

// --- Confirmation Weight ---

/**
 * Determine the confirmation weight for a user based on their grants.
 * Admin = 5, trusted = 3, normal = 1.
 * Queries the full grant set (not OAuth-filtered) from the database.
 */
export async function getSubmissionWeight(userId) {
  const grants = await resolveUserGrants(userId);
  if (grants.has('admin.panel')) return 5;
  if (grants.has('ingestion.trusted')) return 3;
  return 1;
}

// --- Ban Check ---

/**
 * Check if a user is banned from ingestion.
 * @param {bigint|string} userId
 * @returns {Promise<boolean>}
 */
export async function isIngestionBanned(userId) {
  const { rows } = await pool.query(
    'SELECT 1 FROM ingestion_bans WHERE user_id = $1 LIMIT 1',
    [userId]
  );
  return rows.length > 0;
}

// --- Allowlist Check ---

/**
 * Check if an OAuth client application is allowed to submit ingestion data.
 * Non-OAuth requests (e.g. cookie-based admin sessions) are always allowed.
 * @param {string|null} oauthClientId - The OAuth client_id from the request, or null for non-OAuth requests
 * @returns {Promise<boolean>}
 */
export async function isIngestionAllowed(oauthClientId) {
  if (!oauthClientId) return true; // Non-OAuth (admin web session)
  const { rows } = await pool.query(
    'SELECT 1 FROM ingestion_allowed_clients WHERE client_id = $1 LIMIT 1',
    [oauthClientId]
  );
  return rows.length > 0;
}

// --- Validation ---

/**
 * Validate a single global event object from a client submission.
 * Returns null if valid, or an error string if invalid.
 */
export function validateGlobalEvent(event) {
  if (!event || typeof event !== 'object') return 'Invalid event object';
  if (!event.timestamp) return 'Missing timestamp';
  if (!event.type || !VALID_GLOBAL_TYPES.has(event.type)) return `Invalid type: ${event.type}`;
  if (!event.player || typeof event.player !== 'string') return 'Missing player';
  if (!event.target || typeof event.target !== 'string') return 'Missing target';
  if (typeof event.value !== 'number' || event.value <= 0) return 'Invalid value';
  if (event.unit && event.unit !== 'PED' && event.unit !== 'PEC') return 'Invalid unit';

  const ts = new Date(event.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  const age = Date.now() - ts.getTime();
  if (age > MAX_EVENT_AGE_MS) return 'Timestamp too old (>24h)';
  if (age < -TIMESTAMP_WINDOW_MS) return 'Timestamp in the future';

  return null;
}

/**
 * Validate a single trade message object from a client submission.
 */
export function validateTradeMessage(msg) {
  if (!msg || typeof msg !== 'object') return 'Invalid message object';
  if (!msg.timestamp) return 'Missing timestamp';
  if (!msg.channel || typeof msg.channel !== 'string') return 'Missing channel';
  if (!msg.username || typeof msg.username !== 'string') return 'Missing username';
  if (!msg.message || typeof msg.message !== 'string') return 'Missing message';

  const ts = new Date(msg.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  const age = Date.now() - ts.getTime();
  if (age > MAX_EVENT_AGE_MS) return 'Timestamp too old (>24h)';
  if (age < -TIMESTAMP_WINDOW_MS) return 'Timestamp in the future';

  return null;
}

// --- Global Ingestion ---

/**
 * Process a batch of global events from a single user.
 * Deduplicates by content hash within a ±60s window,
 * detects slot conflicts, and tracks confirmations.
 *
 * @param {bigint|string} userId
 * @param {object[]} events - Array of global event objects
 * @returns {Promise<{ accepted: number, duplicates: number, conflicts: number }>}
 */
export async function ingestGlobals(userId, events) {
  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0, conflicts = 0;

  for (const event of events) {
    const contentHash = computeGlobalContentHash(event);
    const eventTs = new Date(event.timestamp);
    const windowLo = new Date(eventTs.getTime() - TIMESTAMP_WINDOW_MS);
    const windowHi = new Date(eventTs.getTime() + TIMESTAMP_WINDOW_MS);

    // 1. Look for exact content match within time window
    const { rows: exactMatches } = await pool.query(
      `SELECT id, confirmation_count, confirmed FROM ingested_globals
       WHERE content_hash = $1
         AND event_timestamp BETWEEN $2 AND $3
       LIMIT 1`,
      [contentHash, windowLo.toISOString(), windowHi.toISOString()]
    );

    if (exactMatches.length > 0) {
      const existing = exactMatches[0];

      // Try to add submission (unique constraint will catch duplicates)
      try {
        await pool.query(
          `INSERT INTO ingested_global_submissions (global_id, user_id, weight, event_timestamp)
           VALUES ($1, $2, $3, $4)`,
          [existing.id, userId, weight, eventTs.toISOString()]
        );

        // Update confirmation count
        const newCount = existing.confirmation_count + weight;
        const wasConfirmed = existing.confirmed;
        const nowConfirmed = newCount >= GLOBAL_CONFIRM_THRESHOLD;

        await pool.query(
          `UPDATE ingested_globals
           SET confirmation_count = $1,
               confirmed = $2,
               confirmed_at = CASE WHEN $2 AND NOT $3 THEN now() ELSE confirmed_at END
           WHERE id = $4`,
          [newCount, nowConfirmed, wasConfirmed, existing.id]
        );

        accepted++;
      } catch (e) {
        if (e.code === '23505') { // unique_violation
          duplicates++;
        } else {
          throw e;
        }
      }
      continue;
    }

    // 2. Check for slot conflict (same type + player within window, different hash)
    const { rows: slotMatches } = await pool.query(
      `SELECT id, content_hash FROM ingested_globals
       WHERE global_type = $1
         AND player_name = $2
         AND event_timestamp BETWEEN $3 AND $4
       LIMIT 1`,
      [event.type, event.player, windowLo.toISOString(), windowHi.toISOString()]
    );

    if (slotMatches.length > 0) {
      // Conflict: same slot but different content
      const existing = slotMatches[0];
      await pool.query(
        `INSERT INTO ingestion_conflicts (type, existing_id, existing_hash, conflicting_hash, conflicting_data, user_id)
         VALUES ('global', $1, $2, $3, $4, $5)`,
        [existing.id, existing.content_hash, contentHash, JSON.stringify(event), userId]
      );
      conflicts++;
      continue;
    }

    // 3. New event — insert canonical entry + first submission
    const confirmed = weight >= GLOBAL_CONFIRM_THRESHOLD;
    const { rows: inserted } = await pool.query(
      `INSERT INTO ingested_globals
         (content_hash, global_type, player_name, target_name, value, value_unit,
          location, is_hof, is_ath, event_timestamp, confirmation_count, confirmed, confirmed_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, CASE WHEN $12 THEN now() ELSE NULL END)
       RETURNING id`,
      [
        contentHash, event.type, event.player, event.target,
        event.value, event.unit || 'PED', event.location || null,
        event.hof || false, event.ath || false,
        eventTs.toISOString(), weight, confirmed,
      ]
    );

    await pool.query(
      `INSERT INTO ingested_global_submissions (global_id, user_id, weight, event_timestamp)
       VALUES ($1, $2, $3, $4)`,
      [inserted[0].id, userId, weight, eventTs.toISOString()]
    );

    accepted++;
  }

  return { accepted, duplicates, conflicts };
}

// --- Trade Message Ingestion ---

/**
 * Process a batch of trade messages from a single user.
 * Similar to globals but with no confirmation threshold.
 */
export async function ingestTrades(userId, messages) {
  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0, conflicts = 0;

  for (const msg of messages) {
    const contentHash = computeTradeContentHash(msg);
    const eventTs = new Date(msg.timestamp);
    const windowLo = new Date(eventTs.getTime() - TIMESTAMP_WINDOW_MS);
    const windowHi = new Date(eventTs.getTime() + TIMESTAMP_WINDOW_MS);

    // 1. Exact content match within time window
    const { rows: exactMatches } = await pool.query(
      `SELECT id, confirmation_count FROM ingested_trade_messages
       WHERE content_hash = $1
         AND event_timestamp BETWEEN $2 AND $3
       LIMIT 1`,
      [contentHash, windowLo.toISOString(), windowHi.toISOString()]
    );

    if (exactMatches.length > 0) {
      const existing = exactMatches[0];

      try {
        await pool.query(
          `INSERT INTO ingested_trade_submissions (trade_message_id, user_id, weight, event_timestamp)
           VALUES ($1, $2, $3, $4)`,
          [existing.id, userId, weight, eventTs.toISOString()]
        );

        await pool.query(
          `UPDATE ingested_trade_messages SET confirmation_count = $1 WHERE id = $2`,
          [existing.confirmation_count + weight, existing.id]
        );

        accepted++;
      } catch (e) {
        if (e.code === '23505') {
          duplicates++;
        } else {
          throw e;
        }
      }
      continue;
    }

    // 2. Slot conflict (same channel + username within ±10s, different content)
    const slotWindowLo = new Date(eventTs.getTime() - TRADE_SLOT_WINDOW_MS);
    const slotWindowHi = new Date(eventTs.getTime() + TRADE_SLOT_WINDOW_MS);

    const { rows: slotMatches } = await pool.query(
      `SELECT id, content_hash FROM ingested_trade_messages
       WHERE channel = $1
         AND username = $2
         AND event_timestamp BETWEEN $3 AND $4
       LIMIT 1`,
      [msg.channel, msg.username, slotWindowLo.toISOString(), slotWindowHi.toISOString()]
    );

    if (slotMatches.length > 0) {
      const existing = slotMatches[0];
      await pool.query(
        `INSERT INTO ingestion_conflicts (type, existing_id, existing_hash, conflicting_hash, conflicting_data, user_id)
         VALUES ('trade', $1, $2, $3, $4, $5)`,
        [existing.id, existing.content_hash, contentHash, JSON.stringify(msg), userId]
      );
      conflicts++;
      continue;
    }

    // 3. New trade message
    const { rows: inserted } = await pool.query(
      `INSERT INTO ingested_trade_messages
         (content_hash, channel, username, message, event_timestamp, confirmation_count)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id`,
      [contentHash, msg.channel, msg.username, msg.message, eventTs.toISOString(), weight]
    );

    await pool.query(
      `INSERT INTO ingested_trade_submissions (trade_message_id, user_id, weight, event_timestamp)
       VALUES ($1, $2, $3, $4)`,
      [inserted[0].id, userId, weight, eventTs.toISOString()]
    );

    accepted++;
  }

  return { accepted, duplicates, conflicts };
}

// --- Distribution ---

/**
 * Fetch global events newer than `since` for distribution.
 * Returns all entries with a confirmed flag.
 */
export async function getGlobalsSince(since, limit = 200) {
  const { rows } = await pool.query(
    `SELECT id, global_type, player_name, target_name, value, value_unit,
            location, is_hof, is_ath, event_timestamp, confirmation_count, confirmed
     FROM ingested_globals
     WHERE first_seen_at > $1
     ORDER BY first_seen_at ASC
     LIMIT $2`,
    [since, Math.min(limit, 1000)]
  );
  return rows;
}

/**
 * Fetch trade messages newer than `since` for distribution.
 */
export async function getTradesSince(since, limit = 200) {
  const { rows } = await pool.query(
    `SELECT id, channel, username, message, event_timestamp, confirmation_count
     FROM ingested_trade_messages
     WHERE first_seen_at > $1
     ORDER BY first_seen_at ASC
     LIMIT $2`,
    [since, Math.min(limit, 1000)]
  );
  return rows;
}

// --- Admin: Stats ---

export async function getIngestionStats() {
  const { rows } = await pool.query(`
    SELECT
      (SELECT count(*) FROM ingested_globals) AS total_globals,
      (SELECT count(*) FROM ingested_globals WHERE confirmed) AS confirmed_globals,
      (SELECT count(*) FROM ingested_trade_messages) AS total_trades,
      (SELECT count(DISTINCT user_id) FROM ingested_global_submissions) +
        (SELECT count(DISTINCT user_id) FROM ingested_trade_submissions) AS active_contributors,
      (SELECT count(*) FROM ingestion_bans) AS active_bans,
      (SELECT count(*) FROM ingestion_alerts WHERE NOT resolved) AS pending_alerts,
      (SELECT count(*) FROM ingestion_conflicts) AS total_conflicts,
      (SELECT count(*) FROM ingestion_allowed_clients) AS allowed_clients
  `);
  return rows[0];
}

// --- Admin: Alerts ---

export async function getAlerts(page = 1, limit = 20) {
  const offset = (page - 1) * limit;
  const { rows } = await pool.query(
    `SELECT a.*, array_agg(u.username) AS user_names
     FROM ingestion_alerts a
     LEFT JOIN ONLY users u ON u.id = ANY(a.user_ids)
     WHERE NOT a.resolved
     GROUP BY a.id
     ORDER BY a.created_at DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  );
  const { rows: countRows } = await pool.query(
    'SELECT count(*) AS total FROM ingestion_alerts WHERE NOT resolved'
  );
  return { rows, total: parseInt(countRows[0].total) };
}

export async function resolveAlert(alertId, resolvedBy, notes) {
  await pool.query(
    `UPDATE ingestion_alerts
     SET resolved = true, resolved_at = now(), resolved_by = $1, resolution_notes = $2
     WHERE id = $3`,
    [resolvedBy, notes || null, alertId]
  );
}

// --- Admin: Per-user Stats ---

export async function getIngestionUsers(page = 1, limit = 50) {
  const offset = (page - 1) * limit;
  const { rows } = await pool.query(
    `WITH user_stats AS (
       SELECT user_id,
              count(*) AS submission_count,
              sum(weight) AS total_weight
       FROM (
         SELECT user_id, weight FROM ingested_global_submissions
         UNION ALL
         SELECT user_id, weight FROM ingested_trade_submissions
       ) all_subs
       GROUP BY user_id
     ),
     conflict_stats AS (
       SELECT user_id, count(*) AS conflict_count
       FROM ingestion_conflicts
       GROUP BY user_id
     )
     SELECT us.user_id, u.username, us.submission_count, us.total_weight,
            COALESCE(cs.conflict_count, 0) AS conflict_count,
            CASE WHEN ib.id IS NOT NULL THEN true ELSE false END AS banned
     FROM user_stats us
     JOIN ONLY users u ON u.id = us.user_id
     LEFT JOIN conflict_stats cs ON cs.user_id = us.user_id
     LEFT JOIN ingestion_bans ib ON ib.user_id = us.user_id
     ORDER BY us.submission_count DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  );
  return rows;
}

export async function getUserSubmissions(userId, type, page = 1, limit = 50) {
  const offset = (page - 1) * limit;

  if (type === 'global') {
    const { rows } = await pool.query(
      `SELECT gs.*, ig.global_type, ig.player_name, ig.target_name, ig.value,
              ig.value_unit, ig.location, ig.is_hof, ig.is_ath, ig.event_timestamp AS global_timestamp
       FROM ingested_global_submissions gs
       JOIN ingested_globals ig ON ig.id = gs.global_id
       WHERE gs.user_id = $1
       ORDER BY gs.submitted_at DESC
       LIMIT $2 OFFSET $3`,
      [userId, limit, offset]
    );
    return rows;
  }

  const { rows } = await pool.query(
    `SELECT ts.*, tm.channel, tm.username, tm.message, tm.event_timestamp AS trade_timestamp
     FROM ingested_trade_submissions ts
     JOIN ingested_trade_messages tm ON tm.id = ts.trade_message_id
     WHERE ts.user_id = $1
     ORDER BY ts.submitted_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset]
  );
  return rows;
}

// --- Admin: Ban/Unban ---

export async function banUser(userId, reason, bannedBy) {
  await pool.query(
    `INSERT INTO ingestion_bans (user_id, reason, banned_by)
     VALUES ($1, $2, $3)
     ON CONFLICT (user_id) DO UPDATE SET reason = $2, banned_at = now(), banned_by = $3,
       data_purged = false, data_purged_at = NULL, data_purged_by = NULL`,
    [userId, reason, bannedBy]
  );
}

export async function unbanUser(userId) {
  await pool.query('DELETE FROM ingestion_bans WHERE user_id = $1', [userId]);
}

// --- Admin: Allowed Clients (OAuth Applications) ---

export async function getAllowedClients(page = 1, limit = 50) {
  const offset = (page - 1) * limit;
  const { rows } = await pool.query(
    `SELECT ac.id, ac.client_id, ac.allowed_at, ac.notes,
            oc.name AS client_name, oc.description AS client_description,
            oc.website_url, oc.is_confidential,
            ab.username AS allowed_by_name
     FROM ingestion_allowed_clients ac
     JOIN oauth_clients oc ON oc.id = ac.client_id
     JOIN ONLY users ab ON ab.id = ac.allowed_by
     ORDER BY ac.allowed_at DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  );
  const { rows: countRows } = await pool.query(
    'SELECT count(*) AS total FROM ingestion_allowed_clients'
  );
  return { rows, total: parseInt(countRows[0].total) };
}

export async function addAllowedClient(clientId, allowedBy, notes = null) {
  const { rows } = await pool.query(
    `INSERT INTO ingestion_allowed_clients (client_id, allowed_by, notes)
     VALUES ($1, $2, $3)
     ON CONFLICT (client_id) DO NOTHING
     RETURNING id`,
    [clientId, allowedBy, notes]
  );
  return rows.length > 0;
}

export async function removeAllowedClient(clientId) {
  const { rowCount } = await pool.query(
    'DELETE FROM ingestion_allowed_clients WHERE client_id = $1',
    [clientId]
  );
  return rowCount > 0;
}

// --- Admin: Purge ---

/**
 * Retroactively remove all ingested data from a user.
 * Recalculates confirmation counts and un-confirms entries that fall below threshold.
 * Deletes entries with 0 remaining submissions.
 */
export async function purgeUserData(userId, purgedBy) {
  const client = await startTransaction();

  try {
    // 1. Collect affected global IDs
    const { rows: globalSubs } = await client.query(
      'SELECT DISTINCT global_id FROM ingested_global_submissions WHERE user_id = $1',
      [userId]
    );
    const globalIds = globalSubs.map(r => r.global_id);

    // 2. Delete global submissions
    await client.query(
      'DELETE FROM ingested_global_submissions WHERE user_id = $1',
      [userId]
    );

    // 3. Recalculate confirmation counts for affected globals
    if (globalIds.length > 0) {
      // Update counts from remaining submissions
      await client.query(
        `UPDATE ingested_globals ig
         SET confirmation_count = COALESCE(sub.total_weight, 0),
             confirmed = COALESCE(sub.total_weight, 0) >= $2,
             confirmed_at = CASE
               WHEN COALESCE(sub.total_weight, 0) >= $2 THEN ig.confirmed_at
               ELSE NULL
             END
         FROM (
           SELECT global_id, sum(weight) AS total_weight
           FROM ingested_global_submissions
           WHERE global_id = ANY($1)
           GROUP BY global_id
         ) sub
         WHERE ig.id = sub.global_id`,
        [globalIds, GLOBAL_CONFIRM_THRESHOLD]
      );

      // Delete globals with 0 remaining submissions
      await client.query(
        `DELETE FROM ingested_globals
         WHERE id = ANY($1)
           AND NOT EXISTS (
             SELECT 1 FROM ingested_global_submissions WHERE global_id = ingested_globals.id
           )`,
        [globalIds]
      );
    }

    // 4. Same for trades
    const { rows: tradeSubs } = await client.query(
      'SELECT DISTINCT trade_message_id FROM ingested_trade_submissions WHERE user_id = $1',
      [userId]
    );
    const tradeIds = tradeSubs.map(r => r.trade_message_id);

    await client.query(
      'DELETE FROM ingested_trade_submissions WHERE user_id = $1',
      [userId]
    );

    if (tradeIds.length > 0) {
      await client.query(
        `UPDATE ingested_trade_messages tm
         SET confirmation_count = COALESCE(sub.total_weight, 0)
         FROM (
           SELECT trade_message_id, sum(weight) AS total_weight
           FROM ingested_trade_submissions
           WHERE trade_message_id = ANY($1)
           GROUP BY trade_message_id
         ) sub
         WHERE tm.id = sub.trade_message_id`,
        [tradeIds]
      );

      // Delete trades with 0 remaining submissions
      await client.query(
        `DELETE FROM ingested_trade_messages
         WHERE id = ANY($1)
           AND NOT EXISTS (
             SELECT 1 FROM ingested_trade_submissions WHERE trade_message_id = ingested_trade_messages.id
           )`,
        [tradeIds]
      );
    }

    // 5. Delete conflicts by this user
    await client.query(
      'DELETE FROM ingestion_conflicts WHERE user_id = $1',
      [userId]
    );

    // 6. Update ban record with purge metadata
    await client.query(
      `UPDATE ingestion_bans
       SET data_purged = true, data_purged_at = now(), data_purged_by = $2
       WHERE user_id = $1`,
      [userId, purgedBy]
    );

    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }

  return { purgedGlobals: globalSubs?.length || 0, purgedTrades: tradeSubs?.length || 0 };
}

// --- Admin: Conflicts ---

export async function getConflicts(page = 1, limit = 50, userId = null) {
  const offset = (page - 1) * limit;
  const params = [limit, offset];
  let whereClause = '';

  if (userId) {
    whereClause = 'WHERE c.user_id = $3';
    params.push(userId);
  }

  const { rows } = await pool.query(
    `SELECT c.*, u.username AS user_name
     FROM ingestion_conflicts c
     JOIN ONLY users u ON u.id = c.user_id
     ${whereClause}
     ORDER BY c.created_at DESC
     LIMIT $1 OFFSET $2`,
    params
  );
  return rows;
}

// --- Background: Conflict Analysis ---

/**
 * Analyze conflict patterns and generate alerts for suspicious users.
 * Should be called periodically (e.g., every 15 minutes).
 *
 * Criteria for alerting:
 * - User has >= 10 conflicts in last 7 days
 * - User is in the minority (their version has fewer confirmations) >= 80% of the time
 * - User has conflicts with >= 3 different counterpart users
 * - No existing unresolved alert for this user
 */
export async function analyzeConflicts() {
  // Find users with significant conflict counts in the last 7 days
  const { rows: conflictUsers } = await pool.query(
    `SELECT user_id, count(*) AS conflict_count
     FROM ingestion_conflicts
     WHERE created_at > now() - interval '7 days'
     GROUP BY user_id
     HAVING count(*) >= 10`
  );

  for (const { user_id: userId, conflict_count: conflictCount } of conflictUsers) {
    // Check if there's already an unresolved alert for this user
    const { rows: existingAlerts } = await pool.query(
      `SELECT 1 FROM ingestion_alerts
       WHERE NOT resolved AND $1 = ANY(user_ids)
       LIMIT 1`,
      [userId]
    );
    if (existingAlerts.length > 0) continue;

    // Get this user's conflicts to analyze minority status
    const { rows: userConflicts } = await pool.query(
      `SELECT c.type, c.existing_id, c.existing_hash, c.conflicting_hash
       FROM ingestion_conflicts c
       WHERE c.user_id = $1 AND c.created_at > now() - interval '7 days'`,
      [userId]
    );

    let minorityCount = 0;
    const counterpartUsers = new Set();

    for (const conflict of userConflicts) {
      // For each conflict, check if the existing entry (what others agree on) has
      // more total confirmations than any entry matching the user's conflicting hash
      if (conflict.type === 'global') {
        const { rows: existing } = await pool.query(
          'SELECT confirmation_count FROM ingested_globals WHERE id = $1',
          [conflict.existing_id]
        );
        if (existing.length > 0 && existing[0].confirmation_count > 0) {
          minorityCount++;
        }

        // Find other users who confirmed the existing entry
        const { rows: otherSubs } = await pool.query(
          `SELECT DISTINCT user_id FROM ingested_global_submissions
           WHERE global_id = $1 AND user_id != $2`,
          [conflict.existing_id, userId]
        );
        for (const s of otherSubs) counterpartUsers.add(String(s.user_id));
      } else {
        const { rows: existing } = await pool.query(
          'SELECT confirmation_count FROM ingested_trade_messages WHERE id = $1',
          [conflict.existing_id]
        );
        if (existing.length > 0 && existing[0].confirmation_count > 0) {
          minorityCount++;
        }

        const { rows: otherSubs } = await pool.query(
          `SELECT DISTINCT user_id FROM ingested_trade_submissions
           WHERE trade_message_id = $1 AND user_id != $2`,
          [conflict.existing_id, userId]
        );
        for (const s of otherSubs) counterpartUsers.add(String(s.user_id));
      }
    }

    const minorityRate = minorityCount / userConflicts.length;

    // Alert conditions: high minority rate AND multiple counterpart users
    if (minorityRate >= 0.8 && counterpartUsers.size >= 3) {
      await pool.query(
        `INSERT INTO ingestion_alerts (type, user_ids, details)
         VALUES ('conflict_pattern', $1, $2)`,
        [
          [userId],
          JSON.stringify({
            conflict_count: parseInt(conflictCount),
            minority_rate: Math.round(minorityRate * 100),
            counterpart_count: counterpartUsers.size,
            period: '7 days',
          }),
        ]
      );
    }
  }
}

// --- Gzip Decompression ---

/**
 * Parse a potentially gzip-compressed request body as JSON.
 * Checks Content-Encoding header and decompresses if needed.
 */
export async function parseRequestBody(request) {
  const encoding = request.headers.get('content-encoding');

  if (encoding === 'gzip') {
    const { promisify } = await import('node:util');
    const { gunzip } = await import('node:zlib');
    const gunzipAsync = promisify(gunzip);

    const buffer = Buffer.from(await request.arrayBuffer());
    const decompressed = await gunzipAsync(buffer);
    return JSON.parse(decompressed.toString('utf-8'));
  }

  return await request.json();
}

// --- Exports for background job registration ---

export const CONFLICT_ANALYSIS_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes
