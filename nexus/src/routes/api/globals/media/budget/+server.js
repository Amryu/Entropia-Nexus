// @ts-nocheck
/**
 * GET /api/globals/media/budget — Get the authenticated user's monthly media upload budget.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

const MONTHLY_IMAGE_LIMIT = 100;
const MONTHLY_VIDEO_LIMIT = 30;

/** @type {import('./$types').RequestHandler} */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const userId = String(user.Id || user.id);

  try {
    const { rows } = await pool.query(
      `SELECT
         COUNT(*) FILTER (WHERE media_image_key IS NOT NULL) AS image_count,
         COUNT(*) FILTER (WHERE media_video_url IS NOT NULL) AS video_count
       FROM ingested_globals
       WHERE media_uploaded_by = $1
         AND date_trunc('month', media_uploaded_at) = date_trunc('month', NOW())`,
      [userId]
    );

    const imageUsed = parseInt(rows[0].image_count);
    const videoUsed = parseInt(rows[0].video_count);

    return new Response(JSON.stringify({
      images: {
        used: imageUsed,
        limit: MONTHLY_IMAGE_LIMIT,
        remaining: Math.max(0, MONTHLY_IMAGE_LIMIT - imageUsed),
      },
      videos: {
        used: videoUsed,
        limit: MONTHLY_VIDEO_LIMIT,
        remaining: Math.max(0, MONTHLY_VIDEO_LIMIT - videoUsed),
      },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    console.error('[api/globals/media/budget] Error:', err);
    return getResponse({ error: 'Internal server error.' }, 500);
  }
}
