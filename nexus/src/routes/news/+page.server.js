// @ts-nocheck
import { getPublishedAnnouncements } from '$lib/server/db.js';
import { formatNewsFeed } from '$lib/server/news-cache.js';

export async function load() {
  const announcements = await getPublishedAnnouncements(100);
  const news = formatNewsFeed(announcements);

  return { news };
}
