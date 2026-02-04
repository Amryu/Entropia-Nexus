// @ts-nocheck
import { getResponse } from '$lib/util.js';
import { markNotificationRead } from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function PATCH({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const notificationId = Number(params.id);
  if (!Number.isFinite(notificationId)) {
    return getResponse({ error: 'Invalid notification id.' }, 400);
  }

  const userId = String(user.Id || user.id);
  const updated = await markNotificationRead(userId, notificationId);
  if (!updated) {
    return getResponse({ error: 'Notification not found.' }, 404);
  }

  return getResponse({ success: true }, 200);
}
