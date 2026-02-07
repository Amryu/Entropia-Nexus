// @ts-nocheck
import { json } from '@sveltejs/kit';
import { updateGuideParagraph, deleteGuideParagraph } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';
import sanitizeHtml from 'sanitize-html';

const SANITIZE_CONFIG = {
  allowedTags: [
    'p', 'strong', 'em', 's', 'code', 'br',
    'h1', 'h2', 'h3', 'h4',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'hr',
    'a',
    'div', 'iframe'
  ],
  allowedAttributes: {
    'a': ['href', 'target', 'rel'],
    'div': ['data-type', 'data-provider', 'data-src', 'class'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']
  },
  allowedIframeHostnames: ['www.youtube.com', 'youtube.com', 'player.vimeo.com', 'vimeo.com'],
  transformTags: {
    'a': (tagName, attribs) => ({
      tagName: 'a',
      attribs: { href: attribs.href || '', target: '_blank', rel: 'noopener noreferrer' }
    })
  }
};

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'guide.edit');
  const body = await request.json();

  const content_html = sanitizeHtml(body.content_html || '', SANITIZE_CONFIG);

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
