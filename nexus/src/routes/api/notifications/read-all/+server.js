// @ts-nocheck
import { getResponse } from '$lib/util.js';
import { markAllNotificationsRead } from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const userId = String(user.Id || user.id);
  await markAllNotificationsRead(userId);
  return getResponse({ success: true }, 200);
}
