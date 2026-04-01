// @ts-nocheck
import crypto from 'crypto';
import { pool, startTransaction, invalidateMarketPriceCache, getLatestMarketPrices } from './db.js';
import { resolveUserGrants } from './grants.js';
import { resolveMob } from './mobResolver.js';
import { invalidateGlobalsCache } from './globals-cache.js';
import { TIERABLE_TYPES } from '$lib/common/itemTypes.js';

// --- Constants ---

const GLOBAL_CONFIRM_THRESHOLD = 3;
const HOF_CONFIRM_THRESHOLD = 6;
const TIMESTAMP_WINDOW_MS = 60_000; // ±60 seconds for matching (trades)
const GLOBAL_DEDUP_WINDOW_MS = 5 * 60 * 1000; // ±5 min for occurrence-based dedup (globals)
const VALID_GLOBAL_TYPES = new Set(['kill', 'team_kill', 'deposit', 'craft', 'rare_item', 'discovery', 'tier', 'examine', 'pvp']);
const VALUE_OPTIONAL_TYPES = new Set(['discovery', 'tier', 'rare_item', 'pvp']);
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
     LEFT JOIN ONLY users u ON u.id = tc.added_by
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
  if (event.unit && !['PED', 'PEC', 'TIER', 'kills'].includes(event.unit)) return 'Invalid unit';
  if (event.hof != null && typeof event.hof !== 'boolean') return 'hof must be a boolean';
  if (event.ath != null && typeof event.ath !== 'boolean') return 'ath must be a boolean';
  if (event.occurrence != null) {
    if (!Number.isInteger(event.occurrence) || event.occurrence < 1)
      return 'Invalid occurrence: must be a positive integer';
  }

  const ts = new Date(event.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  if (Date.now() - ts.getTime() < -TIMESTAMP_WINDOW_MS) return 'Timestamp in the future';

  return null;
}

/**
 * Normalize a global event after validation. Fixes known client issues:
 * - Old clients embed location in discovery target_name as "Item. Item discovered in Location"
 */
