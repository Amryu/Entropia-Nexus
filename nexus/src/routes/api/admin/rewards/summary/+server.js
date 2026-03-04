// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getRewardsSummary } from '$lib/server/db';

export async function GET({ locals }) {
  requireAdminAPI(locals);
  const summary = await getRewardsSummary();
  return json(summary);
}
