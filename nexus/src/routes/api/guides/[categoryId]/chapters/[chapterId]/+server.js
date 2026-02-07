// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideChapterById, updateGuideChapter, deleteGuideChapter } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params }) {
  const chapter = await getGuideChapterById(params.chapterId);
  if (!chapter) return json({ error: 'Chapter not found' }, { status: 404 });
  return json(chapter);
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const chapter = await updateGuideChapter(params.chapterId, {
    title: body.title.trim(),
    description: body.description?.trim() || null,
    sort_order: body.sort_order ?? 0
  });

  if (!chapter) return json({ error: 'Chapter not found' }, { status: 404 });
  return json(chapter);
}

export async function DELETE({ params, locals }) {
  requireGrant(locals, 'guide.delete');
  const chapter = await getGuideChapterById(params.chapterId);
  if (!chapter) return json({ error: 'Chapter not found' }, { status: 404 });
  await deleteGuideChapter(params.chapterId);
  return json({ success: true });
}
