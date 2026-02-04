import sanitizeHtml from 'sanitize-html';

const SANITIZE_CONFIG = {
  allowedTags: sanitizeHtml.defaults.allowedTags.concat(['img', 'h2', 'h3', 'h4']),
  allowedAttributes: {
    ...sanitizeHtml.defaults.allowedAttributes,
    img: ['src', 'alt', 'title'],
    a: ['href', 'name', 'target', 'rel']
  },
  transformTags: {
    a: (tagName, attribs) => ({
      tagName: 'a',
      attribs: {
        href: attribs.href || '',
        target: '_blank',
        rel: 'noopener noreferrer'
      }
    })
  }
};

export function sanitizeRichText(html) {
  if (typeof html !== 'string') return '';
  return sanitizeHtml(html, SANITIZE_CONFIG);
}
