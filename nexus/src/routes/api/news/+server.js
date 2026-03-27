// @ts-nocheck
/**
 * GET /api/news — Returns latest published announcements + active featured posts.
 * Public endpoint, no auth required.
 */
import { getPublishedAnnouncements } from '$lib/server/db.js';
import { formatNewsFeed } from '$lib/server/news-cache.js';
import { getActivePromos } from '$lib/server/promo-cache.js';
import { getResponse } from '$lib/util.js';

const MAX_LIMIT = 500;
const DEFAULT_LIMIT = 3;

export async function GET({ url }) {
  const limit = Math.min(
    Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT),
    MAX_LIMIT
  );

  const [announcements, promos] = await Promise.all([
    getPublishedAnnouncements(limit),
    getActivePromos()
  ]);

  const news = formatNewsFeed(announcements);

  // Append up to 1 active featured post (rotated per request)
  const featuredPosts = promos?.featuredPosts || [];
  if (featuredPosts.length > 0) {
    const fp = featuredPosts[Math.floor(Math.random() * featuredPosts.length)];
    const autoSummary = !fp.summary && fp.content_html
      ? fp.content_html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim().slice(0, 300)
      : fp.summary;
    const insertAt = Math.min(2, news.length);
    news.splice(insertAt, 0, {
      source: 'featured',
      id: `featured-${fp.booking_id}`,
      title: fp.title || fp.name,
      summary: autoSummary || '',
      url: `/api/promos/click/${fp.booking_id}`,
      featured: true,
      has_content: !!fp.content_html,
      date: new Date().toISOString()
    });
  }

  return getResponse(news, 200);
}
