// @ts-nocheck
import { json, error } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getGroup, listGroups } from '$lib/server/manual-unlocks.js';

export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const groupKey = url.searchParams.get('group');
  if (!groupKey) {
    return json({ groups: listGroups() });
  }

  const group = getGroup(groupKey);
  if (!group) throw error(404, `Unknown group: ${groupKey}`);

  const entries = await group.list();
  return json({
    group: { key: group.key, label: group.label, description: group.description, entryLabel: group.entryLabel },
    entries,
  });
}

export async function POST({ locals, request }) {
  const user = requireAdminAPI(locals);

  const body = await request.json().catch(() => ({}));
  const { group: groupKey, id } = body || {};

  if (!groupKey || id == null) throw error(400, 'group and id are required');

  const group = getGroup(groupKey);
  if (!group) throw error(404, `Unknown group: ${groupKey}`);

  const actorName = user?.global_name || user?.username || String(user?.id || 'admin');
  try {
    await group.unlock(id, actorName);
  } catch (err) {
    console.error('[admin/manual-unlocks] unlock failed', err);
    throw error(500, err.message || 'Unlock failed');
  }

  return json({ success: true });
}