export function normalizeGlobalEvent(event) {
  if (event.type === 'discovery' && event.target) {
    const match = event.target.match(/^(.+?)\. Item discovered in (.+)$/);
    if (match) {
      event.target = match[1];
      event.location = match[2];
    }
  }
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

/**
 * Collapse exact intra-batch duplicates (first of each key kept).
 * Per-event dedup with ±5min windows handles real duplicate detection.
 *
 * @param {object[]} events
 * @param {function} hashFn - Content hash function
 * @param {function} [keyFn] - Optional custom key function (event, hash) => string.
 *   Defaults to hash + '|' + timestamp.
 */
function deduplicateBatch(events, hashFn, keyFn) {
  const seen = new Set();
  return events.filter(event => {
    const hash = hashFn(event);
    const key = keyFn ? keyFn(event, hash) : hash + '|' + event.timestamp;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// --- Global Ingestion ---

/**
 * Process a batch of global events from a single user.
 * Deduplicates by content hash + occurrence within a ±5min window,
 * deduplicates by content hash + occurrence, and tracks confirmations.
 *
 * Uses per-event transactions with advisory locks to prevent concurrent
 * requests from creating duplicate canonical rows for the same event.
 *
 * @param {bigint|string} userId
 * @param {object[]} events - Array of global event objects
 * @returns {Promise<{ accepted: number, duplicates: number, rejected?: boolean, reason?: string }>}
 */
export async function ingestGlobals(userId, events) {
  // Collapse exact intra-batch duplicates (same hash+occurrence+timestamp).
  // Per-event ±5min window dedup handles real duplicate detection.
  const deduped = deduplicateBatch(events, computeGlobalContentHash, (e, h) => h + '|' + (e.occurrence ?? 1) + '|' + e.timestamp);

  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0;

  // Single transaction for the entire batch — saves N-1 WAL syncs vs per-event commits.
  // Advisory locks are held until COMMIT but contention is rare (different users process
  // different events, same-user batches are sequential anyway).
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    for (const event of deduped) {
      const contentHash = computeGlobalContentHash(event);
      const occurrence = event.occurrence ?? 1;
      const eventTs = new Date(event.timestamp);
      const confirmThreshold = event.hof ? HOF_CONFIRM_THRESHOLD : GLOBAL_CONFIRM_THRESHOLD;
      const dedupLo = new Date(eventTs.getTime() - GLOBAL_DEDUP_WINDOW_MS);
      const dedupHi = new Date(eventTs.getTime() + GLOBAL_DEDUP_WINDOW_MS);

      try {
        await client.query('SAVEPOINT sp');
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
            // User already confirmed — but check if their weight has increased
            // (e.g. gained ingestion.trusted grant since original submission)
            const { rows: [existingSub] } = await client.query(
              `SELECT weight FROM ingested_global_submissions
               WHERE global_id = $1 AND user_id = $2`,
              [match.id, userId]
            );
            if (existingSub && weight > existingSub.weight) {
              const delta = weight - existingSub.weight;
              await client.query(
                `UPDATE ingested_global_submissions SET weight = $1
                 WHERE global_id = $2 AND user_id = $3`,
                [weight, match.id, userId]
              );
              await client.query(
                `UPDATE ingested_globals
                 SET confirmation_count = confirmation_count + $1,
                     confirmed = (confirmation_count + $1) >= $2,
                     confirmed_at = CASE WHEN (confirmation_count + $1) >= $2 AND NOT confirmed THEN now() ELSE confirmed_at END
                 WHERE id = $3`,
                [delta, confirmThreshold, match.id]
              );
            }
            await client.query('RELEASE SAVEPOINT sp');
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
            [weight, confirmThreshold, match.id]
          );

          await client.query('RELEASE SAVEPOINT sp');
          accepted++;
          continue;
        }

        // 2. New event — resolve mob/maturity and insert canonical entry + first submission
        const confirmed = weight >= confirmThreshold;

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

        await client.query('RELEASE SAVEPOINT sp');
        accepted++;
      } catch (e) {
        await client.query('ROLLBACK TO SAVEPOINT sp').catch(() => {});
        if (e.code === '23505') { // unique_violation
          duplicates++;
        } else {
          // Abort the entire transaction on unexpected errors
          await client.query('ROLLBACK').catch(() => {});
          throw e;
        }
      }
    }

    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK').catch(() => {});
    throw e;
  } finally {
    client.release();
  }

  // Invalidate globals cache when new events were accepted (may have become confirmed)
  if (accepted > 0) {
    // Pass the oldest event timestamp so rollup tables rebuild the correct date range
    const minTs = deduped.reduce((min, e) => {
      const t = new Date(e.timestamp);
      return t < min ? t : min;
    }, new Date());
    invalidateGlobalsCache(minTs);

    // Auto-resolve fraud alerts whose conditions are no longer met (best-effort, non-blocking)
    autoResolveStaleAlerts().catch(err => {
      console.error('[ingestion] autoResolveStaleAlerts failed:', err);
    });
  }

  return { accepted, duplicates };
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
 * @returns {Promise<{ accepted: number, duplicates: number, rejected?: boolean, reason?: string }>}
 */
export async function ingestTrades(userId, messages) {
  // Collapse exact intra-batch duplicates (same hash+timestamp).
  // Per-event dedup handles real duplicates safely.
  const deduped = deduplicateBatch(messages, computeTradeContentHash);

  const weight = await getSubmissionWeight(userId);
  let accepted = 0, duplicates = 0;

  // Single transaction for the entire batch — saves N-1 WAL syncs.
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    for (const msg of deduped) {
      const contentHash = computeTradeContentHash(msg);
      const eventTs = new Date(msg.timestamp);
      const windowLo = new Date(eventTs.getTime() - TIMESTAMP_WINDOW_MS);
      const windowHi = new Date(eventTs.getTime() + TIMESTAMP_WINDOW_MS);

      try {
        await client.query('SAVEPOINT sp');
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

          // Check if user already submitted for this trade message
          const { rows: [existingSub] } = await client.query(
            `SELECT weight FROM ingested_trade_submissions
             WHERE trade_message_id = $1 AND user_id = $2`,
            [existing.id, userId]
          );

          if (existingSub) {
            // Already submitted — update weight if increased
            if (weight > existingSub.weight) {
              const delta = weight - existingSub.weight;
              await client.query(
                `UPDATE ingested_trade_submissions SET weight = $1
                 WHERE trade_message_id = $2 AND user_id = $3`,
                [weight, existing.id, userId]
              );
              await client.query(
                `UPDATE ingested_trade_messages
                 SET confirmation_count = confirmation_count + $1
                 WHERE id = $2`,
                [delta, existing.id]
              );
            }
            await client.query('RELEASE SAVEPOINT sp');
            duplicates++;
            continue;
          }

          // New submission for existing trade message
          await client.query(
            `INSERT INTO ingested_trade_submissions (trade_message_id, user_id, weight, event_timestamp)
             VALUES ($1, $2, $3, $4)`,
            [existing.id, userId, weight, eventTs.toISOString()]
          );

          await client.query(
            `UPDATE ingested_trade_messages SET confirmation_count = confirmation_count + $1 WHERE id = $2`,
            [weight, existing.id]
          );

          await client.query('RELEASE SAVEPOINT sp');
          accepted++;
          continue;
        }

        // 2. Repost dedup: check for similar messages from same user in last 15 min
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
            await client.query('RELEASE SAVEPOINT sp');
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

        await client.query('RELEASE SAVEPOINT sp');
        accepted++;
      } catch (e) {
        await client.query('ROLLBACK TO SAVEPOINT sp').catch(() => {});
        if (e.code === '23505') { // unique_violation
          duplicates++;
        } else {
          await client.query('ROLLBACK').catch(() => {});
          throw e;
        }
      }
    }

    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK').catch(() => {});
    throw e;
  } finally {
    client.release();
  }

  return { accepted, duplicates };
}

// --- Distribution ---

/**
 * Fetch global events newer than `since` for distribution.
 * Returns all entries with a confirmed flag.
 * Excludes historical globals (event_timestamp older than 10 minutes)
 * to prevent flooding feeds when someone ingests old chat logs.
 */
const DISTRIBUTION_MAX_EVENT_AGE = '10 minutes';

export async function getGlobalsSince(since, limit = 200) {
  const { rows } = await pool.query(
    `SELECT id, global_type, player_name, target_name, value, value_unit,
            location, is_hof, is_ath, event_timestamp, confirmation_count, confirmed,
            first_seen_at, occurrence
     FROM ingested_globals
     WHERE first_seen_at > $1
       AND event_timestamp > NOW() - INTERVAL '${DISTRIBUTION_MAX_EVENT_AGE}'
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
      (SELECT count(*) FROM ingestion_allowed_clients) AS allowed_clients,
      (SELECT count(*) FROM ingestion_trade_channels) AS configured_channels,
      (SELECT count(*) FROM market_price_submissions) AS total_mp_submissions,
      (SELECT count(DISTINCT submitted_by) FROM market_price_submissions) AS mp_contributors,
      (SELECT count(*) FROM ONLY market_price_snapshots WHERE finalized_at IS NOT NULL) AS finalized_snapshots
  `);
  return rows[0];
}

// --- Admin: Alerts ---

