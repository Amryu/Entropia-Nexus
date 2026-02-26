// @ts-nocheck
/**
 * GET /api/news/:id — Returns a single published announcement with full content.
 * Public endpoint, no auth required.
 */
import { getPublishedAnnouncementById } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

export async function GET({ params }) {
  const id = parseInt(params.id, 10);
  if (isNaN(id)) return getResponse({ error: 'Invalid ID' }, 400);

  const announcement = await getPublishedAnnouncementById(id);
  if (!announcement) return getResponse({ error: 'Not found' }, 404);

  return getResponse(announcement, 200);
}
