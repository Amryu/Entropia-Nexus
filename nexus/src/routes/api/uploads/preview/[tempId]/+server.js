/**
 * API endpoint to serve preview images from temp storage.
 */
import { error } from '@sveltejs/kit';
import { getPreviewImage } from '$lib/server/imageProcessor.js';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, url }) {
  const { tempId } = params;
  const type = url.searchParams.get('type') || 'icon';

  if (!tempId || !UUID_REGEX.test(tempId)) {
    throw error(400, 'Invalid preview ID');
  }

  if (!['icon', 'thumb'].includes(type)) {
    throw error(400, 'Type must be "icon" or "thumb"');
  }

  try {
    const imageBuffer = await getPreviewImage(tempId, type);

    if (!imageBuffer) {
      throw error(404, 'Image not found');
    }

    return new Response(new Uint8Array(imageBuffer), {
      headers: {
        'Content-Type': 'image/webp',
        'Cache-Control': 'private, no-store'
      }
    });
  } catch (/** @type {any} */ err) {
    if (err.status) {
      throw err;
    }
    throw error(500, 'Failed to retrieve image');
  }
}
