/**
 * API endpoint to serve approved images.
 */
import { error } from '@sveltejs/kit';
import { getApprovedImagePath, isValidEntityType } from '$lib/server/imageProcessor.js';
import { readFile } from 'fs/promises';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, url }) {
  const { entityType, entityId } = params;
  const type = url.searchParams.get('type') || 'icon';

  if (!entityType || !entityId) {
    throw error(400, 'Entity type and ID are required');
  }

  if (!isValidEntityType(entityType)) {
    throw error(400, 'Invalid entity type');
  }

  if (!/^[\w\s\-]+$/.test(entityId) || entityId.length > 200) {
    throw error(400, 'Invalid entity ID');
  }

  if (!['icon', 'thumb'].includes(type)) {
    throw error(400, 'Type must be "icon" or "thumb"');
  }

  try {
    const imagePath = getApprovedImagePath(entityType, entityId, type);

    if (!imagePath) {
      throw error(404, 'Image not found');
    }

    const imageBuffer = await readFile(imagePath);

    return new Response(new Uint8Array(imageBuffer), {
      headers: {
        'Content-Type': 'image/webp',
        'Cache-Control': 'public, max-age=86400' // 24 hours
      }
    });
  } catch (/** @type {any} */ err) {
    if (err.status) {
      throw err;
    }
    throw error(500, 'Failed to retrieve image');
  }
}