export async function getAlerts(page = 1, limit = 20, periodDays = null) {
  const offset = (page - 1) * limit;
  const periodClause = periodDays ? `AND a.created_at >= NOW() - INTERVAL '${parseInt(periodDays)} days'` : '';
  const { rows } = await pool.query(
    `SELECT a.*, array_agg(u.username) AS user_names
     FROM ingestion_alerts a
     LEFT JOIN ONLY users u ON u.id = ANY(a.user_ids)
     WHERE NOT a.resolved ${periodClause}
     GROUP BY a.id
     ORDER BY a.created_at DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  );
  const { rows: countRows } = await pool.query(
    `SELECT count(*) AS total FROM ingestion_alerts WHERE NOT resolved ${periodClause}`
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

/**
 * Auto-resolve global fraud alerts whose conditions are no longer met.
 * Called after processing a confirmation batch.
 * - collusion_pattern: re-checks exclusive event rate between the user pair
 * - solo_fabrication: re-checks solo event rate for the user
 */
async function autoResolveStaleAlerts() {
  try {
    // --- Collusion alerts ---
    const { rows: collusionAlerts } = await pool.query(
      `SELECT id, user_ids FROM ingestion_alerts
       WHERE NOT resolved AND type = 'collusion_pattern'`
    );
    for (const alert of collusionAlerts) {
      if (!alert.user_ids || alert.user_ids.length < 2) continue;
      const [userA, userB] = alert.user_ids;
      const { rows: [stats] } = await pool.query(`
        WITH shared AS (
          SELECT a.global_id
          FROM ingested_global_submissions a
          JOIN ingested_global_submissions b ON a.global_id = b.global_id
          WHERE a.user_id = $1 AND b.user_id = $2
            AND a.submitted_at > now() - interval '7 days'
        ),
        exclusive AS (
          SELECT s.global_id FROM shared s
          WHERE NOT EXISTS (
            SELECT 1 FROM ingested_global_submissions x
            WHERE x.global_id = s.global_id AND x.user_id NOT IN ($1, $2)
          )
        )
        SELECT (SELECT count(*) FROM shared) AS shared_count,
               (SELECT count(*) FROM exclusive) AS exclusive_count
      `, [userA, userB]);

      const shared = parseInt(stats.shared_count) || 0;
      const exclusive = parseInt(stats.exclusive_count) || 0;
      if (shared === 0 || exclusive < COLLUSION_MIN_EXCLUSIVE
          || (exclusive / shared) < COLLUSION_MIN_EXCLUSIVE_RATE) {
        await pool.query(
          `UPDATE ingestion_alerts
           SET resolved = true, resolved_at = now(),
               resolution_notes = 'Auto-resolved: conditions no longer met'
           WHERE id = $1`,
          [alert.id]
        );
      }
    }

    // --- Solo fabrication alerts ---
    const { rows: soloAlerts } = await pool.query(
      `SELECT id, user_ids FROM ingestion_alerts
       WHERE NOT resolved AND type = 'solo_fabrication'`
    );
    for (const alert of soloAlerts) {
      if (!alert.user_ids || alert.user_ids.length < 1) continue;
      const userId = alert.user_ids[0];
      const { rows: [stats] } = await pool.query(`
        SELECT count(*) AS submission_count,
               count(*) FILTER (
                 WHERE ig.confirmation_count <= gs.weight
                   AND ig.first_seen_at < now() - ($2 * interval '1 hour')
               ) AS solo_count
        FROM ingested_global_submissions gs
        JOIN ingested_globals ig ON ig.id = gs.global_id
        WHERE gs.user_id = $1
          AND gs.submitted_at > now() - interval '7 days'
      `, [userId, SOLO_AGE_HOURS]);

      const total = parseInt(stats.submission_count) || 0;
      const solo = parseInt(stats.solo_count) || 0;
      if (total === 0 || solo < SOLO_MIN_SOLO_COUNT
          || (total >= SOLO_MIN_SUBMISSIONS && (solo / total) < SOLO_MAX_RATE)) {
        await pool.query(
          `UPDATE ingestion_alerts
           SET resolved = true, resolved_at = now(),
               resolution_notes = 'Auto-resolved: conditions no longer met'
           WHERE id = $1`,
          [alert.id]
        );
      }
    }
  } catch (err) {
    console.error('[ingestion] Error auto-resolving alerts:', err);
  }
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
     mp_stats AS (
       SELECT submitted_by AS user_id,
              count(*) AS mp_count
       FROM market_price_submissions
       GROUP BY submitted_by
     )
     SELECT COALESCE(us.user_id, ms.user_id) AS user_id,
            u.username,
            COALESCE(us.submission_count, 0) AS submission_count,
            COALESCE(us.total_weight, 0) AS total_weight,
            COALESCE(ms.mp_count, 0) AS mp_count,
            CASE WHEN ib.id IS NOT NULL THEN true ELSE false END AS banned
     FROM user_stats us
     FULL OUTER JOIN mp_stats ms ON ms.user_id = us.user_id
     JOIN ONLY users u ON u.id = COALESCE(us.user_id, ms.user_id)
     LEFT JOIN ingestion_bans ib ON ib.user_id = COALESCE(us.user_id, ms.user_id)
     ORDER BY COALESCE(us.submission_count, 0) + COALESCE(ms.mp_count, 0) DESC
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

  if (type === 'market_price') {
    const { rows } = await pool.query(
      `SELECT *
       FROM market_price_submissions
       WHERE submitted_by = $1
       ORDER BY submitted_at DESC
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
  let globalIds = [], tradeIds = [], mpAffected = [];

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
             confirmed = COALESCE(sub.total_weight, 0) >= CASE WHEN ig.is_hof THEN $2 ELSE $3 END,
             confirmed_at = CASE
               WHEN COALESCE(sub.total_weight, 0) >= CASE WHEN ig.is_hof THEN $2 ELSE $3 END THEN ig.confirmed_at
               ELSE NULL
             END
         FROM (
           SELECT global_id, sum(weight) AS total_weight
           FROM ingested_global_submissions
           WHERE global_id = ANY($1)
           GROUP BY global_id
         ) sub
         WHERE ig.id = sub.global_id`,
        [globalIds, HOF_CONFIRM_THRESHOLD, GLOBAL_CONFIRM_THRESHOLD]
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

    // 5. Collect affected market price (item_id, bucket_hour) pairs
    const { rows: mpRows } = await client.query(
      'SELECT DISTINCT item_id, bucket_hour FROM market_price_submissions WHERE submitted_by = $1',
      [userId]
    );
    mpAffected = mpRows;

    // 6. Delete market price submissions
    await client.query(
      'DELETE FROM market_price_submissions WHERE submitted_by = $1',
      [userId]
    );

    // 7. Update ban record with purge metadata
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

  // Purge may have changed confirmed status of globals
  if (globalIds.length > 0) {
    invalidateGlobalsCache();
  }

  // Re-finalize affected market price snapshots (outside transaction — idempotent)
  for (const { item_id, bucket_hour } of mpAffected) {
    try {
      const { rows: [{ cnt }] } = await pool.query(
        'SELECT count(*) AS cnt FROM market_price_submissions WHERE item_id = $1 AND bucket_hour = $2',
        [item_id, bucket_hour]
      );
      if (parseInt(cnt) === 0) {
        // No submissions remain — delete the snapshot
        await pool.query(
          'DELETE FROM ONLY market_price_snapshots WHERE item_id = $1 AND recorded_at = $2',
          [item_id, bucket_hour]
        );
      } else {
        // Re-run finalization with remaining submissions
        await finalizeMarketPriceHour(item_id, bucket_hour);
      }
      invalidateMarketPriceCache(item_id);
    } catch (err) {
      console.error(`[ingestion] Re-finalize after purge failed: item=${item_id} hour=${bucket_hour}`, err.message);
    }
  }

  return { purgedGlobals: globalIds.length, purgedTrades: tradeIds.length, purgedMarketPrices: mpAffected.length };
}

// --- Background: Fraud Detection ---

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

// --- Throttled Fraud Detection Trigger ---

const FRAUD_DETECTION_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes
let _lastFraudDetection = 0;
let _fraudDetectionRunning = false;

/**
 * Fire-and-forget fraud detection, throttled to at most once per 15 minutes.
 * Runs collusion and solo fabrication checks when enough active contributors exist.
 * Safe to call from hot paths (POST endpoints) — returns immediately.
 */
export function maybeRunFraudDetection() {
  const now = Date.now();
  if (_fraudDetectionRunning || now - _lastFraudDetection < FRAUD_DETECTION_INTERVAL_MS) {
    return;
  }
  _lastFraudDetection = now;
  _fraudDetectionRunning = true;

  void (async () => {
    const { rows: [{ count: activeCount }] } = await pool.query(
      `SELECT count(DISTINCT user_id) FROM ingested_global_submissions
       WHERE submitted_at > now() - interval '7 days'`
    );
    if (parseInt(activeCount) >= MIN_ACTIVE_CONTRIBUTORS) {
      await detectCollusion();
      await detectSoloFabrication();
    }
    // Market price fraud detection runs independently of global contributor count
    await detectMarketPriceOutliers();
    await detectConfidenceClustering();
    await detectLowConfidenceUsers();
  })()
    .catch(err => console.error('[ingestion] Fraud detection failed:', err))
    .finally(() => { _fraudDetectionRunning = false; });
}

// --- Market Price Fraud Detection (Background) ---

/**
 * Flag users whose market price submissions consistently deviate from
 * finalized consensus snapshots. Requires outlier_score to be populated
 * by inline scoring during ingestion.
 */
async function detectMarketPriceOutliers() {
  const { rows: candidates } = await pool.query(`
    SELECT submitted_by,
           count(*) AS total,
           count(*) FILTER (WHERE outlier_score > $1) AS outlier_count,
           round(avg(outlier_score)::numeric, 3) AS avg_outlier
    FROM market_price_submissions
    WHERE submitted_at > now() - interval '7 days'
      AND outlier_score IS NOT NULL
    GROUP BY submitted_by
    HAVING count(*) >= $2
      AND (
        count(*) FILTER (WHERE outlier_score > $1)::numeric / count(*) > $3
        OR avg(outlier_score) > $4
      )
  `, [OUTLIER_FLAG_THRESHOLD, MP_OUTLIER_MIN_SUBMISSIONS, MP_OUTLIER_RATE_THRESHOLD, MP_OUTLIER_SCORE_THRESHOLD]);

  for (const user of candidates) {
    const { rows: existing } = await pool.query(
      `SELECT 1 FROM ingestion_alerts
       WHERE NOT resolved AND type = 'mp_consistent_outlier'
         AND $1 = ANY(user_ids)
       LIMIT 1`,
      [user.submitted_by]
    );
    if (existing.length > 0) continue;

    await pool.query(
      `INSERT INTO ingestion_alerts (type, user_ids, details)
       VALUES ('mp_consistent_outlier', $1, $2)`,
      [
        [user.submitted_by],
        JSON.stringify({
          total_submissions: parseInt(user.total),
          outlier_count: parseInt(user.outlier_count),
          outlier_rate: Math.round(parseInt(user.outlier_count) / parseInt(user.total) * 100),
          avg_outlier_score: parseFloat(user.avg_outlier),
          period: '7 days',
        }),
      ]
    );
  }
}

/**
 * Flag users whose OCR confidence values cluster suspiciously around a
 * single value. Real OCR produces natural variance; a fixed confidence
 * suggests automated/spoofed submissions.
 */
async function detectConfidenceClustering() {
  // Single-pass: bucket confidences to 2 decimal places, find the mode and
  // its count per user in one aggregate query (no self-join).
  const { rows: candidates } = await pool.query(`
    WITH bucketed AS (
      SELECT submitted_by,
             round(confidence::numeric, 2) AS conf_bucket,
             count(*) AS bucket_count
      FROM market_price_submissions
      WHERE submitted_at > now() - interval '7 days'
        AND confidence IS NOT NULL
      GROUP BY submitted_by, round(confidence::numeric, 2)
    ),
    user_totals AS (
      SELECT submitted_by,
             sum(bucket_count) AS total,
             max(bucket_count) AS mode_count
      FROM bucketed
      GROUP BY submitted_by
      HAVING sum(bucket_count) >= $1
    )
    SELECT ut.submitted_by, ut.total, ut.mode_count,
           b.conf_bucket AS mode_conf
    FROM user_totals ut
    JOIN bucketed b ON b.submitted_by = ut.submitted_by
                   AND b.bucket_count = ut.mode_count
    WHERE ut.mode_count::numeric / ut.total > $2
  `, [MP_CONFIDENCE_CLUSTER_MIN, MP_CONFIDENCE_CLUSTER_RATE]);

  for (const user of candidates) {
    const { rows: existing } = await pool.query(
      `SELECT 1 FROM ingestion_alerts
       WHERE NOT resolved AND type = 'mp_confidence_cluster'
         AND $1 = ANY(user_ids)
       LIMIT 1`,
      [user.submitted_by]
    );
    if (existing.length > 0) continue;

    await pool.query(
      `INSERT INTO ingestion_alerts (type, user_ids, details)
       VALUES ('mp_confidence_cluster', $1, $2)`,
      [
        [user.submitted_by],
        JSON.stringify({
          total_submissions: parseInt(user.total),
          mode_confidence: parseFloat(user.mode_conf),
          mode_count: parseInt(user.mode_count),
          mode_pct: Math.round(parseInt(user.mode_count) / parseInt(user.total) * 100),
          period: '7 days',
        }),
      ]
    );
  }
}

/**
 * Flag users whose market price submissions are consistently below the
 * quality threshold (0.85).  The ON CONFLICT upsert in ingestMarketPrices
 * keeps only the best confidence per (user, item, tier, hour), so
 * superseded low-confidence submissions are already excluded — only the
 * user's final best attempt for each slot is evaluated.
 */
async function detectLowConfidenceUsers() {
  const { rows: candidates } = await pool.query(`
    SELECT submitted_by,
           count(*) AS total,
           count(*) FILTER (WHERE confidence < $1) AS low_count,
           round(avg(confidence)::numeric, 3) AS avg_confidence
    FROM market_price_submissions
    WHERE submitted_at > now() - interval '7 days'
      AND confidence IS NOT NULL
    GROUP BY submitted_by
    HAVING count(*) >= $2
      AND count(*) FILTER (WHERE confidence < $1)::numeric / count(*) >= $3
  `, [MP_LOW_CONF_THRESHOLD, MP_LOW_CONF_MIN_SUBMISSIONS, MP_LOW_CONF_RATE_THRESHOLD]);

  for (const user of candidates) {
    const { rows: existing } = await pool.query(
      `SELECT 1 FROM ingestion_alerts
       WHERE NOT resolved AND type = 'mp_low_confidence'
         AND $1 = ANY(user_ids)
       LIMIT 1`,
      [user.submitted_by]
    );
    if (existing.length > 0) continue;

    await pool.query(
      `INSERT INTO ingestion_alerts (type, user_ids, details)
       VALUES ('mp_low_confidence', $1, $2)`,
      [
        [user.submitted_by],
        JSON.stringify({
          total_submissions: parseInt(user.total),
          low_count: parseInt(user.low_count),
          low_rate: Math.round(parseInt(user.low_count) / parseInt(user.total) * 100),
          avg_confidence: parseFloat(user.avg_confidence),
          threshold: MP_LOW_CONF_THRESHOLD,
          period: '7 days',
        }),
      ]
    );
  }
}

// --- Market Price Ingestion ---

const MAX_ITEM_NAME_LENGTH = 200;
const MAX_MARKUP_VALUE = 100_000_000;
const MARKET_PRICE_PERIODS = ['1d', '7d', '30d', '365d', '3650d'];
const MARKET_PRICE_VALUE_COLS = MARKET_PRICE_PERIODS.flatMap(p => [`markup_${p}`, `sales_${p}`]);
const MANUAL_REVIEW_CONFIDENCE_BOOST = 1.5;                // voting weight multiplier
const OUTLIER_FLAG_THRESHOLD = 0.5;                        // per-column deviation to flag
const MARKUP_COLS = MARKET_PRICE_PERIODS.map(p => `markup_${p}`);
const SALES_COLS = MARKET_PRICE_PERIODS.map(p => `sales_${p}`);

// --- Fraud Detection Thresholds (market prices) ---
const MP_OUTLIER_MIN_SUBMISSIONS = 20;   // min submissions to evaluate a user
const MP_OUTLIER_SCORE_THRESHOLD = 0.5;  // avg outlier score to flag
const MP_OUTLIER_RATE_THRESHOLD = 0.4;   // fraction of submissions > 0.5 to flag
const MP_CONFIDENCE_CLUSTER_MIN = 50;    // min submissions to check clustering
const MP_CONFIDENCE_CLUSTER_RATE = 0.90; // 90% at same confidence = suspicious
const MP_LOW_CONF_THRESHOLD = 0.85;     // below this = "low confidence"
const MP_LOW_CONF_MIN_SUBMISSIONS = 20; // min submissions to evaluate a user
const MP_LOW_CONF_RATE_THRESHOLD = 0.50; // flag if ≥50% of submissions are low

let _lastMarketFinalization = 0;
let _marketFinalizationRunning = false;
const MARKET_FINALIZATION_INTERVAL_MS = 60 * 1000; // at most once per minute

/**
 * Validate a single market price entry.
 * @returns {string|null} error message or null if valid
 */
export function validateMarketPrice(entry) {
  if (!entry || typeof entry !== 'object') return 'Not an object';

  // item_name: required, string, 1–200 chars
  if (typeof entry.item_name !== 'string' || entry.item_name.trim().length === 0) return 'Missing item_name';
  if (entry.item_name.length > MAX_ITEM_NAME_LENGTH) return 'item_name too long';

  // item_name_ocr: optional, string — raw OCR read before item matching
  if (entry.item_name_ocr != null) {
    if (typeof entry.item_name_ocr !== 'string') return 'Invalid item_name_ocr';
    if (entry.item_name_ocr.length > MAX_ITEM_NAME_LENGTH) return 'item_name_ocr too long';
  }

  // tier: optional, integer 1–10 or null
  if (entry.tier != null) {
    if (!Number.isInteger(entry.tier) || entry.tier < 0 || entry.tier > 10) return 'Invalid tier';
  }

  // Validate all period columns
  for (const period of MARKET_PRICE_PERIODS) {
    const mu = entry[`markup_${period}`];
    const sales = entry[`sales_${period}`];

    if (mu != null) {
      if (typeof mu !== 'number' || !Number.isFinite(mu)) return `Invalid markup_${period}`;
      // -1 is the overflow sentinel (game displays ">999999%")
      if (mu !== -1 && (mu < 0 || mu > MAX_MARKUP_VALUE)) return `markup_${period} out of range`;
    }
    if (sales != null) {
      if (typeof sales !== 'number' || !Number.isFinite(sales)) return `Invalid sales_${period}`;
      if (sales < 0) return `sales_${period} out of range`;
    }
  }

  // timestamp: required, ISO8601, not future, not older than 24h
  if (!entry.timestamp) return 'Missing timestamp';
  const ts = new Date(entry.timestamp);
  if (isNaN(ts.getTime())) return 'Invalid timestamp';
  const now = Date.now();
  if (ts.getTime() > now + 60_000) return 'Timestamp in the future';
  if (now - ts.getTime() > MAX_EVENT_AGE_MS) return 'Timestamp too old';

  // confidence: optional, number 0.0-1.0
  // Minimum 0.60 — the server accepts low-confidence submissions to track
  // per-user quality patterns.  Snapshot finalization uses confidence-weighted
  // voting, so low-confidence entries have little influence on final values.
  // Manually reviewed submissions bypass the minimum (user corrected values).
  const MIN_CONFIDENCE = 0.60;
  if (entry.confidence != null) {
    if (typeof entry.confidence !== 'number' || !Number.isFinite(entry.confidence)) return 'Invalid confidence';
    if (entry.confidence < 0 || entry.confidence > 1) return 'confidence out of range';
  }
  if (!entry.manually_reviewed && (entry.confidence ?? 0) < MIN_CONFIDENCE) {
    return `Confidence too low (${(entry.confidence ?? 0).toFixed(2)} < ${MIN_CONFIDENCE})`;
  }

  // manually_reviewed: optional, array of field name strings
  if (entry.manually_reviewed != null) {
    if (!Array.isArray(entry.manually_reviewed)) return 'Invalid manually_reviewed';
    if (entry.manually_reviewed.some(f => typeof f !== 'string')) return 'Invalid manually_reviewed entry';
  }

  return null;
}

// --- Market Price Fraud Scoring ---

/**
 * Compute an outlier score for a submission by comparing its values against
 * the latest finalized snapshot for the same item.
 *
 * @returns {{ outlierScore: number|null, fraudFlags: object[]|null }}
 */
async function computeOutlierScore(itemId, entry) {
  let snapshot;
  try {
    const rows = await getLatestMarketPrices([itemId]);
    snapshot = rows?.[0];
  } catch {
    return { outlierScore: null, fraudFlags: null };
  }

  if (!snapshot) return { outlierScore: null, fraudFlags: null };

  // Skip if snapshot is older than 7 days (prices may have legitimately changed)
  const snapshotAge = Date.now() - new Date(snapshot.recorded_at).getTime();
  if (snapshotAge > 7 * 24 * 60 * 60 * 1000) return { outlierScore: null, fraudFlags: null };

  let maxDeviation = 0;
  const flags = [];

  for (const col of MARKUP_COLS) {
    const submitted = entry[col];
    const expected = parseFloat(snapshot[col]);
    if (submitted == null || isNaN(expected)) continue;
    const deviation = Math.min(Math.abs(submitted - expected) / Math.max(Math.abs(expected), 1.0), 1.0);
    if (deviation > maxDeviation) maxDeviation = deviation;
    if (deviation > OUTLIER_FLAG_THRESHOLD) {
      flags.push({ type: 'value_anomaly', col, submitted, expected: parseFloat(expected.toFixed(4)) });
    }
  }

  for (const col of SALES_COLS) {
    const submitted = entry[col];
    const expected = parseFloat(snapshot[col]);
    if (submitted == null || isNaN(expected)) continue;
    const deviation = Math.min(Math.abs(Math.log10(submitted + 1) - Math.log10(expected + 1)) / 3.0, 1.0);
    if (deviation > maxDeviation) maxDeviation = deviation;
    if (deviation > OUTLIER_FLAG_THRESHOLD) {
      flags.push({ type: 'value_anomaly', col, submitted, expected: parseFloat(expected.toFixed(4)) });
    }
  }

  return {
    outlierScore: maxDeviation > 0 ? parseFloat(maxDeviation.toFixed(4)) : null,
    fraudFlags: flags.length > 0 ? flags : null,
  };
}

/**
 * Ingest a batch of market price submissions.
 *
 * Each submission is stored in `market_price_submissions` bucketed by hour.
 * After the hour elapses (+ 5 min grace), a confidence-weighted majority
 * vote finalizes each column into a single authoritative snapshot in
 * `market_price_snapshots`.
 *
 * @param {bigint|string} userId
 * @param {Array} prices
 * @param {Function} resolveItem - async (name, rawName) => { itemId, type?, name? }|number|null
 * @returns {{ accepted: number, duplicates: number, rejected: number }}
 */
export async function ingestMarketPrices(userId, prices, resolveItem) {
  userId = String(userId);
  let accepted = 0, duplicates = 0, rejected = 0;
  const preliminaryPairs = new Map(); // "itemId:tier:hour" → { itemId, tier, bucketHour }

  for (const entry of prices) {
    const ocrName = entry.item_name.trim();
    const rawName = entry.item_name_ocr?.trim() || entry.item_name_raw?.trim() || null;

    let itemId = null;
    let itemType = null;
    let resolvedName = null;
    if (resolveItem) {
      try {
        const resolved = await resolveItem(ocrName, rawName);
        if (resolved && typeof resolved === 'object') {
          itemId = resolved.itemId;
          itemType = resolved.type ?? null;
          resolvedName = resolved.name ?? null;
        } else {
          itemId = resolved;
        }
      } catch {
        // Non-fatal
      }
    }
    if (!itemId) { rejected++; continue; }

    // Force tier to 0 for non-tierable items
    if (entry.tier && entry.tier > 0) {
      const isTierable = itemType && TIERABLE_TYPES.has(itemType);
      if (!isTierable) entry.tier = 0;
    }

    // Bucket to the last full hour
    const entryTs = new Date(entry.timestamp);
    const bucketHour = new Date(entryTs);
    bucketHour.setMinutes(0, 0, 0);

    // Insert submission — on conflict (same user+item+tier+hour), replace with
    // latest data. Manual review always overwrites; otherwise higher
    // confidence wins. Once the hour is finalized (snapshot exists),
    // submissions become read-only — only manual reviews can still update.
    const entryTier = entry.tier ?? 0;
    const { rowCount } = await pool.query(
      `INSERT INTO market_price_submissions
       (item_id, tier, bucket_hour,
        markup_1d, sales_1d, markup_7d, sales_7d,
        markup_30d, sales_30d, markup_365d, sales_365d,
        markup_3650d, sales_3650d,
        submitted_by, confidence, manually_reviewed)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
       ON CONFLICT (item_id, tier, submitted_by, bucket_hour)
       DO UPDATE SET
         markup_1d = EXCLUDED.markup_1d, sales_1d = EXCLUDED.sales_1d,
         markup_7d = EXCLUDED.markup_7d, sales_7d = EXCLUDED.sales_7d,
         markup_30d = EXCLUDED.markup_30d, sales_30d = EXCLUDED.sales_30d,
         markup_365d = EXCLUDED.markup_365d, sales_365d = EXCLUDED.sales_365d,
         markup_3650d = EXCLUDED.markup_3650d, sales_3650d = EXCLUDED.sales_3650d,
         confidence = EXCLUDED.confidence,
         manually_reviewed = EXCLUDED.manually_reviewed,
         submitted_at = now()
       WHERE (
         EXCLUDED.manually_reviewed IS NOT NULL
         OR (
           NOT EXISTS (
             SELECT 1 FROM ONLY market_price_snapshots snap
             WHERE snap.item_id = EXCLUDED.item_id
               AND snap.tier = EXCLUDED.tier
               AND snap.recorded_at = EXCLUDED.bucket_hour
               AND snap.finalized_at IS NOT NULL
           )
           AND COALESCE(EXCLUDED.confidence, 0) >= COALESCE(market_price_submissions.confidence, 0)
         )
       )`,
      [
        itemId,
        entryTier,
        bucketHour.toISOString(),
        entry.markup_1d ?? null, entry.sales_1d ?? null,
        entry.markup_7d ?? null, entry.sales_7d ?? null,
        entry.markup_30d ?? null, entry.sales_30d ?? null,
        entry.markup_365d ?? null, entry.sales_365d ?? null,
        entry.markup_3650d ?? null, entry.sales_3650d ?? null,
        userId,
        entry.confidence ?? null,
        entry.manually_reviewed ? JSON.stringify(entry.manually_reviewed) : null,
      ]
    );

    if (rowCount > 0) {
      accepted++;
      const pairKey = `${itemId}:${entryTier}:${bucketHour.toISOString()}`;
      if (!preliminaryPairs.has(pairKey)) {
        preliminaryPairs.set(pairKey, { itemId, tier: entryTier, bucketHour: new Date(bucketHour) });
      }

      // Compute outlier score against latest snapshot (non-blocking best-effort)
      computeOutlierScore(itemId, entry).then(({ outlierScore, fraudFlags }) => {
        if (outlierScore == null && fraudFlags == null) return;
        pool.query(
          `UPDATE market_price_submissions
           SET outlier_score = $1, fraud_flags = $2
           WHERE item_id = $3 AND tier = $4 AND submitted_by = $5 AND bucket_hour = $6`,
          [outlierScore, fraudFlags ? JSON.stringify(fraudFlags) : null, itemId, entryTier, userId, bucketHour.toISOString()]
        ).catch(err => console.error('[ingestion] Failed to store outlier score:', err.message));
      }).catch(() => {});
    } else {
      duplicates++;
    }

    // Late manual review for an already-finalized hour → re-finalize
    if (entry.manually_reviewed) {
      const currentBucket = new Date();
      currentBucket.setMinutes(0, 0, 0);
      if (bucketHour < currentBucket) {
        try { await finalizeMarketPriceHour(itemId, entryTier, bucketHour); } catch { /* non-fatal */ }
      }
    }
  }

  // Fire-and-forget: create preliminary snapshots for this batch immediately
  // (bypasses global throttle since it's scoped to accepted items only)
  if (preliminaryPairs.size > 0) {
    void (async () => {
      for (const { itemId: id, tier: t, bucketHour: bh } of preliminaryPairs.values()) {
        try { await finalizeMarketPriceHour(id, t, bh); } catch { /* non-fatal */ }
      }
    })().catch(() => {});
  }

  // Fire-and-forget: finalize any other pending hours
  maybeRunMarketFinalization();

  return { accepted, duplicates, rejected };
}

// --- Market Price Finalization ---

/**
 * Finalize a single (item_id, tier, bucket_hour) into an authoritative snapshot.
 *
 * For each value column, computes a confidence-weighted majority vote.
 * Manually reviewed submissions get a 1.5× confidence boost.
 * Result is upserted into market_price_snapshots.
 */
async function finalizeMarketPriceHour(itemId, tier, bucketHour) {
  const { rows: submissions } = await pool.query(
    `SELECT * FROM market_price_submissions
     WHERE item_id = $1 AND tier = $2 AND bucket_hour = $3`,
    [itemId, tier, bucketHour]
  );

  if (submissions.length === 0) return;

  const result = {};

  // Confidence-weighted majority vote for each value column
  for (const col of MARKET_PRICE_VALUE_COLS) {
    const votes = new Map(); // stringified value → total weight
    for (const sub of submissions) {
      const val = sub[col];
      if (val == null) continue;
      const key = String(val);
      const conf = parseFloat(sub.confidence ?? 0.5);
      const boost = sub.manually_reviewed ? MANUAL_REVIEW_CONFIDENCE_BOOST : 1.0;
      votes.set(key, (votes.get(key) || 0) + conf * boost);
    }
    if (votes.size === 0) {
      result[col] = null;
      continue;
    }
    let bestKey = null, bestWeight = -1;
    for (const [key, weight] of votes) {
      if (weight > bestWeight) { bestKey = key; bestWeight = weight; }
    }
    result[col] = parseFloat(bestKey);
  }

  // Best submitter = highest raw confidence
  let bestConfidence = 0, bestSubmitter = null;
  for (const sub of submissions) {
    const conf = parseFloat(sub.confidence ?? 0);
    if (conf > bestConfidence) {
      bestConfidence = conf;
      bestSubmitter = sub.submitted_by;
    }
  }
  if (!bestSubmitter) bestSubmitter = submissions[0].submitted_by;

  // Aggregate manually_reviewed fields across all submissions
  const allReviewed = new Set();
  for (const sub of submissions) {
    if (Array.isArray(sub.manually_reviewed)) {
      for (const field of sub.manually_reviewed) allReviewed.add(field);
    }
  }

  // Upsert snapshot (ON CONFLICT updates if re-finalizing)
  await pool.query(
    `INSERT INTO market_price_snapshots
     (item_id, tier, markup_1d, sales_1d, markup_7d, sales_7d,
      markup_30d, sales_30d, markup_365d, sales_365d, markup_3650d, sales_3650d,
      recorded_at, submitted_by, confidence, manually_reviewed,
      finalized_at, submission_count)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,now(),$17)
     ON CONFLICT (item_id, tier, recorded_at) WHERE item_id IS NOT NULL
     DO UPDATE SET
       markup_1d = EXCLUDED.markup_1d, sales_1d = EXCLUDED.sales_1d,
       markup_7d = EXCLUDED.markup_7d, sales_7d = EXCLUDED.sales_7d,
       markup_30d = EXCLUDED.markup_30d, sales_30d = EXCLUDED.sales_30d,
       markup_365d = EXCLUDED.markup_365d, sales_365d = EXCLUDED.sales_365d,
       markup_3650d = EXCLUDED.markup_3650d, sales_3650d = EXCLUDED.sales_3650d,
       submitted_by = EXCLUDED.submitted_by,
       confidence = EXCLUDED.confidence,
       manually_reviewed = EXCLUDED.manually_reviewed,
       finalized_at = now(),
       submission_count = EXCLUDED.submission_count`,
    [
      itemId, tier,
      result.markup_1d, result.sales_1d,
      result.markup_7d, result.sales_7d,
      result.markup_30d, result.sales_30d,
      result.markup_365d, result.sales_365d,
      result.markup_3650d, result.sales_3650d,
      bucketHour,
      bestSubmitter,
      bestConfidence,
      allReviewed.size > 0 ? JSON.stringify([...allReviewed]) : null,
      submissions.length,
    ]
  );

  // Invalidate cached query results for this item
  invalidateMarketPriceCache(itemId);
}

/**
 * Finalize all pending hours across all items (including current hour).
 * Creates preliminary snapshots for the current hour and definitive ones
 * for past hours. Re-finalizes any snapshot with newer submissions.
 */
async function finalizeAllPendingHours() {
  // Find (item_id, tier, bucket_hour) triples needing finalization
  const { rows: pending } = await pool.query(`
    SELECT DISTINCT s.item_id, s.tier, s.bucket_hour
    FROM market_price_submissions s
    WHERE s.bucket_hour <= date_trunc('hour', now())
      AND (
        NOT EXISTS (
          SELECT 1 FROM ONLY market_price_snapshots snap
          WHERE snap.item_id = s.item_id AND snap.tier = s.tier
            AND snap.recorded_at = s.bucket_hour
        )
        OR EXISTS (
          SELECT 1 FROM market_price_submissions s2
          WHERE s2.item_id = s.item_id AND s2.tier = s.tier
            AND s2.bucket_hour = s.bucket_hour
            AND s2.submitted_at > (
              SELECT snap2.finalized_at FROM ONLY market_price_snapshots snap2
              WHERE snap2.item_id = s.item_id AND snap2.tier = s.tier
                AND snap2.recorded_at = s.bucket_hour
            )
        )
      )
    LIMIT 200
  `);

  for (const { item_id, tier, bucket_hour } of pending) {
    try {
      await finalizeMarketPriceHour(item_id, tier, bucket_hour);
    } catch (err) {
      console.error(`[ingestion] Failed to finalize market price hour item=${item_id} tier=${tier} hour=${bucket_hour}:`, err.message);
    }
  }
}

/**
 * Fire-and-forget market price finalization, throttled to once per minute.
 * Exported for stale-while-revalidate use by the snapshots API endpoint.
 */
export function maybeRunMarketFinalization() {
  const now = Date.now();
  if (_marketFinalizationRunning || now - _lastMarketFinalization < MARKET_FINALIZATION_INTERVAL_MS) return;
  _lastMarketFinalization = now;
  _marketFinalizationRunning = true;

  void finalizeAllPendingHours()
    .catch(err => console.error('[ingestion] Market finalization failed:', err))
    .finally(() => { _marketFinalizationRunning = false; });
}

