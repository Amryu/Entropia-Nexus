// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideTree, createGuideCategory } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

/** GET: Return full guide tree (public) */
export async function GET() {
  const tree = await getGuideTree();
  return json(tree);
}

/** POST: Create a new category */
export async function POST({ request, locals }) {
  const user = requireGrant(locals, 'guide.create');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const category = await createGuideCategory({
    title: body.title.trim(),
    description: body.description?.trim() || null,
    sort_order: body.sort_order ?? 0,
    created_by: user.id
  });

  return json(category, { status: 201 });
}
