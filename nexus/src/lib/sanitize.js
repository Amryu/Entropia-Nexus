/**
 * Client-side HTML sanitization for wiki descriptions.
 * Uses DOMPurify for browser-compatible XSS prevention.
 *
 * This mirrors the server-side sanitization in /api/changes to ensure
 * consistent handling of rich text content from the TipTap editor.
 */

import DOMPurify from 'dompurify';

/**
 * Allowed HTML tags from TipTap rich text editor.
 * Must match the server-side SANITIZE_CONFIG in /api/changes/+server.js
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
  'div', 'iframe'
];

/**
 * Allowed attributes by tag.
 * Must match the server-side configuration.
 */
const ALLOWED_ATTR = [
  'href', 'target', 'rel',                    // Links
  'data-type', 'data-provider', 'data-src', 'class',  // Video embed wrapper
  'src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen'  // Iframe
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
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
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
