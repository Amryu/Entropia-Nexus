// @ts-nocheck
import sanitizeHtml from 'sanitize-html';

const SANITIZE_CONFIG = {
  allowedTags: sanitizeHtml.defaults.allowedTags.concat(['img', 'h2', 'h3', 'h4']),
  allowedAttributes: {
    ...sanitizeHtml.defaults.allowedAttributes,
    img: ['src', 'alt', 'title', 'data-width', 'data-pending', 'style'],
    a: ['href', 'name', 'target', 'rel'],
    div: ['data-type', 'data-provider', 'data-src', 'data-width', 'data-pending', 'data-alt', 'class', 'style']
  },
  allowedStyles: {
    '*': { 'width': [/^\d+px$/], 'max-width': [/^\d+(%|px)$/] }
  },
  transformTags: {
    a: (tagName, attribs) => ({
      tagName: 'a',
      attribs: {
        href: attribs.href || '',
        target: '_blank',
        rel: 'noopener noreferrer'
      }
    }),
    img: (tagName, attribs) => {
      if (!(attribs.src || '').startsWith('/api/img/')) {
        return { tagName: '', attribs: {} };
      }
      return { tagName: 'img', attribs };
    }
  }
};

export function sanitizeRichText(html) {
  if (typeof html !== 'string') return '';
  return sanitizeHtml(html, SANITIZE_CONFIG);
}
