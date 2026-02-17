// @ts-nocheck
import { getPublishedAnnouncements, getUpcomingEvents, getActiveCreators } from '$lib/server/db.js';
import { getCachedSteamNews, mergeAndSortNews } from '$lib/server/news-cache.js';

export async function load() {
  const [announcements, steamNews, events, creators] = await Promise.all([
    getPublishedAnnouncements(6),
    getCachedSteamNews(),
    getUpcomingEvents(5),
    getActiveCreators()
  ]);

  const news = mergeAndSortNews(announcements, steamNews);

  return {
    news,
    events,
    creators
  };
}
