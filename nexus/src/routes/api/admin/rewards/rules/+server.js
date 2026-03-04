// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getRewardRules, createRewardRule } from '$lib/server/db';

export async function GET({ locals }) {
  requireAdminAPI(locals);
  const rules = await getRewardRules();
  return json({ rules });
}

export async function POST({ request, locals }) {
  requireAdminAPI(locals);

  const body = await request.json();

  if (!body.name?.trim()) {
    return json({ error: 'Name is required' }, { status: 400 });
  }
  if (body.min_amount == null || body.max_amount == null) {
    return json({ error: 'Amount range is required' }, { status: 400 });
  }
  if (parseFloat(body.min_amount) < 0 || parseFloat(body.max_amount) < 0) {
    return json({ error: 'Amounts must be non-negative' }, { status: 400 });
  }
  if (parseFloat(body.min_amount) > parseFloat(body.max_amount)) {
    return json({ error: 'Min amount cannot exceed max amount' }, { status: 400 });
  }

  const rule = await createRewardRule({
    name: body.name.trim(),
    description: body.description?.trim() || null,
    category: body.category?.trim() || null,
    entities: body.entities?.length ? body.entities : null,
    change_type: body.change_type || null,
    data_fields: body.data_fields?.length ? body.data_fields : null,
    min_amount: parseFloat(body.min_amount),
    max_amount: parseFloat(body.max_amount),
    contribution_score: body.contribution_score != null ? parseFloat(body.contribution_score) : null,
    sort_order: parseInt(body.sort_order || '0')
  });

  return json(rule, { status: 201 });
}
