// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { assignReward, getChangeRewards } from '$lib/server/db';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);
  const changeId = url.searchParams.get('change_id');
  if (!changeId) return json({ error: 'change_id required' }, { status: 400 });
  const rewards = await getChangeRewards(parseInt(changeId));
  const reward = rewards[0] || null;
  return json({ reward, rewards });
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
    const amount = parseFloat(body.amount);

    // Auto-calculate contribution score: 2x PED amount, minimum 1,
    // with probabilistic rounding on the decimal part
    let contributionScore;
    if (body.contribution_score != null) {
      contributionScore = parseFloat(body.contribution_score);
    } else {
      const raw = Math.max(1, amount * 2);
      const base = Math.floor(raw);
      const decimal = raw - base;
      contributionScore = decimal > 0 && Math.random() < decimal ? base + 1 : base;
    }

    const reward = await assignReward({
      change_id: parseInt(body.change_id),
      user_id: body.user_id,
      rule_id: body.rule_id ? parseInt(body.rule_id) : null,
      amount,
      contribution_score: contributionScore,
      note: body.note?.trim() || null,
      assigned_by: user.id
    });
    return json(reward, { status: 201 });
  } catch (err) {
    if (err.code === '23505') {
      return json({ error: 'This reward rule is already assigned for this change' }, { status: 409 });
    }
    throw err;
  }
}
