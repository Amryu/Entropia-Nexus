//@ts-nocheck
import { getAllLinks } from '$lib/sitemapUtil.js';

function generateSitemapEntry(url, priority = '0.9') {
  return `<url>
    <loc>https://entropianexus.com${url}</loc>
    <changefreq>daily</changefreq>
    <priority>${priority}</priority>
  </url>`;
};

export async function GET({ url }) {
  let links = await getAllLinks(fetch);

  let xmlString = Object.values(links).flat().map(x => generateSitemapEntry(x)).join('\n');

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