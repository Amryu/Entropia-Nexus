/**
 * API endpoint to serve preview images from temp storage.
 */
import { error } from '@sveltejs/kit';
import { getPreviewImage } from '$lib/server/imageProcessor.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, url }) {
  const { tempId } = params;
  const type = url.searchParams.get('type') || 'icon';

  if (!tempId) {
    throw error(400, 'Temp ID is required');
  }

  if (!['icon', 'thumb'].includes(type)) {
    throw error(400, 'Type must be "icon" or "thumb"');
  }

  try {
    const imageBuffer = await getPreviewImage(tempId, type);

    if (!imageBuffer) {
      throw error(404, 'Image not found');
    }

    return new Response(imageBuffer, {
      headers: {
        'Content-Type': 'image/webp',
        'Cache-Control': 'private, max-age=3600'
      }
    });
  } catch (err) {
    if (err.status) {
      throw err;
    }
    throw error(500, 'Failed to retrieve image');
  }
}
