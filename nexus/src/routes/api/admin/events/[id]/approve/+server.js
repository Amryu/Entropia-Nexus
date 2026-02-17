// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getEventById, updateEventState } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function POST({ params, locals }) {
  const user = requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const event = await getEventById(id);
  if (!event) {
    return json({ error: 'Event not found' }, { status: 404 });
  }

  const updated = await updateEventState(id, 'approved', user.id);
  return json(updated);
}
