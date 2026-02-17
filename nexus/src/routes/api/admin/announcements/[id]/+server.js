// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAnnouncementById, updateAnnouncement, deleteAnnouncement } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

export async function GET({ params, locals }) {
  requireAdmin(locals);

  const announcement = await getAnnouncementById(parseInt(params.id, 10));
  if (!announcement) {
    return json({ error: 'Announcement not found' }, { status: 404 });
  }

  return json(announcement);
}

export async function PUT({ params, request, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const existing = await getAnnouncementById(id);
  if (!existing) {
    return json({ error: 'Announcement not found' }, { status: 404 });
  }

  const body = await request.json();

  if ('title' in body && !body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }
  if (body.title && body.title.trim().length > 200) {
    return json({ error: 'Title must be 200 characters or less' }, { status: 400 });
  }
  if (body.summary && body.summary.length > 500) {
    return json({ error: 'Summary must be 500 characters or less' }, { status: 400 });
  }

  const fields = {};
  if ('title' in body) fields.title = body.title.trim();
  if ('summary' in body) fields.summary = body.summary?.trim() || null;
  if ('link' in body) fields.link = body.link?.trim() || null;
  if ('image_url' in body) fields.image_url = body.image_url?.trim() || null;
  if ('pinned' in body) fields.pinned = !!body.pinned;
  if ('published' in body) fields.published = !!body.published;
  if ('content_html' in body) fields.content_html = body.content_html ? sanitizeRichText(body.content_html) : null;

  const updated = await updateAnnouncement(id, fields);
  return json(updated);
}

export async function DELETE({ params, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const deleted = await deleteAnnouncement(id);
  if (!deleted) {
    return json({ error: 'Announcement not found' }, { status: 404 });
  }

  return json({ success: true });
}
