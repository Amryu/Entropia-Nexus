// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { updateRewardRule, deleteRewardRule } from '$lib/server/db';

export async function PATCH({ params, request, locals }) {
  requireAdminAPI(locals);

  const body = await request.json();

  if ('min_amount' in body && 'max_amount' in body) {
    if (parseFloat(body.min_amount) > parseFloat(body.max_amount)) {
      return json({ error: 'Min amount cannot exceed max amount' }, { status: 400 });
    }
  }

  const fields = {};
  const allowed = ['name', 'description', 'category', 'entities', 'change_type', 'data_fields', 'min_amount', 'max_amount', 'contribution_score', 'active', 'sort_order'];
  for (const key of allowed) {
    if (key in body) {
      if (key === 'min_amount' || key === 'max_amount' || key === 'contribution_score') {
        fields[key] = body[key] != null ? parseFloat(body[key]) : null;
      } else if (key === 'sort_order') {
        fields[key] = parseInt(body[key] || '0');
      } else if (key === 'entities' || key === 'data_fields') {
        fields[key] = body[key]?.length ? body[key] : null;
      } else {
        fields[key] = body[key];
      }
    }
  }

  const updated = await updateRewardRule(parseInt(params.id), fields);
  if (!updated) {
    return json({ error: 'Rule not found' }, { status: 404 });
  }

  return json(updated);
}

export async function DELETE({ params, locals }) {
  requireAdminAPI(locals);

  const deleted = await deleteRewardRule(parseInt(params.id));
  if (!deleted) {
    return json({ error: 'Rule not found' }, { status: 404 });
  }

  return json({ success: true });
}
