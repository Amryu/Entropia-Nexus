// @ts-nocheck
import { getPublishedAnnouncements } from '$lib/server/db.js';

const SITE_URL = 'https://entropianexus.com';
const FEED_TITLE = 'Entropia Nexus';
const FEED_DESCRIPTION = 'News and updates from Entropia Nexus — the community hub for Entropia Universe.';

function escapeXml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function buildItemUrl(a) {
  if (a.has_content || a.source === 'steam') return `${SITE_URL}/news/${a.id}`;
  return a.link || `${SITE_URL}/news/${a.id}`;
}

export async function GET() {
  const announcements = await getPublishedAnnouncements(50);

  const items = announcements.map(a => {
    const url = buildItemUrl(a);
    const pubDate = new Date(a.created_at).toUTCString();

    return `    <item>
      <title>${escapeXml(a.title)}</title>
      <link>${escapeXml(url)}</link>
      <guid isPermaLink="${a.has_content || a.source === 'steam' ? 'true' : 'false'}">${escapeXml(url)}</guid>
      <pubDate>${pubDate}</pubDate>${a.summary ? `
      <description>${escapeXml(a.summary)}</description>` : ''}${a.source ? `
      <category>${escapeXml(a.source === 'steam' ? 'Entropia Universe' : 'Entropia Nexus')}</category>` : ''}
    </item>`;
  });

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(FEED_TITLE)}</title>
    <link>${SITE_URL}</link>
    <description>${escapeXml(FEED_DESCRIPTION)}</description>
    <language>en</language>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
${items.join('\n')}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'max-age=900'
    }
  });
}
