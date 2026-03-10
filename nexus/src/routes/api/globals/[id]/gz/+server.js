// @ts-nocheck
/**
 * POST /api/globals/[id]/gz — Toggle GZ (congrats) on a global.
 * GET  /api/globals/[id]/gz — Get GZ count and user's GZ status.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

const RATE_LIMIT_MAX = 60;
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const globalId = parseInt(params.id);
  if (isNaN(globalId)) {
    return getResponse({ error: 'Invalid global ID.' }, 400);
  }

  const userId = String(user.Id || user.id);

  const rateCheck = checkRateLimit(`gz:${userId}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please slow down.' }, 429);
  }

  // Verify global exists
  const { rows: globalRows } = await pool.query(
    `SELECT id FROM ingested_globals WHERE id = $1 AND confirmed = true`,
    [globalId]
  );
  if (globalRows.length === 0) {
    return getResponse({ error: 'Global not found.' }, 404);
  }

  // Atomic toggle using CTE to avoid race conditions
  const { rows } = await pool.query(
    `WITH deleted AS (
       DELETE FROM globals_gz
       WHERE global_id = $1 AND user_id = $2
       RETURNING 1
     ),
     inserted AS (
       INSERT INTO globals_gz (global_id, user_id)
       SELECT $1, $2
       WHERE NOT EXISTS (SELECT 1 FROM deleted)
       ON CONFLICT DO NOTHING
       RETURNING 1
     )
     SELECT
       EXISTS (SELECT 1 FROM inserted) AS user_gz,
       (
         (SELECT COUNT(*)::int FROM globals_gz WHERE global_id = $1)
         - (SELECT COUNT(*)::int FROM deleted)
         + (SELECT COUNT(*)::int FROM inserted)
       ) AS gz_count`,
    [globalId, userId]
  );

  return getResponse({
    gz_count: rows[0].gz_count,
    user_gz: rows[0].user_gz,
  });
}

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, locals }) {
  const globalId = parseInt(params.id);
  if (isNaN(globalId)) {
    return getResponse({ error: 'Invalid global ID.' }, 400);
  }

  const userId = locals.session?.user ? String(locals.session.user.Id || locals.session.user.id) : null;

  const { rows: countRows } = await pool.query(
    `SELECT COUNT(*)::int AS gz_count FROM globals_gz WHERE global_id = $1`,
    [globalId]
  );

  let userGz = false;
  if (userId) {
    const { rows } = await pool.query(
      `SELECT 1 FROM globals_gz WHERE global_id = $1 AND user_id = $2`,
      [globalId, userId]
    );
    userGz = rows.length > 0;
  }

  return getResponse({
    gz_count: countRows[0].gz_count,
    user_gz: userGz,
  });
}
