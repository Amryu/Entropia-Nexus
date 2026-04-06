//@ts-nocheck
import crypto from 'node:crypto';
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { checkRateLimit, checkConcurrentUploads, startUpload, endUpload } from '$lib/server/rateLimiter.js';
import { isIngestionAllowed, isIngestionBanned, parseRequestBody } from '$lib/server/ingestion.js';
import { pool } from '$lib/server/db.js';

const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW = 60_000;
const MAX_GAIN_EVENTS = 50_000;
const MAX_SKILL_VALUES = 300;

// Salt for contributor hash — set in environment
const HASH_SALT = process.env.SKILL_DATA_HASH_SALT || 'skill-data-default-salt';

// Reasonable timestamp bounds (2020-01-01 to 2030-01-01)
const MIN_TS = 1577836800;
const MAX_TS = 1893456000;

function hashContributor(userId) {
  return crypto.createHash('sha256').update(String(userId) + HASH_SALT).digest('hex');
}

function validateGainEvent(e) {
  if (typeof e.ts !== 'number' || e.ts < MIN_TS || e.ts > MAX_TS) return 'invalid ts';
  if (typeof e.skill_id !== 'number' || e.skill_id < 1) return 'invalid skill_id';
  if (typeof e.amount !== 'number' || e.amount <= 0 || e.amount > 1000) return 'invalid amount';
  return null;
}

/**
 * POST /api/ingestion/skill-data — Submit anonymized skill data.
 * Accepts "snapshot" (skill values + gain history) or "delta" (gain events only).
 */
export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  const isAdmin = user.grants?.includes('admin.panel');
  if (!isAdmin) {
    const rl = checkRateLimit(`ingest-skill-data:${user.id}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
    if (!rl.allowed) {
      return getResponse(
        { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
        429
      );
    }
  }

  const uploadKey = `ingest-skill-data:${user.id}`;
  if (!checkConcurrentUploads(uploadKey, 1)) {
    return getResponse({ error: 'Concurrent upload in progress' }, 409);
  }
  startUpload(uploadKey);

  try {
    if (!(await isIngestionAllowed(locals.oauthClientId || null))) {
      return getResponse({ error: 'This application is not authorized for ingestion' }, 403);
    }
    if (await isIngestionBanned(user.id)) {
      return getResponse({ error: 'Ingestion access revoked' }, 403);
    }

    let body;
    try {
      body = await parseRequestBody(request);
    } catch (e) {
      return getResponse({ error: 'Invalid request body' }, 400);
    }

    const { type } = body;
    if (type !== 'snapshot' && type !== 'delta') {
      return getResponse({ error: 'type must be "snapshot" or "delta"' }, 400);
    }

    // Validate gains
    const gains = body.gains;
    if (!Array.isArray(gains)) {
      return getResponse({ error: 'Missing gains array' }, 400);
    }
    if (gains.length > MAX_GAIN_EVENTS) {
      return getResponse({ error: `Too many gain events (max ${MAX_GAIN_EVENTS})` }, 400);
    }

    const validGains = [];
    for (const g of gains) {
      const err = validateGainEvent(g);
      if (!err) validGains.push(g);
    }

    // Validate skills (snapshot only)
    let skillEntries = [];
    if (type === 'snapshot') {
      const skills = body.skills;
      if (!skills || typeof skills !== 'object') {
        return getResponse({ error: 'snapshot requires skills object' }, 400);
      }
      skillEntries = Object.entries(skills);
      if (skillEntries.length > MAX_SKILL_VALUES) {
        return getResponse({ error: `Too many skill values (max ${MAX_SKILL_VALUES})` }, 400);
      }
      for (const [id, val] of skillEntries) {
        if (isNaN(Number(id)) || typeof val !== 'number' || val < 0) {
          return getResponse({ error: `Invalid skill entry: ${id}=${val}` }, 400);
        }
      }
    }

    // Hash the user ID — this is the ONLY identifier stored
    const contributorHash = hashContributor(user.id);

    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      // Upsert contributor
      const { rows: [contributor] } = await client.query(
        `INSERT INTO skill_data_contributors (contributor_hash)
         VALUES ($1)
         ON CONFLICT (contributor_hash) DO UPDATE SET last_upload_at = now()
         RETURNING id`,
        [contributorHash]
      );
      const contributorId = contributor.id;

      let batchId = null;
      const clientVersion = body.client_version || null;

      if (type === 'snapshot') {
        // Insert snapshot
        const scanTs = body.scan_timestamp
          ? new Date(body.scan_timestamp * 1000).toISOString()
          : new Date().toISOString();

        const { rows: [snapshot] } = await client.query(
          `INSERT INTO skill_data_snapshots (contributor_id, scan_timestamp, client_version)
           VALUES ($1, $2, $3)
           RETURNING id`,
          [contributorId, scanTs, clientVersion]
        );
        batchId = snapshot.id;

        // Insert skill values
        if (skillEntries.length > 0) {
          const valuesClause = skillEntries.map((_, i) =>
            `($1, $${i * 2 + 2}, $${i * 2 + 3})`
          ).join(', ');
          const params = [snapshot.id];
          for (const [id, val] of skillEntries) {
            params.push(Number(id), val);
          }
          await client.query(
            `INSERT INTO skill_data_snapshot_values (snapshot_id, skill_id, current_points)
             VALUES ${valuesClause}`,
            params
          );
        }

        await client.query(
          `UPDATE skill_data_contributors SET snapshot_count = snapshot_count + 1
           WHERE id = $1`,
          [contributorId]
        );
      } else {
        await client.query(
          `UPDATE skill_data_contributors SET delta_count = delta_count + 1
           WHERE id = $1`,
          [contributorId]
        );
      }

      // Insert gain events in batches of 500
      const CHUNK_SIZE = 500;
      for (let i = 0; i < validGains.length; i += CHUNK_SIZE) {
        const chunk = validGains.slice(i, i + CHUNK_SIZE);
        const valuesClause = chunk.map((_, j) =>
          `($1, to_timestamp($${j * 3 + 2}), $${j * 3 + 3}, $${j * 3 + 4}, $5)`
        ).join(', ');
        const params = [contributorId];
        for (const g of chunk) {
          params.push(g.ts, g.skill_id, g.amount);
        }
        params.push(batchId);
        await client.query(
          `INSERT INTO skill_data_gain_events (contributor_id, event_ts, skill_id, amount, batch_id)
           VALUES ${valuesClause}`,
          params
        );
      }

      // Record the upload batch for dedup
      const minTs = validGains.length > 0
        ? new Date(validGains[0].ts * 1000).toISOString()
        : null;
      const maxTs = validGains.length > 0
        ? new Date(validGains[validGains.length - 1].ts * 1000).toISOString()
        : null;

      await client.query(
        `INSERT INTO skill_data_upload_batches
         (contributor_id, upload_type, min_event_ts, max_event_ts, event_count, client_version)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [contributorId, type, minTs, maxTs, validGains.length, clientVersion]
      );

      await client.query('COMMIT');

      return getResponse({
        accepted: true,
        type,
        skills_stored: skillEntries.length,
        events_stored: validGains.length,
      }, 200);

    } catch (e) {
      await client.query('ROLLBACK').catch(() => {});
      throw e;
    } finally {
      client.release();
    }

  } catch (e) {
    console.error('[ingestion] Failed to ingest skill data:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    endUpload(uploadKey);
  }
}
