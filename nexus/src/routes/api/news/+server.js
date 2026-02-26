// @ts-nocheck
/**
 * GET /api/news — Returns latest published announcements.
 * Public endpoint, no auth required.
 */
import { getPublishedAnnouncements } from '$lib/server/db.js';
import { formatNewsFeed } from '$lib/server/news-cache.js';
import { getResponse } from '$lib/util.js';

const MAX_LIMIT = 500;
const DEFAULT_LIMIT = 3;

export async function GET({ url }) {
  const limit = Math.min(
    Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT),
    MAX_LIMIT
  );

  const announcements = await getPublishedAnnouncements(limit);
  const news = formatNewsFeed(announcements);

  return getResponse(news, 200);
}
