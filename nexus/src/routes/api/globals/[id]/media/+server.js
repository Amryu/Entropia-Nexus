// @ts-nocheck
/**
 * POST /api/globals/[id]/media — Upload screenshot or submit video link for a global.
 * DELETE /api/globals/[id]/media — Remove media (uploader or admin only).
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { deleteR2Prefix } from '$lib/server/r2Storage.js';
import { parseVideoUrl, SUPPORTED_PLATFORM_NAMES } from '$lib/utils/videoEmbed.js';

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

  // Verify the global exists and is confirmed
  const { rows: globalRows } = await pool.query(
    `SELECT id, player_name, media_image_key, media_video_url
     FROM ingested_globals WHERE id = $1 AND confirmed = true`,
    [globalId]
  );
  if (globalRows.length === 0) {
    return getResponse({ error: 'Global not found.' }, 404);
  }
  if (globalRows[0].media_image_key || globalRows[0].media_video_url) {
    return getResponse({ error: 'This global already has media attached.' }, 409);
  }

  // Only allow uploading media for the user's own globals
  const euName = user.eu_name;
  const isAdmin = user.grants?.includes('admin.panel');
  if (!isAdmin) {
    if (!euName || euName.toLowerCase() !== (globalRows[0].player_name || '').toLowerCase()) {
      return getResponse({ error: 'You can only upload media for your own globals.' }, 403);
    }
  }

  // Determine media type from Content-Type
  const contentType = request.headers.get('content-type') || '';
  const isFormData = contentType.includes('multipart/form-data');
  const isJson = contentType.includes('application/json');

  if (isFormData) {
    // --- Image upload (temporarily disabled) ---
    return getResponse({ error: 'Image uploads are currently disabled.' }, 403);
  } else if (isJson) {
    // --- Video link ---
    let body;
    try {
      body = await request.json();
    } catch {
      return getResponse({ error: 'Invalid JSON body.' }, 400);
    }

    const videoInput = body.video_url || body.youtube_url;
    const parsed = parseVideoUrl(videoInput);
    if (!parsed) {
      return getResponse({
        error: `Invalid or unsupported video URL. Supported platforms: ${SUPPORTED_PLATFORM_NAMES.join(', ')}.`,
      }, 400);
    }

    try {
      await pool.query(
        `UPDATE ingested_globals
         SET media_video_url = $1, media_uploaded_by = $2, media_uploaded_at = NOW()
         WHERE id = $3`,
        [parsed.originalUrl, userId, globalId]
      );

      return getResponse({
        success: true,
        media_type: 'video',
        platform: parsed.platform,
      }, 200);
    } catch (err) {
      console.error('[api/globals/media] Video link error:', err);
      return getResponse({ error: 'Failed to save video link.' }, 500);
    }
  } else {
    return getResponse({ error: 'Unsupported content type. Use multipart/form-data for images or application/json for video links.' }, 400);
  }
}

/** @type {import('./$types').RequestHandler} */
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const globalId = parseInt(params.id);
  if (isNaN(globalId)) {
    return getResponse({ error: 'Invalid global ID.' }, 400);
  }

  const userId = String(user.Id || user.id);
  const isAdmin = user?.grants?.includes('admin.panel');

  // Fetch current media info
  const { rows } = await pool.query(
    `SELECT media_image_key, media_video_url, media_uploaded_by
     FROM ingested_globals WHERE id = $1`,
    [globalId]
  );
  if (rows.length === 0) {
    return getResponse({ error: 'Global not found.' }, 404);
  }

  const row = rows[0];
  if (!row.media_image_key && !row.media_video_url) {
    return getResponse({ error: 'No media attached to this global.' }, 404);
  }

  // Only the uploader or admin can delete
  if (String(row.media_uploaded_by) !== userId && !isAdmin) {
    return getResponse({ error: 'You can only remove media you uploaded.' }, 403);
  }

  try {
    // Clear media columns
    await pool.query(
      `UPDATE ingested_globals
       SET media_image_key = NULL, media_video_url = NULL,
           media_uploaded_by = NULL, media_uploaded_at = NULL
       WHERE id = $1`,
      [globalId]
    );

    // Delete R2 objects if it was an image
    if (row.media_image_key) {
      deleteR2Prefix(`global/${globalId}/`)
        .catch(err => console.error(`[R2] Delete failed for global/${globalId}:`, err?.message));
    }

    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('[api/globals/media] Delete error:', err);
    return getResponse({ error: 'Failed to remove media.' }, 500);
  }
}
