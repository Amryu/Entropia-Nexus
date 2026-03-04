// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { removeReward } from '$lib/server/db';

export async function DELETE({ params, locals }) {
  requireAdminAPI(locals);

  const deleted = await removeReward(parseInt(params.id));
  if (!deleted) {
    return json({ error: 'Reward not found' }, { status: 404 });
  }

  return json({ success: true });
}
