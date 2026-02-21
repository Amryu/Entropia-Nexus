/**
 * Client-side HTML sanitization for wiki descriptions.
 * Uses DOMPurify for browser-compatible XSS prevention.
 *
 * The canonical server-side config lives in $lib/server/sanitizeRichText.js.
 * Keep allowed tags, attributes, and transform rules in sync between both files.
 */

import DOMPurify from 'dompurify';

/**
 * Allowed HTML tags from TipTap rich text editor.
 * Must match the server-side SANITIZE_CONFIG in $lib/server/sanitizeRichText.js.
 */
const ALLOWED_TAGS = [
  // Basic formatting
  'p', 'strong', 'em', 's', 'code', 'br',
  // Headings
  'h1', 'h2', 'h3', 'h4',
  // Lists
  'ul', 'ol', 'li',
  // Block elements
  'blockquote', 'pre', 'hr',
  // Links
  'a',
  // Video embeds (custom TipTap extension)
  'div', 'iframe',
  // Images (resizable, uploaded via entity-image endpoint)
  'img'
];

/**
 * Allowed attributes by tag.
 * Must match the server-side SANITIZE_CONFIG in $lib/server/sanitizeRichText.js.
 */
const ALLOWED_ATTR = [
  'href', 'target', 'rel',                    // Links
  'data-type', 'data-provider', 'data-src', 'class',  // Video embed wrapper
  'data-width', 'data-pending', 'data-alt', 'style',  // Resizable media
  'src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen',  // Iframe
  'alt'  // Images
];

/**
 * Configure DOMPurify with our whitelist.
 * Called once when the module is loaded.
 */
function configureDOMPurify() {
  // Only configure in browser environment
  if (typeof window === 'undefined') {
    return;
  }

  // Add hook to enforce safe link attributes
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    // Force safe attributes on links
    if (node.tagName === 'A') {
      const href = node.getAttribute('href') || '';
      if (href.startsWith('/')) {
        // Relative links: allow SvelteKit router to handle client-side navigation
        node.removeAttribute('target');
        node.removeAttribute('rel');
      } else {
        // External links: open in new tab safely
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
    }

    // Validate img sources (only allow our own image endpoint)
    if (node.tagName === 'IMG') {
      const src = node.getAttribute('src') || '';
      if (!src.startsWith('/api/img/')) {
        node.remove();
      }
    }

    // Validate iframe sources (only allow YouTube and Vimeo)
    if (node.tagName === 'IFRAME') {
      const src = node.getAttribute('src') || '';
      const allowedHosts = [
        'www.youtube.com',
        'youtube.com',
        'player.vimeo.com',
        'vimeo.com'
      ];

      try {
        const url = new URL(src);
        if (!allowedHosts.includes(url.hostname)) {
          node.remove();
        }
      } catch {
        // Invalid URL, remove the iframe
        node.remove();
      }
    }
  });
}

// Configure on module load (browser only)
if (typeof window !== 'undefined') {
  configureDOMPurify();
}

/**
 * Sanitize HTML content for safe rendering.
 *
 * @param {string} html - The HTML string to sanitize
 * @returns {string} - Sanitized HTML safe for rendering with {@html}
 */
export function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') {
    return '';
  }

  // In SSR context, return empty string (should not render user HTML on server)
  if (typeof window === 'undefined') {
    return '';
  }

  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: true,  // Allow data-* attributes for video embeds
    ADD_ATTR: ['allowfullscreen'],  // Ensure this isn't stripped
  });
}

/**
 * Restricted allowed tags for market descriptions (auctions, rentals).
 * Must match MARKET_SANITIZE_CONFIG in $lib/server/sanitizeRichText.js.
 */
const MARKET_ALLOWED_TAGS = [
  'p', 'strong', 'em', 's', 'br',
  'ul', 'ol', 'li',
  'blockquote', 'hr',
  'a'
];

/**
 * Sanitize HTML for market descriptions (auctions, rentals).
 * Uses a restricted tag allowlist — no images, videos, headings, or code.
 * The existing afterSanitizeAttributes hook handles link safety.
 *
 * @param {string} html - The HTML string to sanitize
 * @returns {string} - Sanitized HTML safe for rendering with {@html}
 */
export function sanitizeMarketHtml(html) {
  if (!html || typeof html !== 'string') {
    return '';
  }

  if (typeof window === 'undefined') {
    return '';
  }

  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: MARKET_ALLOWED_TAGS,
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  });
}

/**
 * Check if a string contains any HTML tags.
 * Useful for determining whether to use {@html} or plain text.
 *
 * @param {string} str - The string to check
 * @returns {boolean} - True if the string contains HTML tags
 */
export function containsHtml(str) {
  if (!str || typeof str !== 'string') {
    return false;
  }
  return /<[a-z][\s\S]*>/i.test(str);
}

/**
 * Strip all HTML tags from a string, returning plain text.
 * Also decodes common HTML entities.
 *
 * @param {string} text - The string potentially containing HTML
 * @returns {string} - Plain text with tags and entities removed
 */
export function stripHtml(text) {
  if (!text) return '';
  return `${text}`.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
}
