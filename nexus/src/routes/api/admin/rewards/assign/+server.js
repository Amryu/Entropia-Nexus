// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { assignReward, getChangeReward } from '$lib/server/db';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);
  const changeId = url.searchParams.get('change_id');
  if (!changeId) return json({ error: 'change_id required' }, { status: 400 });
  const reward = await getChangeReward(parseInt(changeId));
  return json({ reward });
}

export async function POST({ request, locals }) {
  const user = requireAdminAPI(locals);

  const body = await request.json();

  if (!body.change_id) {
    return json({ error: 'change_id is required' }, { status: 400 });
  }
  if (!body.user_id) {
    return json({ error: 'user_id is required' }, { status: 400 });
  }
  if (body.amount == null || parseFloat(body.amount) <= 0) {
    return json({ error: 'A positive amount is required' }, { status: 400 });
  }

  try {
    const reward = await assignReward({
      change_id: parseInt(body.change_id),
      user_id: body.user_id,
      rule_id: body.rule_id ? parseInt(body.rule_id) : null,
      amount: parseFloat(body.amount),
      contribution_score: body.contribution_score != null ? parseFloat(body.contribution_score) : null,
      note: body.note?.trim() || null,
      assigned_by: user.id
    });
    return json(reward, { status: 201 });
  } catch (err) {
    if (err.code === '23505') {
      return json({ error: 'This change already has a reward assigned' }, { status: 409 });
    }
    throw err;
  }
}
