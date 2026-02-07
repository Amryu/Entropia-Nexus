// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideCategoryById, updateGuideCategory, deleteGuideCategory } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params }) {
  const category = await getGuideCategoryById(params.categoryId);
  if (!category) return json({ error: 'Category not found' }, { status: 404 });
  return json(category);
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const category = await updateGuideCategory(params.categoryId, {
    title: body.title.trim(),
    description: body.description?.trim() || null,
    sort_order: body.sort_order ?? 0
  });

  if (!category) return json({ error: 'Category not found' }, { status: 404 });
  return json(category);
}

export async function DELETE({ params, locals }) {
  requireGrant(locals, 'guide.delete');
  const category = await getGuideCategoryById(params.categoryId);
  if (!category) return json({ error: 'Category not found' }, { status: 404 });
  await deleteGuideCategory(params.categoryId);
  return json({ success: true });
}
