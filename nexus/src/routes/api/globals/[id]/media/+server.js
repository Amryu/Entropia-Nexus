// @ts-nocheck
/**
 * POST /api/globals/[id]/media — Upload screenshot or submit video link for a global.
 * DELETE /api/globals/[id]/media — Remove media (uploader or admin only).
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import {
  processAndSaveImage,
  approveImage,
} from '$lib/server/imageProcessor.js';
import { deleteR2Prefix } from '$lib/server/r2Storage.js';
import {
  checkRateLimit,
  checkConcurrentUploads,
  startUpload,
  endUpload,
} from '$lib/server/rateLimiter.js';
import { parseVideoUrl, SUPPORTED_PLATFORM_NAMES } from '$lib/utils/videoEmbed.js';

const MONTHLY_IMAGE_LIMIT = 100;
const MAX_REQUEST_SIZE = 5 * 1024 * 1024; // 5MB for screenshots
const RATE_LIMIT_MAX = 10;
const RATE_LIMIT_WINDOW = 5 * 60 * 1000; // 5 minutes
const MAX_CONCURRENT = 2;

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
    // --- Image upload ---
    const rateCheck = checkRateLimit(`global-media:${userId}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
    if (!rateCheck.allowed) {
      return getResponse({ error: 'Too many upload requests. Please try again later.' }, 429);
    }
    if (!checkConcurrentUploads(userId, MAX_CONCURRENT)) {
      return getResponse({ error: 'Too many concurrent uploads.' }, 429);
    }

    // Monthly budget check
    const { rows: budgetRows } = await pool.query(
      `SELECT COUNT(*) AS cnt FROM ingested_globals
       WHERE media_uploaded_by = $1 AND media_image_key IS NOT NULL
       AND date_trunc('month', media_uploaded_at) = date_trunc('month', NOW())`,
      [userId]
    );
    const imageCount = parseInt(budgetRows[0].cnt);
    if (imageCount >= MONTHLY_IMAGE_LIMIT) {
      return getResponse({
        error: `Monthly screenshot upload limit reached (${MONTHLY_IMAGE_LIMIT}).`,
        budget: { images: { used: imageCount, limit: MONTHLY_IMAGE_LIMIT } },
      }, 429);
    }

    // Content-Length pre-check
    const cl = request.headers.get('content-length');
    if (cl && parseInt(cl) > MAX_REQUEST_SIZE) {
      return getResponse({ error: 'Image too large. Maximum 5MB.' }, 413);
    }

    startUpload(userId);
    try {
      let formData;
      try {
        formData = await request.formData();
      } catch {
        return getResponse({ error: 'Invalid form data.' }, 400);
      }

      const imageFile = formData.get('image');
      if (!imageFile || !(imageFile instanceof File)) {
        return getResponse({ error: 'Image file is required.' }, 400);
      }

      const arrayBuffer = await imageFile.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);

      // Process and auto-approve (global is an auto-approve type)
      await processAndSaveImage(buffer, 'global', String(globalId), userId);
      await approveImage('global', String(globalId));

      // Update the global record
      const r2Key = `global/${globalId}/icon.webp`;
      await pool.query(
        `UPDATE ingested_globals
         SET media_image_key = $1, media_uploaded_by = $2, media_uploaded_at = NOW()
         WHERE id = $3`,
        [r2Key, userId, globalId]
      );

      return getResponse({
        success: true,
        media_type: 'image',
        budget_remaining: MONTHLY_IMAGE_LIMIT - imageCount - 1,
      }, 200);
    } catch (err) {
      console.error('[api/globals/media] Image upload error:', err);
      return getResponse({ error: 'Failed to upload image.' }, 500);
    } finally {
      endUpload(userId);
    }
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
