// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getEventById, updateEventState } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function POST({ params, request, locals }) {
  const user = requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const event = await getEventById(id);
  if (!event) {
    return json({ error: 'Event not found' }, { status: 404 });
  }

  const body = await request.json().catch(() => ({}));
  const adminNote = body.reason?.trim() || null;

  const updated = await updateEventState(id, 'denied', user.id, adminNote);
  return json(updated);
}
