// @ts-nocheck
import { json } from '@sveltejs/kit';
import { updateGuideParagraph, deleteGuideParagraph } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  const content_html = sanitizeRichText(body.content_html || '');

  const paragraph = await updateGuideParagraph(params.paragraphId, {
    content_html,
    sort_order: body.sort_order ?? 0
  });

  if (!paragraph) return json({ error: 'Paragraph not found' }, { status: 404 });
  return json(paragraph);
}

export async function DELETE({ params, locals }) {
  requireGrant(locals, 'guide.delete');
  await deleteGuideParagraph(params.paragraphId);
  return json({ success: true });
}
