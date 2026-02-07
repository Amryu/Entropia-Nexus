// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideChaptersByCategory, createGuideChapter } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params }) {
  const chapters = await getGuideChaptersByCategory(params.categoryId);
  return json(chapters);
}

export async function POST({ params, request, locals }) {
  const user = requireGrant(locals, 'guide.create');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const chapter = await createGuideChapter({
    category_id: params.categoryId,
    title: body.title.trim(),
    description: body.description?.trim() || null,
    sort_order: body.sort_order ?? 0,
    created_by: user.id
  });

  return json(chapter, { status: 201 });
}
