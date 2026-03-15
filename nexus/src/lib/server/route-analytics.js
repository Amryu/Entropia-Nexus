// @ts-nocheck
/**
 * Route analytics collector.
 *
 * Records page views and API requests in an in-memory buffer, then flushes
 * to the route_visits table every FLUSH_INTERVAL_MS.  GeoIP country resolution
 * and bot detection happen synchronously (microsecond lookups).
 *
 * Lifecycle:
 *   initRouteAnalytics()  — called once from hooks.server.js at startup
 *   recordVisit(event, response, startTime) — called fire-and-forget after resolve()
 *   reloadBotPatterns()   — called when admin changes patterns
 */
import { pool } from '$lib/server/db.js';

// ---------- constants ----------
const FLUSH_INTERVAL_MS = 10_000;       // flush buffer to DB every 10 s
const PRUNE_INTERVAL_MS = 60 * 60_000;  // prune old rows every hour
const RETENTION_DAYS = 30;
const MAX_BUFFER_SIZE = 10_000;
const BATCH_INSERT_SIZE = 500;
const RATE_LIMIT_DEDUP_MS = 60_000;     // only record one 429 per IP+route per minute

// ---------- state ----------
let buffer = [];
let botRegex = null;                    // compiled from DB patterns
let botIpRanges = [];                   // [{ ipInt, maskInt, cidr }] for CIDR matching
let geoLookup = null;                   // geoip-lite lookup function
const rateLimitDedup = new Map();       // key → last-recorded timestamp

// Site host(s) for referrer filtering — set during init
let siteHosts = new Set();

// ---------- skip patterns ----------
const SKIP_PREFIXES = ['/_app/', '/static/', '/node_modules/', '/api/admin/analytics/'];
const SKIP_EXACT = new Set(['/favicon.ico', '/robots.txt', '/sitemap.xml']);

function shouldSkip(pathname, method) {
  if (method === 'OPTIONS') return true;
  if (SKIP_EXACT.has(pathname)) return true;
  for (const prefix of SKIP_PREFIXES) {
    if (pathname.startsWith(prefix)) return true;
  }
  return false;
}

// ---------- IP extraction ----------
// Rough check: must look like an IPv4 or IPv6 address (rejects garbage strings
// that would cause the PostgreSQL inet type to throw and kill the entire batch).
const IP_PATTERN = /^[\d.:a-fA-F]+$/;

function getClientIp(event) {
  // CF-Connecting-IP is set by Cloudflare and cannot be spoofed — check first.
  // X-Forwarded-For can be spoofed by clients (Cloudflare appends to it, so the
  // first entry may be attacker-controlled).
  const cfIp = event.request.headers.get('cf-connecting-ip');
  if (cfIp && IP_PATTERN.test(cfIp)) return cfIp;
  const xff = event.request.headers.get('x-forwarded-for');
  if (xff) {
    // Take the last entry — that's what the nearest trusted proxy (Cloudflare/nginx) added.
    const parts = xff.split(',');
    const last = parts[parts.length - 1].trim();
    if (last && IP_PATTERN.test(last)) return last;
  }
  try {
    return event.getClientAddress();
  } catch {
    return '0.0.0.0';
  }
}

// ---------- referrer parsing ----------
function parseExternalReferrer(referrerHeader) {
  if (!referrerHeader) return null;
  try {
    const url = new URL(referrerHeader);
    const host = url.hostname.toLowerCase();
    if (siteHosts.has(host)) return null;          // same-origin
    return host;
  } catch {
    return null;
  }
}

// ---------- route helpers ----------
function extractCategory(pathname) {
  if (pathname === '/') return 'home';
  const seg = pathname.split('/')[1];
  return seg || 'home';
}

// ---------- IP-based bot detection ----------
function ipv4ToInt(ip) {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let num = 0;
  for (let i = 0; i < 4; i++) {
    const octet = parseInt(parts[i], 10);
    if (isNaN(octet) || octet < 0 || octet > 255) return null;
    num = (num * 256) + octet;
  }
  return num >>> 0; // unsigned 32-bit
}

