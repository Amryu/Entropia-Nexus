// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getNotifications,
  countNotifications,
  countUnreadNotifications
} from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ url, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
  const pageSize = Math.min(50, Math.max(5, parseInt(url.searchParams.get('pageSize') || '10', 10)));
  const offset = (page - 1) * pageSize;

  const userId = String(user.Id || user.id);

  const [rows, total, unread] = await Promise.all([
    getNotifications(userId, pageSize, offset),
    countNotifications(userId),
    countUnreadNotifications(userId)
  ]);

  return getResponse({
    rows,
    total,
    unread,
    page,
    pageSize
  }, 200);
}
