/**
 * API endpoint for linking an entity's image to another entity's approved image.
 * Creates filesystem symlinks to avoid duplicating image files.
 *
 * POST /api/uploads/link-image
 * Body: { entityType, entityId, sourceEntityId }
 *
 * Both entities must be the same type. Source must have an approved image.
 * No approval workflow — the source image is already approved.
 */
import { error } from '@sveltejs/kit';
import { createImageLink, isValidEntityType } from '$lib/server/imageProcessor.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ request, locals }) {
  const user = locals.session?.user;
  if (!user) throw error(401, 'Authentication required');
  if (!user.verified) throw error(403, 'Account verification required');

  const body = await request.json().catch(() => null);
  if (!body) throw error(400, 'Invalid request body');

  const { entityType, entityId, sourceEntityId } = body;

  if (!entityType || !isValidEntityType(entityType)) {
    throw error(400, 'Valid entityType required');
  }
  if (!entityId) throw error(400, 'entityId required');
  if (!sourceEntityId) throw error(400, 'sourceEntityId required');
  if (String(entityId) === String(sourceEntityId)) {
    throw error(400, 'Cannot link an entity to itself');
  }

  const userId = String(user.Id || user.id);

  try {
    await createImageLink(entityType, String(entityId), entityType, String(sourceEntityId), userId);
  } catch (err) {
    console.error('Image link error:', err);
    throw error(500, err.message || 'Failed to create image link');
  }

  return new Response(JSON.stringify({
    success: true,
    imageUrl: `/api/img/${entityType}/${entityId}`
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}