function isBotIp(ip) {
  if (botIpRanges.length === 0) return false;
  const ipInt = ipv4ToInt(ip);
  if (ipInt === null) return false; // skip IPv6 for now
  for (const range of botIpRanges) {
    if ((ipInt & range.maskInt) === range.netInt) return true;
  }
  return false;
}

export async function reloadBotIpRanges() {
  try {
    const { rows } = await pool.query(
      `SELECT cidr::text FROM bot_ip_ranges WHERE enabled = true ORDER BY id`
    );
    const ranges = [];
    for (const row of rows) {
      // cidr comes as e.g. "43.128.0.0/10"
      const [ipStr, bitsStr] = row.cidr.split('/');
      const bits = parseInt(bitsStr, 10);
      const ipInt = ipv4ToInt(ipStr);
      if (ipInt === null || isNaN(bits)) continue;
      const maskInt = bits === 0 ? 0 : (~0 << (32 - bits)) >>> 0;
      ranges.push({ netInt: (ipInt & maskInt) >>> 0, maskInt });
    }
    botIpRanges = ranges;
  } catch (e) {
    console.error('[route-analytics] Failed to load bot IP ranges:', e.message);
  }
}

// ---------- bot detection ----------

// Minimum plausible browser versions (roughly 2021 era).
// Anything older is almost certainly a bot using a stale/randomized UA.
const MIN_BROWSER_VERSIONS = [
  { pattern: /Chrome\/(\d+)/, min: 90 },    // Chrome 90 = Apr 2021
  { pattern: /Firefox\/(\d+)/, min: 90 },    // Firefox 90 = Jul 2021
  { pattern: /Version\/(\d+).*Safari/, min: 14 }, // Safari 14 = Sep 2020
  { pattern: /Edg(?:e|A|iOS)?\/(\d+)/, min: 90 },
  { pattern: /OPR\/(\d+)/, min: 77 },        // Opera 77 ≈ Chrome 91
  { pattern: /SamsungBrowser\/(\d+)/, min: 14 },
];

function hasAncientBrowser(ua) {
  for (const { pattern, min } of MIN_BROWSER_VERSIONS) {
    const m = ua.match(pattern);
    if (m) return parseInt(m[1], 10) < min;
  }
  return false;
}

function isBot(userAgent, method) {
  // HEAD requests are almost never from real browsers
  if (method === 'HEAD') return true;
  // Missing user-agent is a strong bot signal
  if (!userAgent) return true;
  // Ancient browser versions are randomized bot UAs
  if (hasAncientBrowser(userAgent)) return true;
  if (!botRegex) return false;
  return botRegex.test(userAgent);
}

// ---------- GeoIP ----------
function lookupCountry(ip) {
  if (!geoLookup) return null;
  try {
    const result = geoLookup(ip);
    return result?.country || null;
  } catch {
    return null;
  }
}

// ---------- buffer flush ----------
let flushing = false;

async function flushBuffer() {
  if (buffer.length === 0 || flushing) return;
  flushing = true;

  // Atomic swap
  const batch = buffer;
  buffer = [];

  // Process in chunks
  for (let i = 0; i < batch.length; i += BATCH_INSERT_SIZE) {
    const chunk = batch.slice(i, i + BATCH_INSERT_SIZE);
    const values = [];
    const params = [];
    let idx = 1;

    for (const row of chunk) {
      values.push(`($${idx},$${idx + 1},$${idx + 2},$${idx + 3},$${idx + 4},$${idx + 5},$${idx + 6},$${idx + 7},$${idx + 8},$${idx + 9},$${idx + 10},$${idx + 11},$${idx + 12},$${idx + 13},$${idx + 14})`);
      params.push(
        row.visited_at,
        row.ip_address,
        row.country_code,
        row.user_agent,
        row.route_category,
        row.route_pattern,
        row.route_path,
        row.method,
        row.status_code,
        row.referrer,
        row.is_bot,
        row.is_api,
        row.oauth_client_id,
        row.rate_limited,
        row.response_time_ms
      );
      idx += 15;
    }

    try {
      await pool.query(
        `INSERT INTO route_visits (visited_at, ip_address, country_code, user_agent, route_category, route_pattern, route_path, method, status_code, referrer, is_bot, is_api, oauth_client_id, rate_limited, response_time_ms)
         VALUES ${values.join(',')}`,
        params
      );
    } catch (e) {
      console.error('[route-analytics] Flush error:', e.message);
    }
  }

  flushing = false;
}

