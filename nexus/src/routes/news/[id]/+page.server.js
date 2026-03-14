// @ts-nocheck
import { error } from '@sveltejs/kit';
import { getPublishedAnnouncementById } from '$lib/server/db.js';
import { sanitizeNewsHtml, sanitizeRichText } from '$lib/server/sanitizeRichText.js';

export async function load({ params }) {
  const id = parseInt(params.id, 10);
  if (isNaN(id)) throw error(404, 'Not found');

  const announcement = await getPublishedAnnouncementById(id);
  if (!announcement) throw error(404, 'Not found');

  // Sanitize HTML on the server so the page can render it directly via {@html}
  // without needing client-side DOMPurify (which breaks SSR and strips external images).
  if (announcement.content_html) {
    announcement.content_html = announcement.source === 'steam'
      ? sanitizeNewsHtml(announcement.content_html)
      : sanitizeRichText(announcement.content_html);
  }

  return { announcement };
}
