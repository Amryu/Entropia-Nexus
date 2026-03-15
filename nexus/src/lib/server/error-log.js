// @ts-nocheck
/**
 * Error log — captures HTTP error responses (4xx/5xx) with full diagnostic info.
 * Keeps the last MAX_PER_GROUP errors per (route_pattern, status_code) pair.
 *
 * Usage from hooks.server.js:
 *   recordError(event, response, startTime)  — fire-and-forget after resolve()
 */
import { pool } from '$lib/server/db.js';

const MAX_PER_GROUP = 10;
const PRUNE_INTERVAL_MS = 10 * 60_000; // prune excess rows every 10 min

// Headers to redact from the stored request headers
const REDACT_HEADERS = new Set(['cookie', 'authorization', 'x-api-key']);

// Debounce: don't record the same route+status more than once per second
// (prevents flood from repeated rapid errors)
const recentErrors = new Map();
const DEDUP_MS = 1000;

/**
 * Record an error response. Call fire-and-forget from hooks.
 * Only call when response.status >= 400.
 */
export async function recordError(event, response, startTime, clonedBody) {
  const pathname = event.url.pathname;
  const routePattern = event.route?.id || pathname;
  const statusCode = response.status;

  // Dedup rapid identical errors
  const dedupKey = `${routePattern}:${statusCode}`;
  const now = Date.now();
  if (recentErrors.get(dedupKey) > now - DEDUP_MS) return;
  recentErrors.set(dedupKey, now);

  // Extract request headers (redact sensitive ones)
  const headers = {};
  for (const [key, value] of event.request.headers.entries()) {
    headers[key] = REDACT_HEADERS.has(key.toLowerCase()) ? '[REDACTED]' : value;
  }

  // IP + country (reuse from route-analytics if available, but standalone here)
  const cfIp = event.request.headers.get('cf-connecting-ip');
  const xff = event.request.headers.get('x-forwarded-for');
  let ip = cfIp || (xff ? xff.split(',').pop().trim() : null);
  if (!ip) { try { ip = event.getClientAddress(); } catch { ip = null; } }

  let countryCode = null;
  try {
    const geoip = await import('geoip-lite');
    const lookup = geoip.default?.lookup || geoip.lookup;
    if (lookup && ip) countryCode = lookup(ip)?.country || null;
  } catch { /* geoip not available */ }

  const responseTime = startTime ? (Date.now() - startTime) : null;

  // Truncate response body
  const body = clonedBody ? clonedBody.substring(0, 2000) : null;

  try {
    await pool.query(
      `INSERT INTO error_log
         (route_pattern, route_path, method, status_code, ip_address, country_code,
          user_agent, request_headers, response_body, response_time_ms)
       VALUES ($1, $2, $3, $4, $5::inet, $6, $7, $8, $9, $10)`,
      [
        routePattern,
        pathname.substring(0, 512),
        event.request.method,
        statusCode,
        ip,
        countryCode,
        (event.request.headers.get('user-agent') || '').substring(0, 512) || null,
        JSON.stringify(headers),
        body,
        responseTime
      ]
    );
  } catch (e) {
    console.error('[error-log] Insert error:', e.message);
  }
}

/**
 * Record the error message from handleError (linked by route+timestamp proximity).
 * Called from handleError hook. Stores the error message on the most recent
 * matching error_log row that has no error_message yet.
 */
export async function recordErrorMessage(routeId, pathname, errorMessage) {
  try {
    await pool.query(
      `UPDATE error_log SET error_message = $1
       WHERE id = (
         SELECT id FROM error_log
         WHERE route_pattern = $2 AND route_path = $3
           AND error_message IS NULL
           AND created_at > now() - interval '5 seconds'
         ORDER BY created_at DESC LIMIT 1
       )`,
      [errorMessage?.substring(0, 2000) || null, routeId || pathname, pathname]
    );
  } catch { /* best effort */ }
}

/**
 * Prune old entries beyond MAX_PER_GROUP per (route_pattern, status_code).
 */
async function pruneExcess() {
  try {
    await pool.query(
      `DELETE FROM error_log WHERE id IN (
         SELECT id FROM (
           SELECT id, ROW_NUMBER() OVER (
             PARTITION BY route_pattern, status_code ORDER BY created_at DESC
           ) AS rn FROM error_log
         ) ranked WHERE rn > ${MAX_PER_GROUP}
       )`
    );
  } catch (e) {
    console.error('[error-log] Prune error:', e.message);
  }

  // Clean dedup map
  const now = Date.now();
  for (const [key, ts] of recentErrors) {
    if (now - ts > DEDUP_MS * 10) recentErrors.delete(key);
  }
}

/**
 * Initialize error log (start prune timer).
 */
export function initErrorLog() {
  setInterval(() => {
    pruneExcess().catch(() => {});
  }, PRUNE_INTERVAL_MS).unref();
  // Initial prune
  pruneExcess().catch(() => {});
}
