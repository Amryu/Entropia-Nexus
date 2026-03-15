//@ts-nocheck
import { getAllLinks } from '$lib/sitemapUtil.js';
import { getPublishedAnnouncements } from '$lib/server/db.js';

function generateSitemapEntry(url, priority = '0.9') {
  return `<url>
    <loc>https://entropianexus.com${url}</loc>
    <changefreq>daily</changefreq>
    <priority>${priority}</priority>
  </url>`;
};

export async function GET({ url }) {
  const [links, announcements] = await Promise.all([
    getAllLinks(fetch),
    getPublishedAnnouncements(500),
  ]);

  const newsUrls = (announcements || [])
    .filter(a => a.has_content)
    .map(a => `/news/${a.id}`);

  let xmlString = [...Object.values(links).flat(), ...newsUrls]
    .map(x => generateSitemapEntry(x)).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      ${generateSitemapEntry('', '1.0')}
      ${xmlString}
    </urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml'
    }
  });
}