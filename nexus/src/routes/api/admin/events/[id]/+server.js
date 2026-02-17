// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getEventById, updateEvent, deleteEvent } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireAdmin(locals);

  const event = await getEventById(parseInt(params.id, 10));
  if (!event) {
    return json({ error: 'Event not found' }, { status: 404 });
  }

  return json(event);
}

export async function PUT({ params, request, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const existing = await getEventById(id);
  if (!existing) {
    return json({ error: 'Event not found' }, { status: 404 });
  }

  const body = await request.json();

  if ('title' in body && !body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }
  if (body.title && body.title.trim().length > 200) {
    return json({ error: 'Title must be 200 characters or less' }, { status: 400 });
  }
  if (body.description && body.description.length > 2000) {
    return json({ error: 'Description must be 2000 characters or less' }, { status: 400 });
  }

  const fields = {};
  if ('title' in body) fields.title = body.title.trim();
  if ('description' in body) fields.description = body.description?.trim() || null;
  if ('start_date' in body) fields.start_date = body.start_date;
  if ('end_date' in body) fields.end_date = body.end_date || null;
  if ('location' in body) fields.location = body.location?.trim() || null;
  if ('type' in body) fields.type = body.type;
  if ('link' in body) fields.link = body.link?.trim() || null;
  if ('image_url' in body) fields.image_url = body.image_url?.trim() || null;

  const updated = await updateEvent(id, fields);
  return json(updated);
}

export async function DELETE({ params, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const deleted = await deleteEvent(id);
  if (!deleted) {
    return json({ error: 'Event not found' }, { status: 404 });
  }

  return json({ success: true });
}
