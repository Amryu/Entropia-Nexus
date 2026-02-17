// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAnnouncementsAdmin, createAnnouncement } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

export async function GET({ url, locals }) {
  requireAdmin(locals);

  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20', 10), 100);

  const result = await getAnnouncementsAdmin(page, limit);
  return json(result);
}

export async function POST({ request, locals }) {
  const user = requireAdmin(locals);
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }
  if (body.title.trim().length > 200) {
    return json({ error: 'Title must be 200 characters or less' }, { status: 400 });
  }
  if (body.summary && body.summary.length > 500) {
    return json({ error: 'Summary must be 500 characters or less' }, { status: 400 });
  }

  const announcement = await createAnnouncement({
    title: body.title.trim(),
    summary: body.summary?.trim() || null,
    link: body.link?.trim() || null,
    image_url: body.image_url?.trim() || null,
    pinned: !!body.pinned,
    published: !!body.published,
    author_id: user.id,
    content_html: body.content_html ? sanitizeRichText(body.content_html) : null
  });

  return json(announcement, { status: 201 });
}
