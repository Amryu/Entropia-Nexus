// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getCreatorById } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';
import { refreshCreator } from '$lib/server/creator-enrichment.js';

export async function POST({ params, locals }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  const creator = await getCreatorById(id);
  if (!creator) {
    return json({ error: 'Creator not found' }, { status: 404 });
  }

  try {
    const updated = await refreshCreator(creator);
    return json(updated);
  } catch (err) {
    console.error(`[creator-enrichment] Manual refresh failed for creator ${id}:`, err.message);
    return json({ error: 'Refresh failed: ' + err.message }, { status: 500 });
  }
}
