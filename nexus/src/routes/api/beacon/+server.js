// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getClientIp } from '$lib/server/route-analytics.js';

// In-memory dedup to avoid DB writes on every page load
const recentIps = new Map();
const DEDUP_MS = 60 * 60_000; // 1 hour

// Valid BotD detection types (whitelist to prevent injection)
const VALID_BOTD_TYPES = new Set([
  'notDetected', 'awesomium', 'cef', 'cefsharp', 'coachjs', 'electron',
  'fminer', 'geb', 'nightmarejs', 'phantomas', 'phantomjs', 'rhino',
  'selenium', 'sequentum', 'slimerjs', 'webdriverio', 'webdriver',
  'headless_chrome', 'unknown',
]);

export async function POST(event) {
  const ip = getClientIp(event);
  if (!ip || ip === '0.0.0.0') return new Response(null, { status: 204 });

  // Parse BotD result from body (if present)
  let botDetected = false;
  let botdType = null;
  try {
    const text = await event.request.text();
    if (text) {
      const body = JSON.parse(text);
      botDetected = body.bot === true;
      if (body.type && VALID_BOTD_TYPES.has(body.type)) {
        botdType = body.type;
      }
    }
  } catch {
    // No body or invalid JSON - that's fine, plain beacon still works
  }

  const now = Date.now();
  const last = recentIps.get(ip);
  // Always update if BotD detected a bot (override dedup for bot signals)
  if (!botDetected && last && now - last < DEDUP_MS) return new Response(null, { status: 204 });
  recentIps.set(ip, now);

  // Periodic cleanup
  if (recentIps.size > 5000) {
    for (const [k, v] of recentIps) {
      if (now - v > DEDUP_MS) recentIps.delete(k);
    }
  }

  pool.query(
    `INSERT INTO beacon_hits (ip_address, last_seen, bot_detected, botd_type)
     VALUES ($1, now(), $2, $3)
     ON CONFLICT (ip_address) DO UPDATE SET
       last_seen = now(),
       bot_detected = CASE WHEN $2 THEN true ELSE beacon_hits.bot_detected END,
       botd_type = CASE WHEN $2 THEN $3 ELSE beacon_hits.botd_type END`,
    [ip, botDetected, botdType]
  ).catch(() => {});

  return new Response(null, { status: 204 });
}
