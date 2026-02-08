/**
 * API endpoint for serving entity images.
 * Serves approved images with proper caching headers.
 *
 * GET /api/img/:entityType/:entityId - Serves the icon image
 * GET /api/img/:entityType/:entityId?type=thumb - Serves the thumbnail
 */
import { getApprovedImagePath } from '$lib/server/imageProcessor.js';
import { existsSync, statSync } from 'fs';
import { readFile } from 'fs/promises';

// Valid entity types to prevent path traversal
const VALID_ENTITY_TYPES = [
  'weapon', 'armorset', 'material', 'blueprint', 'clothing',
  'consumable', 'tool', 'attachment', 'medicaltool', 'vehicle',
  'pet', 'furnishing', 'strongbox', 'mob', 'skill', 'profession', 'vendor',
  'teleporter', 'apartment', 'area', 'user', 'guide-category', 'richtext'
];

// Cache duration: 1 day for approved images (they rarely change)
const CACHE_MAX_AGE = 86400;

export async function GET({ params, url }) {
  const { entityType, entityId } = params;
  const type = url.searchParams.get('type') || 'icon';

  // Validate entity type
  if (!entityType || !VALID_ENTITY_TYPES.includes(entityType.toLowerCase())) {
    return new Response('Invalid entity type', { status: 400 });
  }

  // Validate type parameter
  if (type !== 'icon' && type !== 'thumb') {
    return new Response('Invalid type. Must be "icon" or "thumb"', { status: 400 });
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

    // Generate ETag from file stats
    const etag = `"${stats.size}-${stats.mtimeMs}"`;

    return new Response(imageBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(imageBuffer.length),
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
