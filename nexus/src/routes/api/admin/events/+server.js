// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getEventsAdmin } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function GET({ url, locals }) {
  requireAdmin(locals);

  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20', 10), 100);
  const state = url.searchParams.get('state') || null;

  const result = await getEventsAdmin(page, limit, state);
  return json(result);
}
