// @ts-nocheck
import { json } from '@sveltejs/kit';
import { createGuideParagraph, reorderGuideParagraphs, getGuideParagraphsByLesson } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

/** POST: Create a new paragraph in a lesson */
export async function POST({ params, request, locals }) {
  const user = requireGrant(locals, 'guide.create');
  const body = await request.json();

  const content_html = sanitizeRichText(body.content_html || '');

  const paragraph = await createGuideParagraph({
    lesson_id: params.lessonId,
    content_html,
    sort_order: body.sort_order ?? 0,
    created_by: user.id
  });

  return json(paragraph, { status: 201 });
}

/** PUT: Reorder paragraphs within a lesson */
export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  if (!Array.isArray(body.orderedIds)) {
    return json({ error: 'orderedIds must be an array of paragraph IDs' }, { status: 400 });
  }

  await reorderGuideParagraphs(params.lessonId, body.orderedIds);
  const paragraphs = await getGuideParagraphsByLesson(params.lessonId);
  return json(paragraphs);
}
