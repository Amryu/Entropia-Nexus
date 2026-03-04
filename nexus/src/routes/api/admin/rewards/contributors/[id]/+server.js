// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getContributorDetail } from '$lib/server/db';

export async function GET({ params, locals }) {
  requireAdminAPI(locals);

  const detail = await getContributorDetail(params.id);
  if (!detail.user) {
    return json({ error: 'User not found' }, { status: 404 });
  }

  return json(detail);
}
