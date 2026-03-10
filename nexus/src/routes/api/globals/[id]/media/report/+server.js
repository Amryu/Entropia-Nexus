// @ts-nocheck
/**
 * POST /api/globals/[id]/media/report — Report inappropriate media on a global.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

const RATE_LIMIT_MAX = 20;
const RATE_LIMIT_WINDOW = 60 * 60 * 1000; // 1 hour
const MAX_REASON_LENGTH = 500;

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const globalId = parseInt(params.id);
  if (isNaN(globalId)) {
    return getResponse({ error: 'Invalid global ID.' }, 400);
  }

  const userId = String(user.Id || user.id);

  const rateCheck = checkRateLimit(`media-report:${userId}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many reports. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON body.' }, 400);
  }

  const reason = (body.reason || '').trim();
  if (!reason) {
    return getResponse({ error: 'A reason is required.' }, 400);
  }
  if (reason.length > MAX_REASON_LENGTH) {
    return getResponse({ error: `Reason must be under ${MAX_REASON_LENGTH} characters.` }, 400);
  }

  // Verify global has media
  const { rows: globalRows } = await pool.query(
    `SELECT media_image_key, media_video_url, media_uploaded_by
     FROM ingested_globals WHERE id = $1`,
    [globalId]
  );
  if (globalRows.length === 0) {
    return getResponse({ error: 'Global not found.' }, 404);
  }

  const g = globalRows[0];
  if (!g.media_image_key && !g.media_video_url) {
    return getResponse({ error: 'This global has no media to report.' }, 400);
  }

  // Cannot report own upload
  if (String(g.media_uploaded_by) === userId) {
    return getResponse({ error: 'You cannot report your own media.' }, 400);
  }

  try {
    await pool.query(
      `INSERT INTO globals_media_reports (global_id, reporter_id, reason)
       VALUES ($1, $2, $3)
       ON CONFLICT (global_id, reporter_id) DO UPDATE SET reason = $3, created_at = NOW()`,
      [globalId, userId, reason]
    );

    return getResponse({ success: true });
  } catch (err) {
    console.error('[api/globals/media/report] Error:', err);
    return getResponse({ error: 'Failed to submit report.' }, 500);
  }
}
