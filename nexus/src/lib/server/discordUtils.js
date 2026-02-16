/**
 * Shared Discord invite code utilities.
 * Used by societies and transportation services.
 */

/**
 * Extract a Discord invite code from a URL or raw code string.
 * Accepts: discord.gg/CODE, discord.com/invite/CODE, discordapp.com/invite/CODE, or just CODE.
 * @param {string|null|undefined} input
 * @returns {string|null} The extracted invite code, or null if input is empty
 */
export function extractDiscordInviteCode(input) {
  if (!input) return null;
  const raw = String(input).trim();
  if (!raw) return null;

  const match = raw.match(/discord(?:app)?\.com\/invite\/([A-Za-z0-9-]+)/i)
    || raw.match(/discord\.gg\/([A-Za-z0-9-]+)/i);

  const code = match ? match[1] : raw;
  return code.trim();
}

/**
 * Validate that a string is a plausible Discord invite code.
 * @param {string} code
 * @returns {boolean}
 */
export function isValidDiscordCode(code) {
  return /^[A-Za-z0-9-]{2,32}$/.test(code);
}