// ---------- pruning ----------
const PRUNE_BATCH_SIZE = 10_000;

async function pruneOldRows() {
  try {
    // Delete in batches to avoid long-running locks
    let totalPruned = 0;
    let deleted;
    do {
      const result = await pool.query(
        `DELETE FROM route_visits WHERE id IN (
           SELECT id FROM route_visits WHERE visited_at < now() - interval '${RETENTION_DAYS} days'
           LIMIT ${PRUNE_BATCH_SIZE}
         )`
      );
      deleted = result.rowCount || 0;
      totalPruned += deleted;
    } while (deleted === PRUNE_BATCH_SIZE);

    if (totalPruned > 0) {
      console.log(`[route-analytics] Pruned ${totalPruned} rows older than ${RETENTION_DAYS} days`);
    }
  } catch (e) {
    console.error('[route-analytics] Prune error:', e.message);
  }

  // Also clean up stale dedup entries
  const now = Date.now();
  for (const [key, ts] of rateLimitDedup) {
    if (now - ts > RATE_LIMIT_DEDUP_MS * 2) rateLimitDedup.delete(key);
  }
}

// ---------- bot pattern loading ----------
export async function reloadBotPatterns() {
  try {
    const { rows } = await pool.query(
      `SELECT pattern FROM bot_patterns WHERE enabled = true ORDER BY id`
    );
    if (rows.length === 0) {
      botRegex = null;
      return;
    }
    // Combine into alternation, case-insensitive
    const combined = rows.map(r => r.pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    botRegex = new RegExp(combined, 'i');
  } catch (e) {
    console.error('[route-analytics] Failed to load bot patterns:', e.message);
  }
}

// ---------- public API ----------

/**
 * Record a visit (fire-and-forget, synchronous push to buffer).
 */
export function recordVisit(event, response, startTime) {
  const pathname = event.url.pathname;
  const method = event.request.method;

  if (shouldSkip(pathname, method)) return;

  const routeId = event.route?.id;
  // Skip if no route matched and it's a static-looking path
  if (!routeId && (pathname.includes('.') || pathname.startsWith('/__'))) return;

  const ip = getClientIp(event);
  const userAgent = event.request.headers.get('user-agent') || null;
  const referrerHeader = event.request.headers.get('referer') || event.request.headers.get('referrer') || null;
  const statusCode = response.status;
  const isRateLimited = statusCode === 429;

  // 429 dedup: skip if we recorded a 429 for same IP+route recently
  if (isRateLimited) {
    const dedupKey = `${ip}:${routeId || pathname}`;
    const lastRecorded = rateLimitDedup.get(dedupKey);
    const now = Date.now();
    if (lastRecorded && now - lastRecorded < RATE_LIMIT_DEDUP_MS) return;
    rateLimitDedup.set(dedupKey, now);
  }

  const routePattern = routeId || pathname;
  const routeCategory = extractCategory(pathname);
  const isApiRoute = pathname.startsWith('/api/');
  const botFlag = isBot(userAgent, method) || isBotIp(ip);
  const countryCode = lookupCountry(ip);
  const externalReferrer = parseExternalReferrer(referrerHeader);

  // Cap buffer to prevent memory issues under extreme load
  if (buffer.length >= MAX_BUFFER_SIZE) return;

  buffer.push({
    visited_at: new Date(),
    ip_address: ip,
    country_code: countryCode,
    user_agent: userAgent ? userAgent.substring(0, 512) : null,
    route_category: routeCategory,
    route_pattern: routePattern,
    route_path: pathname.substring(0, 512),
    method,
    status_code: statusCode,
    referrer: externalReferrer,
    is_bot: botFlag,
    is_api: isApiRoute,
    oauth_client_id: event.locals?.oauthClientId || null,
    rate_limited: isRateLimited,
    response_time_ms: startTime ? (Date.now() - startTime) : null
  });
}

/**
 * Initialize the analytics collector.
 * Call once from hooks.server.js at import time.
 */
export async function initRouteAnalytics() {
  // Load GeoIP (lazy)
  try {
    const geoip = await import('geoip-lite');
    geoLookup = geoip.default?.lookup || geoip.lookup;
  } catch (e) {
    console.warn('[route-analytics] geoip-lite not available, country resolution disabled:', e.message);
  }

  // Build site host set for referrer filtering
  try {
    const viteUrl = process.env.VITE_URL || process.env.CANONICAL_PUBLIC_URL || '';
    if (viteUrl) {
      const parsed = new URL(viteUrl);
      siteHosts.add(parsed.hostname.toLowerCase());
    }
    // Always include common local hosts
    siteHosts.add('localhost');
    siteHosts.add('127.0.0.1');
    // Add canonical and short-URL domains
    siteHosts.add('entropianexus.com');
    siteHosts.add('www.entropianexus.com');
    siteHosts.add('dev.entropianexus.com');
    siteHosts.add('eunex.us');
    siteHosts.add('www.eunex.us');
  } catch { /* ignore */ }

  // Load bot patterns and IP ranges
  await reloadBotPatterns();
  await reloadBotIpRanges();

  // Start flush timer
  setInterval(() => {
    flushBuffer().catch(e => console.error('[route-analytics] Flush error:', e.message));
  }, FLUSH_INTERVAL_MS).unref();

  // Start prune timer
  setInterval(() => {
    pruneOldRows().catch(e => console.error('[route-analytics] Prune error:', e.message));
  }, PRUNE_INTERVAL_MS).unref();

  // Initial prune on startup
  pruneOldRows().catch(() => {});

  console.log('[route-analytics] Initialized (bot patterns: ' + (botRegex ? 'loaded' : 'none') + ', geoip: ' + (geoLookup ? 'ready' : 'disabled') + ')');
}

/**
 * Re-evaluate is_bot on all existing route_visits rows using current
 * bot patterns and version thresholds. Processes in batches to avoid
 * long-running locks.
 * @returns {{ updated: number }} count of rows whose is_bot flag changed
 */
export async function reevaluateBotFlags() {
  const BATCH = 5000;
  let totalUpdated = 0;
  let lastId = 0;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { rows } = await pool.query(
      `SELECT id, user_agent, method, ip_address::text AS ip FROM route_visits WHERE id > $1 ORDER BY id LIMIT ${BATCH}`,
      [lastId]
    );
    if (rows.length === 0) break;

    const toTrue = [];
    const toFalse = [];
    for (const row of rows) {
      const shouldBeBot = isBot(row.user_agent, row.method) || isBotIp(row.ip);
      if (shouldBeBot) toTrue.push(row.id);
      else toFalse.push(row.id);
    }

    // Batch update rows that should be true but might not be
    if (toTrue.length > 0) {
      const { rowCount } = await pool.query(
        `UPDATE route_visits SET is_bot = true WHERE id = ANY($1) AND is_bot = false`,
        [toTrue]
      );
      totalUpdated += rowCount || 0;
    }
    if (toFalse.length > 0) {
      const { rowCount } = await pool.query(
        `UPDATE route_visits SET is_bot = false WHERE id = ANY($1) AND is_bot = true`,
        [toFalse]
      );
      totalUpdated += rowCount || 0;
    }

    lastId = rows[rows.length - 1].id;
  }

  console.log(`[route-analytics] Re-evaluated bot flags: ${totalUpdated} rows changed`);
  return { updated: totalUpdated };
}
