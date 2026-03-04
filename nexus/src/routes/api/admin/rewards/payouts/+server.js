// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getPayouts, createPayout } from '$lib/server/db';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const status = url.searchParams.get('status') || null;
  const user_id = url.searchParams.get('user_id') || null;

  const filters = {};
  if (status) filters.status = status;
  if (user_id) filters.user_id = user_id;

  const result = await getPayouts(page, limit, filters);
  return json(result);
}

export async function POST({ request, locals }) {
  const user = requireAdminAPI(locals);

  const body = await request.json();

  if (!body.user_id) {
    return json({ error: 'user_id is required' }, { status: 400 });
  }
  if (body.amount == null || parseFloat(body.amount) <= 0) {
    return json({ error: 'A positive amount is required' }, { status: 400 });
  }

  const payout = await createPayout({
    user_id: body.user_id,
    amount: parseFloat(body.amount),
    is_bonus: body.is_bonus || false,
    note: body.note?.trim() || null,
    created_by: user.id
  });

  return json(payout, { status: 201 });
}
