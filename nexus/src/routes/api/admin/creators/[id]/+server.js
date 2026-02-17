// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getCreatorById, updateCreator, deleteCreator } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireAdmin(locals);

  const creator = await getCreatorById(parseInt(params.id, 10));
  if (!creator) {
    return json({ error: 'Creator not found' }, { status: 404 });
  }

  return json(creator);
}

export async function PUT({ params, request, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const existing = await getCreatorById(id);
  if (!existing) {
    return json({ error: 'Creator not found' }, { status: 404 });
  }

  const body = await request.json();

  if ('name' in body && !body.name?.trim()) {
    return json({ error: 'Name is required' }, { status: 400 });
  }

  const fields = {};
  if ('name' in body) fields.name = body.name.trim();
  if ('platform' in body) fields.platform = body.platform;
  if ('channel_id' in body) fields.channel_id = body.channel_id?.trim() || null;
  if ('channel_url' in body) fields.channel_url = body.channel_url?.trim() || null;
  if ('description' in body) fields.description = body.description?.trim() || null;
  if ('avatar_url' in body) fields.avatar_url = body.avatar_url?.trim() || null;
  if ('active' in body) fields.active = !!body.active;
  if ('display_order' in body) fields.display_order = parseInt(body.display_order, 10) || 0;

  const updated = await updateCreator(id, fields);
  return json(updated);
}

export async function DELETE({ params, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const deleted = await deleteCreator(id);
  if (!deleted) {
    return json({ error: 'Creator not found' }, { status: 404 });
  }

  return json({ success: true });
}
