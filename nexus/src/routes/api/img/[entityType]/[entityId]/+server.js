/**
 * API endpoint for serving entity images.
 * Serves approved images with proper caching headers.
 *
 * GET /api/img/:entityType/:entityId - Serves the icon image
 * GET /api/img/:entityType/:entityId?type=thumb - Serves the thumbnail
 * GET /api/img/:entityType/:entityId?mode=dark|light - Enhanced icon with trim/scale/backdrop
 */
import { getApprovedImagePath, isValidEntityType } from '$lib/server/imageProcessor.js';
import { enhanceEntityImage } from '$lib/server/imageEnhancer.js';
import { existsSync, statSync } from 'fs';
import { readFile } from 'fs/promises';

// Cache duration: 1 day for approved images (they rarely change)
const CACHE_MAX_AGE = 86400;

const VALID_MODES = ['dark', 'light'];

export async function GET({ params, url }) {
  const { entityType, entityId } = params;
  const type = url.searchParams.get('type') || 'icon';
  const mode = url.searchParams.get('mode');

  // Validate entity type
  if (!isValidEntityType(entityType)) {
    return new Response('Invalid entity type', { status: 400 });
  }

  // Validate type parameter
  if (type !== 'icon' && type !== 'thumb') {
    return new Response('Invalid type. Must be "icon" or "thumb"', { status: 400 });
  }

  // Validate mode parameter (optional)
  if (mode !== null && !VALID_MODES.includes(mode)) {
    return new Response('Invalid mode. Must be "dark" or "light"', { status: 400 });
  }

  // Validate entity ID (prevent path traversal)
  if (!entityId || !/^[\w\s\-]+$/.test(entityId) || entityId.length > 200) {
    return new Response('Invalid entity ID', { status: 400 });
  }

  // Get the image path
  const imagePath = getApprovedImagePath(entityType.toLowerCase(), entityId, type);

  if (!imagePath || !existsSync(imagePath)) {
    // Return 204 No Content instead of 404 to avoid console spam
    // Client can still detect missing image by checking response status
    return new Response(null, { status: 204 });
  }

  try {
    const stats = statSync(imagePath);
    const imageBuffer = await readFile(imagePath);

    // Apply enhancement pipeline for icons when mode is specified
    let outputBuffer = imageBuffer;
    if (mode && type === 'icon') {
      outputBuffer = await enhanceEntityImage(imageBuffer, mode);
    }

    // Include mode in ETag so CDN caches dark/light variants separately
    const etagBase = `${stats.size}-${stats.mtimeMs}`;
    const etag = mode ? `"${etagBase}-${mode}"` : `"${etagBase}"`;

    return new Response(outputBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(outputBuffer.length),
        'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
        'ETag': etag,
        'Last-Modified': stats.mtime.toUTCString()
      }
    });
  } catch (error) {
    console.error('Error serving image:', error);
    return new Response('Error serving image', { status: 500 });
  }
}
