// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { completePayout } from '$lib/server/db';

export async function PATCH({ params, locals }) {
  requireAdminAPI(locals);

  const payout = await completePayout(parseInt(params.id));
  if (!payout) {
    return json({ error: 'Payout not found or already completed' }, { status: 404 });
  }

  return json(payout);
}
