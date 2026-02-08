// @ts-nocheck
import { json } from '@sveltejs/kit';
import { createGuideParagraph, reorderGuideParagraphs, getGuideParagraphsByLesson } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';
import sanitizeHtml from 'sanitize-html';

const SANITIZE_CONFIG = {
  allowedTags: [
    'p', 'strong', 'em', 's', 'code', 'br',
    'h1', 'h2', 'h3', 'h4',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'hr',
    'a',
    'div', 'iframe',
    'img'
  ],
  allowedAttributes: {
    'a': ['href', 'target', 'rel'],
    'div': ['data-type', 'data-provider', 'data-src', 'data-width', 'data-pending', 'data-alt', 'class', 'style'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen'],
    'img': ['src', 'alt', 'data-width', 'data-pending', 'style']
  },
  allowedStyles: {
    '*': { 'width': [/^\d+px$/], 'max-width': [/^\d+(%|px)$/] }
  },
  allowedIframeHostnames: ['www.youtube.com', 'youtube.com', 'player.vimeo.com', 'vimeo.com'],
  transformTags: {
    'a': (tagName, attribs) => ({
      tagName: 'a',
      attribs: { href: attribs.href || '', target: '_blank', rel: 'noopener noreferrer' }
    }),
    'img': (tagName, attribs) => {
      if (!(attribs.src || '').startsWith('/api/img/')) {
        return { tagName: '', attribs: {} };
      }
      return { tagName: 'img', attribs };
    }
  }
};

/** POST: Create a new paragraph in a lesson */
export async function POST({ params, request, locals }) {
  const user = requireGrant(locals, 'guide.create');
  const body = await request.json();

  const content_html = sanitizeHtml(body.content_html || '', SANITIZE_CONFIG);

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
