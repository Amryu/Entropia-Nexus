// @ts-nocheck
import crypto from 'crypto';
import { pool, startTransaction } from './db.js';
import { resolveUserGrants } from './grants.js';
import { resolveMob } from './mobResolver.js';

// --- Constants ---

const GLOBAL_CONFIRM_THRESHOLD = 5;
const TIMESTAMP_WINDOW_MS = 60_000; // ±60 seconds for matching (trades)
const GLOBAL_DEDUP_WINDOW_MS = 5 * 60 * 1000; // ±5 min for occurrence-based dedup (globals)
const TRADE_SLOT_WINDOW_MS = 10_000; // ±10 seconds for trade slot conflicts
const MAX_OCCURRENCE = 3;
const VALID_GLOBAL_TYPES = new Set(['kill', 'team_kill', 'deposit', 'craft', 'rare_item', 'discovery', 'tier']);
const VALUE_OPTIONAL_TYPES = new Set(['discovery', 'tier']);
const MAX_BATCH_SIZE = 500;
const MAX_EVENT_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours
const MAX_PLAYER_LENGTH = 200;
const MAX_TARGET_LENGTH = 300;
const MAX_LOCATION_LENGTH = 200;
const MAX_CHANNEL_LENGTH = 100;
const MAX_MESSAGE_LENGTH = 2000;
const MAX_COMPRESSED_SIZE = 1_048_576; // 1 MB compressed
const MAX_DECOMPRESSED_SIZE = 10_485_760; // 10 MB decompressed

// --- Fraud Detection Thresholds ---
const MIN_ACTIVE_CONTRIBUTORS = 10;         // Skip collusion/solo checks if fewer contributors
const MAJORITY_SWAP_MIN_USERS = 3;          // Minimum conflict users to trigger swap
const COLLUSION_MIN_EXCLUSIVE = 10;         // Minimum exclusive shared events
const COLLUSION_MIN_EXCLUSIVE_RATE = 0.7;   // 70% exclusive overlap threshold
const SOLO_MIN_SUBMISSIONS = 50;            // Minimum total submissions to evaluate
const SOLO_MIN_SOLO_COUNT = 5;              // Minimum solo events to alert
const SOLO_MAX_RATE = 0.3;                  // 30% solo rate threshold
const SOLO_AGE_HOURS = 24;                  // Hours to wait before counting as "solo"

// --- Repost Detection ---
const REPOST_WINDOW_MS = 15 * 60 * 1000;    // 15 minutes
const REPOST_MAX_DISTANCE_RATIO = 0.15;     // 15% character difference
const REPOST_MIN_DISTANCE = 5;              // At least 5 chars must differ

// --- Trade Keyword Filter ---
const TRADE_KEYWORDS = /\b(wts|wtb|wtt|sell|selling|buy|buying|trade|trading|price|pc|offer|obo|lf|looking\s+for)\b/i;
const ITEM_LINK_PATTERN = /\[[^\[\]]{2,}\]/; // [ItemName] — at least 2 chars inside brackets

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
    event.value != null ? String(event.value) : '',
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

// --- Data Sanitization ---

/** Strip event/message to only known fields before storing as conflict data. */
function sanitizeGlobalEvent(event) {
  return {
    type: event.type, player: event.player, target: event.target,
    value: event.value, unit: event.unit, location: event.location,
    hof: event.hof, ath: event.ath, timestamp: event.timestamp,
    occurrence: event.occurrence ?? 1,
  };
}

function sanitizeTradeMessage(msg) {
  return {
    channel: msg.channel, username: msg.username,
    message: msg.message, timestamp: msg.timestamp,
  };
}

// --- Confirmation Weight ---

/**
 * Determine the confirmation weight for a user based on their grants.
 * Admin = auto-confirm (always exceeds threshold), trusted = 3, normal = 1.
 * Queries the full grant set (not OAuth-filtered) from the database.
 */
