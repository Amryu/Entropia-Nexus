/**
 * Pure HTML utility functions (no sanitization).
 *
 * All HTML sanitization is consolidated server-side in
 * $lib/server/sanitizeRichText.js — that is the single source of truth.
 */

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

/**
 * Returns true if the string contains visible text after stripping HTML tags
 * and whitespace. Useful for checking if a rich-text description has actual
 * content vs. empty markup like `<p></p>` or `<br>`.
 */
export function hasVisibleText(html) {
  return stripHtml(html).trim().length > 0;
}
