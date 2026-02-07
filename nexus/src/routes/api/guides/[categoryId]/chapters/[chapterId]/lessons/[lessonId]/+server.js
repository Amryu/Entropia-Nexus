// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideLessonById, updateGuideLesson, deleteGuideLesson, getGuideParagraphsByLesson } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

/** GET: Lesson with paragraphs */
export async function GET({ params }) {
  const lesson = await getGuideLessonById(params.lessonId);
  if (!lesson) return json({ error: 'Lesson not found' }, { status: 404 });

  const paragraphs = await getGuideParagraphsByLesson(params.lessonId);
  return json({ ...lesson, paragraphs });
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const slug = body.slug?.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-');

  try {
    const lesson = await updateGuideLesson(params.lessonId, {
      title: body.title.trim(),
      slug: slug || undefined,
      sort_order: body.sort_order ?? 0
    });
    if (!lesson) return json({ error: 'Lesson not found' }, { status: 404 });
    return json(lesson);
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'A lesson with that slug already exists' }, { status: 409 });
    }
    throw e;
  }
}

export async function DELETE({ params, locals }) {
  requireGrant(locals, 'guide.delete');
  const lesson = await getGuideLessonById(params.lessonId);
  if (!lesson) return json({ error: 'Lesson not found' }, { status: 404 });
  await deleteGuideLesson(params.lessonId);
  return json({ success: true });
}
