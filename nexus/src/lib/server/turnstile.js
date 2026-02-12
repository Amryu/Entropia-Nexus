// @ts-nocheck
/**
 * Cloudflare Turnstile server-side verification.
 * Used for bot protection on auction bids and buyouts.
 */

const TURNSTILE_SECRET = process.env.TURNSTILE_SECRET_KEY;
const TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

/**
 * Verify a Turnstile token server-side.
 * @param {string} token - The Turnstile response token from the client
 * @param {string} [remoteip] - Optional client IP for additional validation
 * @returns {Promise<boolean>} Whether the token is valid
 */
export async function verifyTurnstile(token, remoteip) {
  if (!TURNSTILE_SECRET) {
    console.warn('TURNSTILE_SECRET_KEY not configured — skipping verification');
    return true; // Allow in dev when not configured
  }

  if (!token || typeof token !== 'string') {
    return false;
  }

  try {
    const body = { secret: TURNSTILE_SECRET, response: token };
    if (remoteip) body.remoteip = remoteip;

    const res = await fetch(TURNSTILE_VERIFY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      console.error('Turnstile verification HTTP error:', res.status);
      return false;
    }

    const data = await res.json();
    return data.success === true;
  } catch (err) {
    console.error('Turnstile verification error:', err);
    return false;
  }
}
