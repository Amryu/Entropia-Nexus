/**
 * API endpoint to get user's pending image for a specific entity.
 * Returns the pending image preview URL if the current user has one.
 */
// @ts-nocheck
import { error, json } from '@sveltejs/kit';
import { getUserPendingImage } from '$lib/server/imageProcessor.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    throw error(401, 'Authentication required');
  }

  const userId = String(user.Id || user.id);
  const { entityType, entityId } = params;

  // Validate entity type (alphanumeric only)
  if (!/^[a-zA-Z]+$/.test(entityType)) {
    throw error(400, 'Invalid entity type');
  }

  // Get user's pending image for this entity
  const pendingImage = await getUserPendingImage(userId, entityType, entityId);

  if (!pendingImage) {
    return json({ hasPending: false });
  }

  return json({
    hasPending: true,
    previewUrl: pendingImage.previewUrl,
    uploadedAt: pendingImage.uploadedAt
  });
}
