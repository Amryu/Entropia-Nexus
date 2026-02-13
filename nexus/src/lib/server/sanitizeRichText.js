// @ts-nocheck
import sanitizeHtml from 'sanitize-html';

/**
 * Canonical server-side HTML sanitization config for TipTap rich text editor output.
 * Used by all API endpoints that accept rich text (changes, profiles, societies, guides).
 *
 * The client-side equivalent is in $lib/sanitize.js (uses DOMPurify).
 * Keep both in sync when adding new tags or attributes.
 */
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
    'a': (tagName, attribs) => {
      const href = attribs.href || '';
      if (href.startsWith('/')) {
        // Relative links: no target/rel so SvelteKit router handles navigation
        return { tagName: 'a', attribs: { href } };
      }
      return { tagName: 'a', attribs: { href, target: '_blank', rel: 'noopener noreferrer' } };
    },
    'img': (tagName, attribs) => {
      if (!(attribs.src || '').startsWith('/api/img/')) {
        return { tagName: '', attribs: {} };
      }
      return { tagName: 'img', attribs };
    }
  }
};

/**
 * Sanitize HTML content from the TipTap rich text editor.
 *
 * @param {string} html - The HTML string to sanitize
 * @returns {string} - Sanitized HTML safe for storage and rendering
 */
export function sanitizeRichText(html) {
  if (typeof html !== 'string') return '';
  return sanitizeHtml(html, SANITIZE_CONFIG);
}
