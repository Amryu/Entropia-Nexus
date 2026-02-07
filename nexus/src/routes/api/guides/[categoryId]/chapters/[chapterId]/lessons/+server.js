// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getGuideLessonsByChapter, createGuideLesson } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params }) {
  const lessons = await getGuideLessonsByChapter(params.chapterId);
  return json(lessons);
}

export async function POST({ params, request, locals }) {
  const user = requireGrant(locals, 'guide.create');
  const body = await request.json();

  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  if (!body.slug?.trim()) {
    return json({ error: 'Slug is required' }, { status: 400 });
  }

  // Validate slug format
  const slug = body.slug.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-');

  try {
    const lesson = await createGuideLesson({
      chapter_id: params.chapterId,
      title: body.title.trim(),
      slug,
      sort_order: body.sort_order ?? 0,
      created_by: user.id
    });
    return json(lesson, { status: 201 });
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'A lesson with that slug already exists' }, { status: 409 });
    }
    throw e;
  }
}