export async function getSubmissionWeight(userId) {
  const grants = await resolveUserGrants(userId);
  if (grants.has('admin.panel')) return 1_000_000;
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

// --- Trade Channel Configuration ---

let _tradeChannelCache = null;
let _tradeChannelCacheTime = 0;
const TRADE_CHANNEL_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function loadTradeChannels() {
  const now = Date.now();
  if (_tradeChannelCache && now - _tradeChannelCacheTime < TRADE_CHANNEL_CACHE_TTL) {
    return _tradeChannelCache;
  }
  const { rows } = await pool.query('SELECT channel_name, planet FROM ingestion_trade_channels ORDER BY channel_name');
  _tradeChannelCache = new Map(rows.map(r => [r.channel_name.toLowerCase(), r.planet]));
  _tradeChannelCacheTime = now;
  return _tradeChannelCache;
}

/**
 * Check if a channel name is in the configured trade channel list.
 * Uses an in-memory cache refreshed every 5 minutes.
 */
export async function isKnownTradeChannel(channelName) {
  const channels = await loadTradeChannels();
  return channels.has(channelName.toLowerCase());
}

export async function getTradeChannels() {
  const { rows } = await pool.query(
    `SELECT tc.*, u.username AS added_by_name
     FROM ingestion_trade_channels tc
     JOIN ONLY users u ON u.id = tc.added_by
     ORDER BY tc.channel_name`,
  );
  return rows;
}

export async function addTradeChannel(channelName, planet, addedBy) {
  const { rows } = await pool.query(
    `INSERT INTO ingestion_trade_channels (channel_name, planet, added_by)
     VALUES ($1, $2, $3)
     ON CONFLICT (channel_name) DO NOTHING
     RETURNING id`,
    [channelName.toLowerCase(), planet || null, addedBy]
  );
  _tradeChannelCache = null; // invalidate cache
  return rows.length > 0;
}

export async function removeTradeChannel(channelName) {
  const { rowCount } = await pool.query(
    'DELETE FROM ingestion_trade_channels WHERE channel_name = $1',
    [channelName.toLowerCase()]
  );
  _tradeChannelCache = null; // invalidate cache
  return rowCount > 0;
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
  if (event.player.length > MAX_PLAYER_LENGTH) return 'Player name too long';
  if (!event.target || typeof event.target !== 'string') return 'Missing target';
  if (event.target.length > MAX_TARGET_LENGTH) return 'Target name too long';
  if (event.location != null && typeof event.location !== 'string') return 'Location must be a string';
  if (typeof event.location === 'string' && event.location.length > MAX_LOCATION_LENGTH) return 'Location too long';
  if (VALUE_OPTIONAL_TYPES.has(event.type)) {
    if (event.value != null && (typeof event.value !== 'number' || !Number.isFinite(event.value))) return 'Invalid value';
  } else {
    if (typeof event.value !== 'number' || !Number.isFinite(event.value) || event.value <= 0) return 'Invalid value';
  }
  if (event.unit && event.unit !== 'PED' && event.unit !== 'PEC' && event.unit !== 'TIER') return 'Invalid unit';
  if (event.hof != null && typeof event.hof !== 'boolean') return 'hof must be a boolean';
  if (event.ath != null && typeof event.ath !== 'boolean') return 'ath must be a boolean';
  if (event.occurrence != null) {
    if (!Number.isInteger(event.occurrence) || event.occurrence < 1 || event.occurrence > MAX_OCCURRENCE)
      return `Invalid occurrence: must be integer 1-${MAX_OCCURRENCE}`;
  }

  const ts = new Date(event.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  const age = Date.now() - ts.getTime();
  if (age > MAX_EVENT_AGE_MS) return 'Timestamp too old (>24h)';
  if (age < -TIMESTAMP_WINDOW_MS) return 'Timestamp in the future';

  return null;
}

/**
 * Validate a single trade message object from a client submission.
 * Async because channel validation uses an in-memory cache loaded on demand.
 */
export async function validateTradeMessage(msg) {
  if (!msg || typeof msg !== 'object') return 'Invalid message object';
  if (!msg.timestamp) return 'Missing timestamp';
  if (!msg.channel || typeof msg.channel !== 'string') return 'Missing channel';
  if (msg.channel.length > MAX_CHANNEL_LENGTH) return 'Channel name too long';
  if (!(await isKnownTradeChannel(msg.channel))) return 'Unknown trade channel';
  if (!msg.username || typeof msg.username !== 'string') return 'Missing username';
  if (msg.username.length > MAX_PLAYER_LENGTH) return 'Username too long';
  if (!msg.message || typeof msg.message !== 'string') return 'Missing message';
  if (msg.message.length > MAX_MESSAGE_LENGTH) return 'Message too long';
  if (!TRADE_KEYWORDS.test(msg.message) && !ITEM_LINK_PATTERN.test(msg.message)) {
    return 'Message does not contain trade keywords or item links';
  }

  const ts = new Date(msg.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  const age = Date.now() - ts.getTime();
  if (age > MAX_EVENT_AGE_MS) return 'Timestamp too old (>24h)';
  if (age < -TIMESTAMP_WINDOW_MS) return 'Timestamp in the future';

  return null;
}

// --- Levenshtein Distance (Bounded) ---

/**
 * Compute the Levenshtein edit distance between two strings, with early
 * termination when the distance exceeds maxDist. Returns maxDist + 1
 * if the strings are too dissimilar.
 */
function levenshteinBounded(a, b, maxDist) {
  const m = a.length, n = b.length;
  if (Math.abs(m - n) > maxDist) return maxDist + 1;
  if (m === 0) return n;
  if (n === 0) return m;

  let prev = Array.from({ length: n + 1 }, (_, i) => i);

  for (let i = 1; i <= m; i++) {
    const curr = [i];
    let rowMin = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
      if (curr[j] < rowMin) rowMin = curr[j];
    }
    if (rowMin > maxDist) return maxDist + 1;
    prev = curr;
  }

  return prev[n];
}

// --- Intra-batch Dedup ---

const SUSPICIOUS_REPEAT_THRESHOLD = 5;

/**
 * Check a batch for intra-batch duplicates. Rejects if any key appears
 * 5+ times. Returns deduplicated events (first of each key kept).
 *
 * @param {object[]} events
 * @param {function} hashFn - Content hash function
 * @param {function} [keyFn] - Optional custom key function (event, hash) => string.
 *   Defaults to hash + '|' + timestamp (used for trades).
 */
function checkBatchDuplicates(events, hashFn, keyFn) {
  const keyCounts = new Map();
  for (const event of events) {
    const hash = hashFn(event);
    const key = keyFn ? keyFn(event, hash) : hash + '|' + event.timestamp;
    keyCounts.set(key, (keyCounts.get(key) || 0) + 1);
  }

  const maxRepeats = keyCounts.size > 0 ? Math.max(...keyCounts.values()) : 0;
  if (maxRepeats >= SUSPICIOUS_REPEAT_THRESHOLD) {
    return { rejected: true, maxRepeats };
  }

  const seen = new Set();
  const deduped = events.filter(e => {
    const hash = hashFn(e);
    const key = keyFn ? keyFn(e, hash) : hash + '|' + e.timestamp;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return { rejected: false, deduped };
}

// --- Global Ingestion ---

/**
 * Process a batch of global events from a single user.
 * Deduplicates by content hash + occurrence within a ±5min window,
 * detects slot conflicts, and tracks confirmations.
 *
 * Uses per-event transactions with advisory locks to prevent concurrent
 * requests from creating duplicate canonical rows for the same event.
 *
 * @param {bigint|string} userId
 * @param {object[]} events - Array of global event objects
 * @returns {Promise<{ accepted: number, duplicates: number, conflicts: number, rejected?: boolean, reason?: string }>}
 */
export async function ingestGlobals(userId, events) {
  // Intra-batch dedup: key on hash|occurrence; reject if 5+ identical
  const batchCheck = checkBatchDuplicates(events, computeGlobalContentHash, (e, h) => h + '|' + (e.occurrence ?? 1));
  if (batchCheck.rejected) {
    console.warn('[ingestion] Suspicious global batch from user %s: %d repeats of same event', userId, batchCheck.maxRepeats);
    return { accepted: 0, duplicates: 0, conflicts: 0, rejected: true, reason: 'Duplicate events in batch' };
  }

  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0, conflicts = 0;

  const client = await pool.connect();
  try {
    for (const event of batchCheck.deduped) {
      const contentHash = computeGlobalContentHash(event);
      const occurrence = event.occurrence ?? 1;
      const eventTs = new Date(event.timestamp);
      const dedupLo = new Date(eventTs.getTime() - GLOBAL_DEDUP_WINDOW_MS);
      const dedupHi = new Date(eventTs.getTime() + GLOBAL_DEDUP_WINDOW_MS);

      try {
        await client.query('BEGIN');
        // Serialize concurrent processing of the same content hash + occurrence
        await client.query('SELECT pg_advisory_xact_lock(hashtext($1))', [contentHash + '|' + occurrence]);

        // 1. Exact match: same content_hash + occurrence within ±5 min window
        const { rows: exactMatches } = await client.query(
          `SELECT ig.id,
                  EXISTS(
                    SELECT 1 FROM ingested_global_submissions
                    WHERE global_id = ig.id AND user_id = $5
                  ) AS already_submitted
           FROM ingested_globals ig
           WHERE ig.content_hash = $1
             AND ig.occurrence = $2
             AND ig.event_timestamp BETWEEN $3 AND $4
           ORDER BY abs(extract(epoch from ig.event_timestamp - $6::timestamptz))
           LIMIT 1`,
          [contentHash, occurrence, dedupLo.toISOString(), dedupHi.toISOString(), userId, eventTs.toISOString()]
        );

        if (exactMatches.length > 0) {
          const match = exactMatches[0];
          if (match.already_submitted) {
            // User already confirmed this exact event+occurrence — duplicate
            await client.query('COMMIT');
            duplicates++;
            continue;
          }

          // Confirm the existing entry
          await client.query(
            `INSERT INTO ingested_global_submissions (global_id, user_id, weight, event_timestamp)
             VALUES ($1, $2, $3, $4)`,
            [match.id, userId, weight, eventTs.toISOString()]
          );

          await client.query(
            `UPDATE ingested_globals
             SET confirmation_count = confirmation_count + $1,
                 confirmed = (confirmation_count + $1) >= $2,
                 confirmed_at = CASE WHEN (confirmation_count + $1) >= $2 AND NOT confirmed THEN now() ELSE confirmed_at END
             WHERE id = $3`,
            [weight, GLOBAL_CONFIRM_THRESHOLD, match.id]
          );

          await client.query('COMMIT');
          accepted++;
          continue;
        }

        // 2. Check for slot conflict (same type + player + target within tight window, different hash).
        //    Uses a tight ±10s window. Identical events (same hash) with different occurrences
        //    won't trigger this since their content_hash matches — they fall through to step 3.
        const slotLo = new Date(eventTs.getTime() - TRADE_SLOT_WINDOW_MS);
        const slotHi = new Date(eventTs.getTime() + TRADE_SLOT_WINDOW_MS);
        const { rows: slotMatches } = await client.query(
          `SELECT id, content_hash FROM ingested_globals
           WHERE global_type = $1
             AND player_name = $2
             AND target_name = $3
             AND event_timestamp BETWEEN $4 AND $5
           LIMIT 1`,
          [event.type, event.player, event.target, slotLo.toISOString(), slotHi.toISOString()]
        );

        if (slotMatches.length > 0) {
          const existing = slotMatches[0];
          if (existing.content_hash !== contentHash) {
            // Actual conflict: same slot, different content
            await client.query(
              `INSERT INTO ingestion_conflicts (type, existing_id, existing_hash, conflicting_hash, conflicting_data, user_id)
               VALUES ('global', $1, $2, $3, $4, $5)`,
              [existing.id, existing.content_hash, contentHash, JSON.stringify(sanitizeGlobalEvent(event)), userId]
            );
            await client.query('COMMIT');
            conflicts++;
            continue;
          }
          // Same hash, different occurrence — fall through to step 3 (new entry)
        }

        // 3. New event — resolve mob/maturity and insert canonical entry + first submission
        const confirmed = weight >= GLOBAL_CONFIRM_THRESHOLD;

        const mobMatch = (event.type === 'kill' || event.type === 'team_kill')
          ? resolveMob(event.target)
          : null;

        const extra = event.type === 'tier' && event.value != null
          ? JSON.stringify({ tier: event.value })
          : null;

        const { rows: inserted } = await client.query(
          `INSERT INTO ingested_globals
             (content_hash, occurrence, global_type, player_name, target_name, value, value_unit,
              location, is_hof, is_ath, event_timestamp, confirmation_count, confirmed, confirmed_at,
              mob_id, maturity_id, extra)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, CASE WHEN $13 THEN now() ELSE NULL END,
                   $14, $15, $16)
           RETURNING id`,
          [
            contentHash, occurrence, event.type, event.player, event.target,
            event.value, event.unit || 'PED', event.location || null,
            event.hof ?? false, event.ath ?? false,
            eventTs.toISOString(), weight, confirmed,
            mobMatch?.mobId ?? null, mobMatch?.maturityId ?? null, extra,
          ]
        );

        await client.query(
          `INSERT INTO ingested_global_submissions (global_id, user_id, weight, event_timestamp)
           VALUES ($1, $2, $3, $4)`,
          [inserted[0].id, userId, weight, eventTs.toISOString()]
        );

        await client.query('COMMIT');
        accepted++;
      } catch (e) {
        await client.query('ROLLBACK').catch(() => {});
        if (e.code === '23505') { // unique_violation
          duplicates++;
        } else {
          throw e;
        }
      }
    }
  } finally {
    client.release();
  }

  return { accepted, duplicates, conflicts };
}

// --- Trade Message Ingestion ---

/**
 * Process a batch of trade messages from a single user.
 * Similar to globals but with no confirmation threshold.
 *
 * Uses per-event transactions with advisory locks to prevent concurrent
 * requests from creating duplicate canonical rows for the same message.
 *
 * @param {bigint|string} userId
 * @param {object[]} messages - Array of trade message objects
 * @returns {Promise<{ accepted: number, duplicates: number, conflicts: number, rejected?: boolean, reason?: string }>}
 */
export async function ingestTrades(userId, messages) {
  // Intra-batch dedup: reject if same message appears 3+ times (suspicious)
  const batchCheck = checkBatchDuplicates(messages, computeTradeContentHash);
  if (batchCheck.rejected) {
    console.warn('[ingestion] Suspicious trade batch from user %s: %d repeats of same message', userId, batchCheck.maxRepeats);
    return { accepted: 0, duplicates: 0, conflicts: 0, rejected: true, reason: 'Duplicate messages in batch' };
  }

  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0, conflicts = 0;

  const client = await pool.connect();
  try {
    for (const msg of batchCheck.deduped) {
      const contentHash = computeTradeContentHash(msg);
      const eventTs = new Date(msg.timestamp);
      const windowLo = new Date(eventTs.getTime() - TIMESTAMP_WINDOW_MS);
      const windowHi = new Date(eventTs.getTime() + TIMESTAMP_WINDOW_MS);

      try {
        await client.query('BEGIN');
        // Serialize concurrent processing of the same content hash
        await client.query('SELECT pg_advisory_xact_lock(hashtext($1))', [contentHash]);

        // 1. Exact content match within time window
        const { rows: exactMatches } = await client.query(
          `SELECT id FROM ingested_trade_messages
           WHERE content_hash = $1
             AND event_timestamp BETWEEN $2 AND $3
           LIMIT 1`,
          [contentHash, windowLo.toISOString(), windowHi.toISOString()]
        );

        if (exactMatches.length > 0) {
          const existing = exactMatches[0];

          await client.query(
            `INSERT INTO ingested_trade_submissions (trade_message_id, user_id, weight, event_timestamp)
             VALUES ($1, $2, $3, $4)`,
            [existing.id, userId, weight, eventTs.toISOString()]
          );

          await client.query(
            `UPDATE ingested_trade_messages SET confirmation_count = confirmation_count + $1 WHERE id = $2`,
            [weight, existing.id]
          );

          await client.query('COMMIT');
          accepted++;
          continue;
        }

        // 2. Slot conflict (same channel + username within ±10s, different content)
        const slotWindowLo = new Date(eventTs.getTime() - TRADE_SLOT_WINDOW_MS);
        const slotWindowHi = new Date(eventTs.getTime() + TRADE_SLOT_WINDOW_MS);

        const { rows: slotMatches } = await client.query(
          `SELECT id, content_hash FROM ingested_trade_messages
           WHERE channel = $1
             AND username = $2
             AND event_timestamp BETWEEN $3 AND $4
           LIMIT 1`,
          [msg.channel, msg.username, slotWindowLo.toISOString(), slotWindowHi.toISOString()]
        );

        if (slotMatches.length > 0) {
          const existing = slotMatches[0];
          await client.query(
            `INSERT INTO ingestion_conflicts (type, existing_id, existing_hash, conflicting_hash, conflicting_data, user_id)
             VALUES ('trade', $1, $2, $3, $4, $5)`,
            [existing.id, existing.content_hash, contentHash, JSON.stringify(sanitizeTradeMessage(msg)), userId]
          );
          await client.query('COMMIT');
          conflicts++;
          continue;
        }

        // 2.5 Repost dedup: check for similar messages from same user in last 15 min
        const repostLo = new Date(eventTs.getTime() - REPOST_WINDOW_MS);
        const { rows: recentMsgs } = await client.query(
          `SELECT message FROM ingested_trade_messages
           WHERE username = $1 AND channel = $2
             AND event_timestamp > $3
           ORDER BY event_timestamp DESC LIMIT 5`,
          [msg.username, msg.channel, repostLo.toISOString()]
        );

        if (recentMsgs.length > 0) {
          const msgNorm = msg.message.toLowerCase().trim();
          const maxDist = Math.max(REPOST_MIN_DISTANCE, Math.floor(msgNorm.length * REPOST_MAX_DISTANCE_RATIO));
          const isRepost = recentMsgs.some(r => {
            const existing = r.message.toLowerCase().trim();
            return levenshteinBounded(msgNorm, existing, maxDist) <= maxDist;
          });
          if (isRepost) {
            await client.query('COMMIT');
            duplicates++;
            continue;
          }
        }

        // 3. New trade message
        const { rows: inserted } = await client.query(
          `INSERT INTO ingested_trade_messages
             (content_hash, channel, username, message, event_timestamp, confirmation_count)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id`,
          [contentHash, msg.channel, msg.username, msg.message, eventTs.toISOString(), weight]
        );

        await client.query(
          `INSERT INTO ingested_trade_submissions (trade_message_id, user_id, weight, event_timestamp)
           VALUES ($1, $2, $3, $4)`,
          [inserted[0].id, userId, weight, eventTs.toISOString()]
        );

        await client.query('COMMIT');
        accepted++;
      } catch (e) {
        await client.query('ROLLBACK').catch(() => {});
        if (e.code === '23505') { // unique_violation
          duplicates++;
        } else {
          throw e;
        }
      }
    }
  } finally {
    client.release();
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
            location, is_hof, is_ath, event_timestamp, confirmation_count, confirmed,
            first_seen_at, occurrence
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
    `SELECT id, channel, username, message, event_timestamp, confirmation_count,
            first_seen_at
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
      (SELECT count(DISTINCT user_id) FROM (
        SELECT user_id FROM ingested_global_submissions
        UNION
        SELECT user_id FROM ingested_trade_submissions
      ) all_users) AS active_contributors,
      (SELECT count(*) FROM ingestion_bans) AS active_bans,
      (SELECT count(*) FROM ingestion_alerts WHERE NOT resolved) AS pending_alerts,
      (SELECT count(*) FROM ingestion_conflicts) AS total_conflicts,
      (SELECT count(*) FROM ingestion_allowed_clients) AS allowed_clients,
      (SELECT count(*) FROM ingestion_trade_channels) AS configured_channels
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
  let globalIds = [], tradeIds = [];

  try {
    // 1. Collect affected global IDs
    const { rows: globalSubs } = await client.query(
      'SELECT DISTINCT global_id FROM ingested_global_submissions WHERE user_id = $1',
      [userId]
    );
    globalIds = globalSubs.map(r => r.global_id);

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
    tradeIds = tradeSubs.map(r => r.trade_message_id);

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

  return { purgedGlobals: globalIds.length, purgedTrades: tradeIds.length };
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

    // Batch-fetch other submitters for all conflicted entries to avoid N+1 queries
    const globalConflictIds = userConflicts.filter(c => c.type === 'global').map(c => c.existing_id);
    const tradeConflictIds = userConflicts.filter(c => c.type !== 'global').map(c => c.existing_id);

    // Map existing_id → set of other user_ids who confirmed the canonical entry
    const confirmersMap = new Map();

    if (globalConflictIds.length > 0) {
      const { rows } = await pool.query(
        `SELECT global_id, user_id FROM ingested_global_submissions
         WHERE global_id = ANY($1) AND user_id != $2`,
        [globalConflictIds, userId]
      );
      for (const r of rows) {
        if (!confirmersMap.has(r.global_id)) confirmersMap.set(r.global_id, new Set());
        confirmersMap.get(r.global_id).add(String(r.user_id));
      }
    }
    if (tradeConflictIds.length > 0) {
      const { rows } = await pool.query(
        `SELECT trade_message_id, user_id FROM ingested_trade_submissions
         WHERE trade_message_id = ANY($1) AND user_id != $2`,
        [tradeConflictIds, userId]
      );
      for (const r of rows) {
        if (!confirmersMap.has(r.trade_message_id)) confirmersMap.set(r.trade_message_id, new Set());
        confirmersMap.get(r.trade_message_id).add(String(r.user_id));
      }
    }

    for (const conflict of userConflicts) {
      const others = confirmersMap.get(conflict.existing_id);
      if (others && others.size > 0) {
        // User is in the minority: at least one other user confirmed the canonical version
        minorityCount++;
        for (const uid of others) counterpartUsers.add(uid);
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

  // --- Additional fraud analyses ---

  // Majority swap: always runs (requires 3+ conflict users, self-gating)
  try { await resolveMajorityConflicts(); }
  catch (err) { console.error('[ingestion] Majority conflict resolution failed:', err); }

  // Statistical analyses: only meaningful with enough active contributors
  const { rows: [{ count: activeCount }] } = await pool.query(
    `SELECT count(DISTINCT user_id) FROM ingested_global_submissions
     WHERE submitted_at > now() - interval '7 days'`
  );
  if (parseInt(activeCount) >= MIN_ACTIVE_CONTRIBUTORS) {
    try { await detectCollusion(); }
    catch (err) { console.error('[ingestion] Collusion detection failed:', err); }

    try { await detectSoloFabrication(); }
    catch (err) { console.error('[ingestion] Solo fabrication detection failed:', err); }
  }
}

// --- Majority Conflict Resolution ---

/**
 * When a conflicting version of a global event has more supporters than the
 * canonical entry, swap them. The original submitter becomes the conflict,
 * the majority version becomes canonical.
 *
 * Only processes 'global' type conflicts (trade messages don't have confirmation
 * thresholds). Requires at least MAJORITY_SWAP_MIN_USERS (3) conflict users
 * AND strictly more than the existing entry's confirmation count.
 */
async function resolveMajorityConflicts() {
  const { rows: candidates } = await pool.query(`
    SELECT
      c.existing_id,
      c.conflicting_hash,
      ig.confirmation_count AS existing_confirmations,
      ig.content_hash AS existing_hash,
      count(DISTINCT c.user_id) AS conflict_user_count,
      array_agg(DISTINCT c.user_id) AS conflict_user_ids,
      (array_agg(c.conflicting_data ORDER BY c.created_at ASC))[1] AS conflicting_data
    FROM ingestion_conflicts c
    JOIN ingested_globals ig ON ig.id = c.existing_id
    WHERE c.type = 'global'
      AND c.created_at > now() - interval '7 days'
      -- Cooldown: skip globals that were already swapped in the last 24h to prevent ping-pong
      AND NOT EXISTS (
        SELECT 1 FROM ingestion_alerts
        WHERE type = 'majority_swap'
          AND (details->>'global_id')::int = c.existing_id
          AND created_at > now() - interval '24 hours'
      )
    GROUP BY c.existing_id, c.conflicting_hash, ig.confirmation_count, ig.content_hash
    HAVING count(DISTINCT c.user_id) >= $1
       AND count(DISTINCT c.user_id) > ig.confirmation_count
    LIMIT 50
  `, [MAJORITY_SWAP_MIN_USERS]);

  // Pre-fetch all submission weights to avoid N+1 queries inside the transaction.
  // getSubmissionWeight() uses pool.query() internally — calling it inside a
  // startTransaction() block would acquire separate connections and risk leaks.
  const allUserIds = new Set();
  for (const c of candidates) {
    for (const uid of c.conflict_user_ids) allUserIds.add(String(uid));
  }
  const weightMap = new Map();
  for (const uid of allUserIds) {
    weightMap.set(uid, await getSubmissionWeight(uid));
  }

  for (const candidate of candidates) {
    const client = await startTransaction();
    try {
      const newData = typeof candidate.conflicting_data === 'string'
        ? JSON.parse(candidate.conflicting_data)
        : candidate.conflicting_data;

      // 1. Snapshot the current canonical entry for the reverse conflict record
      const { rows: [oldEntry] } = await client.query(
        `SELECT global_type, player_name, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp
         FROM ingested_globals WHERE id = $1`,
        [candidate.existing_id]
      );

      const oldData = {
        type: oldEntry.global_type,
        player: oldEntry.player_name,
        target: oldEntry.target_name,
        value: oldEntry.value != null ? parseFloat(oldEntry.value) : null,
        unit: oldEntry.value_unit,
        location: oldEntry.location,
        hof: oldEntry.is_hof,
        ath: oldEntry.is_ath,
        timestamp: oldEntry.event_timestamp,
      };

      // 2. Get existing submitters (will become conflict users)
      const { rows: existingSubs } = await client.query(
        'SELECT user_id FROM ingested_global_submissions WHERE global_id = $1',
        [candidate.existing_id]
      );

      // 3. Update canonical entry with the majority version
      await client.query(
        `UPDATE ingested_globals SET
           content_hash = $1,
           global_type = $2,
           player_name = $3,
           target_name = $4,
           value = $5,
           value_unit = COALESCE($6, 'PED'),
           location = $7,
           is_hof = COALESCE($8, false),
           is_ath = COALESCE($9, false)
         WHERE id = $10`,
        [
          candidate.conflicting_hash,
          newData.type, newData.player, newData.target,
          newData.value, newData.unit || 'PED',
          newData.location || null,
          newData.hof ?? false, newData.ath ?? false,
          candidate.existing_id,
        ]
      );

      // 4. Delete old submissions
      await client.query(
        'DELETE FROM ingested_global_submissions WHERE global_id = $1',
        [candidate.existing_id]
      );

      // 5. Insert submissions for the conflict users (with pre-fetched weights)
      const swapTs = newData.timestamp || new Date().toISOString();
      for (const userId of candidate.conflict_user_ids) {
        const weight = weightMap.get(String(userId)) || 1;
        await client.query(
          `INSERT INTO ingested_global_submissions (global_id, user_id, weight, event_timestamp)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (global_id, user_id) DO NOTHING`,
          [candidate.existing_id, userId, weight, swapTs]
        );
      }

      // 6. Recalculate confirmation_count from actual submissions
      const { rows: [{ total_weight: newWeight }] } = await client.query(
        `SELECT COALESCE(SUM(weight), 0) AS total_weight
         FROM ingested_global_submissions WHERE global_id = $1`,
        [candidate.existing_id]
      );
      const newCount = parseInt(newWeight);
      const nowConfirmed = newCount >= GLOBAL_CONFIRM_THRESHOLD;

      await client.query(
        `UPDATE ingested_globals
         SET confirmation_count = $1,
             confirmed = $2,
             confirmed_at = CASE WHEN $2 AND confirmed_at IS NULL THEN now() ELSE confirmed_at END
         WHERE id = $3`,
        [newCount, nowConfirmed, candidate.existing_id]
      );

      // 7. Create conflict records for original submitters
      for (const oldSub of existingSubs) {
        await client.query(
          `INSERT INTO ingestion_conflicts (type, existing_id, existing_hash, conflicting_hash, conflicting_data, user_id)
           VALUES ('global', $1, $2, $3, $4, $5)`,
          [
            candidate.existing_id,
            candidate.conflicting_hash,
            candidate.existing_hash,
            JSON.stringify(oldData),
            oldSub.user_id,
          ]
        );
      }

      // 8. Delete the old conflict records that triggered this swap
      await client.query(
        `DELETE FROM ingestion_conflicts
         WHERE type = 'global'
           AND existing_id = $1
           AND conflicting_hash = $2`,
        [candidate.existing_id, candidate.conflicting_hash]
      );

      // 9. Create audit alert
      await client.query(
        `INSERT INTO ingestion_alerts (type, user_ids, details)
         VALUES ('majority_swap', $1, $2)`,
        [
          [
            ...existingSubs.map(s => s.user_id),
            ...candidate.conflict_user_ids,
          ],
          JSON.stringify({
            global_id: candidate.existing_id,
            old_hash: candidate.existing_hash,
            new_hash: candidate.conflicting_hash,
            old_submitter_count: existingSubs.length,
            new_submitter_count: parseInt(candidate.conflict_user_count),
          }),
        ]
      );

      await client.query('COMMIT');
      console.log('[ingestion] Majority swap for global %d: %d→%d submitters',
        candidate.existing_id, existingSubs.length, parseInt(candidate.conflict_user_count));
    } catch (err) {
      await client.query('ROLLBACK');
      console.error('[ingestion] Majority swap failed for global', candidate.existing_id, err);
    } finally {
      client.release();
    }
  }
}

// --- Collusion Detection ---

/**
 * Detect pairs of users with suspiciously high exclusive overlap in their
 * global submissions — i.e., they frequently confirm the same events that
 * NO other users confirm.
 *
 * Accounts for planet-local playerbases: if all exclusive events come from
 * a single location, suspicion is lowered. Exclusive HoFs (game-wide events
 * that should have broad confirmation) raise suspicion.
 */
async function detectCollusion() {
  // Use a dedicated client with elevated timeout for analysis queries
  const client = await pool.connect();
  await client.query('SET statement_timeout = 30000');

  try {
    const { rows: suspiciousPairs } = await client.query(`
      WITH recent_subs AS (
        SELECT global_id, user_id
        FROM ingested_global_submissions
        WHERE submitted_at > now() - interval '7 days'
      ),
      submission_counts AS (
        SELECT global_id, count(DISTINCT user_id) AS submitter_count
        FROM recent_subs GROUP BY global_id
      ),
      user_pairs AS (
        SELECT a.user_id AS user_a, b.user_id AS user_b,
               count(*) AS shared_count,
               count(*) FILTER (WHERE sc.submitter_count = 2) AS exclusive_count
        FROM recent_subs a
        JOIN recent_subs b ON a.global_id = b.global_id AND a.user_id < b.user_id
        JOIN submission_counts sc ON sc.global_id = a.global_id
        GROUP BY a.user_id, b.user_id
        HAVING count(*) >= $1
      )
      SELECT user_a, user_b, shared_count, exclusive_count,
             ROUND(exclusive_count::numeric / shared_count, 2) AS exclusive_rate
      FROM user_pairs
      WHERE exclusive_count >= $1
        AND (exclusive_count::numeric / shared_count) >= $2
      ORDER BY exclusive_rate DESC
      LIMIT 50
    `, [COLLUSION_MIN_EXCLUSIVE, COLLUSION_MIN_EXCLUSIVE_RATE]);

    for (const pair of suspiciousPairs) {
      // Skip if already alerted
      const { rows: existing } = await client.query(
        `SELECT 1 FROM ingestion_alerts
         WHERE NOT resolved
           AND type = 'collusion_pattern'
           AND $1 = ANY(user_ids)
           AND $2 = ANY(user_ids)
         LIMIT 1`,
        [pair.user_a, pair.user_b]
      );
      if (existing.length > 0) continue;

      // Location distribution + HoF count of exclusive events (single query)
      // Include NULL locations so HoFs without location are still counted
      const { rows: exclusiveRows } = await client.query(`
        WITH exclusive_globals AS (
          SELECT a.global_id
          FROM ingested_global_submissions a
          JOIN ingested_global_submissions b ON a.global_id = b.global_id
          WHERE a.user_id = $1 AND b.user_id = $2
            AND a.submitted_at > now() - interval '7 days'
            AND NOT EXISTS (
              SELECT 1 FROM ingested_global_submissions x
              WHERE x.global_id = a.global_id
                AND x.user_id NOT IN ($1, $2)
            )
        )
        SELECT ig.location, count(*) AS count,
               count(*) FILTER (WHERE ig.is_hof) AS hof_count
        FROM exclusive_globals eg
        JOIN ingested_globals ig ON ig.id = eg.global_id
        GROUP BY ig.location
        ORDER BY count DESC
        LIMIT 6
      `, [pair.user_a, pair.user_b]);

      const exclusiveHofs = exclusiveRows.reduce((sum, r) => sum + parseInt(r.hof_count), 0);
      const locationDist = exclusiveRows.filter(r => r.location !== null);
      const locationCount = locationDist.length;

      // Suspicion level based on location spread and HoF exclusives
      let suspicion = 'medium';
      if (exclusiveHofs > 0 || locationCount > 2) {
        suspicion = 'high';
      } else if (locationCount <= 1 && exclusiveHofs === 0) {
        suspicion = 'low';
      }

      // Only alert on medium or high suspicion
      if (suspicion === 'low') continue;

      await client.query(
        `INSERT INTO ingestion_alerts (type, user_ids, details)
         VALUES ('collusion_pattern', $1, $2)`,
        [
          [pair.user_a, pair.user_b],
          JSON.stringify({
            shared_count: parseInt(pair.shared_count),
            exclusive_count: parseInt(pair.exclusive_count),
            exclusive_rate: Math.round(parseFloat(pair.exclusive_rate) * 100),
            exclusive_hofs: exclusiveHofs,
            top_locations: locationDist.map(r => ({ location: r.location, count: parseInt(r.count) })),
            suspicion_level: suspicion,
            period: '7 days',
          }),
        ]
      );
    }
  } finally {
    await client.query('RESET statement_timeout').catch(() => {});
    client.release();
  }
}

// --- Solo Fabrication Detection ---

/**
 * Flag users who have a high ratio of global events that nobody else ever
 * confirms. A high "solo rate" suggests fabricated events injected into
 * the chat log.
 *
 * Uses a relative comparison: only alerts if the user's solo rate is
 * significantly above the system-wide average, preventing false positives
 * when overall confirmation coverage is low.
 *
 * Solo HoFs are especially suspicious since HoFs are game-wide events
 * that should be seen by many players.
 */
async function detectSoloFabrication() {
  // Compute system-wide average solo rate first
  const { rows: avgRows } = await pool.query(`
    WITH user_stats AS (
      SELECT
        gs.user_id,
        count(*) AS submission_count,
        count(*) FILTER (
          WHERE ig.confirmation_count <= gs.weight
            AND ig.first_seen_at < now() - ($2 * interval '1 hour')
        ) AS solo_count
      FROM ingested_global_submissions gs
      JOIN ingested_globals ig ON ig.id = gs.global_id
      WHERE gs.submitted_at > now() - interval '7 days'
      GROUP BY gs.user_id
      HAVING count(*) >= $1
    )
    SELECT
      COALESCE(AVG(solo_count::numeric / NULLIF(submission_count, 0)), 0) AS avg_solo_rate
    FROM user_stats
  `, [SOLO_MIN_SUBMISSIONS, SOLO_AGE_HOURS]);

  const avgSoloRate = parseFloat(avgRows[0].avg_solo_rate);
  // Effective threshold: max of absolute threshold and 2x the average
  const effectiveRate = Math.max(SOLO_MAX_RATE, avgSoloRate * 2);

  const { rows: candidates } = await pool.query(`
    WITH user_stats AS (
      SELECT
        gs.user_id,
        count(*) AS submission_count,
        count(*) FILTER (
          WHERE ig.confirmation_count <= gs.weight
            AND ig.first_seen_at < now() - ($4 * interval '1 hour')
        ) AS solo_count,
        count(*) FILTER (
          WHERE ig.confirmation_count <= gs.weight
            AND ig.first_seen_at < now() - ($4 * interval '1 hour')
            AND ig.is_hof = true
        ) AS solo_hof_count
      FROM ingested_global_submissions gs
      JOIN ingested_globals ig ON ig.id = gs.global_id
      WHERE gs.submitted_at > now() - interval '7 days'
      GROUP BY gs.user_id
      HAVING count(*) >= $1
    )
    SELECT user_id, submission_count, solo_count, solo_hof_count,
           ROUND(solo_count::numeric / submission_count, 2) AS solo_rate
    FROM user_stats
    WHERE solo_count >= $2
      AND (solo_count::numeric / submission_count) >= $3
  `, [SOLO_MIN_SUBMISSIONS, SOLO_MIN_SOLO_COUNT, effectiveRate, SOLO_AGE_HOURS]);

  for (const user of candidates) {
    // Skip if already alerted
    const { rows: existing } = await pool.query(
      `SELECT 1 FROM ingestion_alerts
       WHERE NOT resolved
         AND type = 'solo_fabrication'
         AND $1 = ANY(user_ids)
       LIMIT 1`,
      [user.user_id]
    );
    if (existing.length > 0) continue;

    await pool.query(
      `INSERT INTO ingestion_alerts (type, user_ids, details)
       VALUES ('solo_fabrication', $1, $2)`,
      [
        [user.user_id],
        JSON.stringify({
          submission_count: parseInt(user.submission_count),
          solo_count: parseInt(user.solo_count),
          solo_rate: Math.round(parseFloat(user.solo_rate) * 100),
          solo_hof_count: parseInt(user.solo_hof_count),
          avg_solo_rate: Math.round(avgSoloRate * 100),
          period: '7 days',
          age_threshold_hours: SOLO_AGE_HOURS,
        }),
      ]
    );
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
    if (buffer.length > MAX_COMPRESSED_SIZE) {
      throw new Error('Compressed payload too large');
    }
    const decompressed = await gunzipAsync(buffer);
    if (decompressed.length > MAX_DECOMPRESSED_SIZE) {
      throw new Error('Decompressed payload too large');
    }
    return JSON.parse(decompressed.toString('utf-8'));
  }

  return await request.json();
}

// --- Throttled Conflict Analysis Trigger ---

const CONFLICT_ANALYSIS_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes
let _lastConflictAnalysis = 0;
let _conflictAnalysisRunning = false;

/**
 * Fire-and-forget conflict analysis, throttled to at most once per 15 minutes.
 * Safe to call from hot paths (POST endpoints) — returns immediately.
 *
 * Race-condition safe: Node.js runs JS on a single event-loop thread, so the
 * synchronous guard checks (_conflictAnalysisRunning, timestamp comparison)
 * and flag assignments cannot interleave between concurrent requests.
 * The async work only begins after the guards have been set.
 */
export function maybeAnalyzeConflicts() {
  const now = Date.now();
  if (_conflictAnalysisRunning || now - _lastConflictAnalysis < CONFLICT_ANALYSIS_INTERVAL_MS) {
    return;
  }
  _lastConflictAnalysis = now;
  _conflictAnalysisRunning = true;

  // Intentional fire-and-forget — result is deliberately discarded.
  void analyzeConflicts()
    .catch(err => console.error('[ingestion] Conflict analysis failed:', err))
    .finally(() => { _conflictAnalysisRunning = false; });
}
