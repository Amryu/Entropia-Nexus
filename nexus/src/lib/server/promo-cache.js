// @ts-nocheck
/**
 * In-memory cache for active promos with view-tracking buffer.
 *
 * - getActivePromos(): returns promos grouped by slot type, cached for 60s
 * - invalidatePromoCache(): forces refresh on next call
 * - bufferPromoView(bookingIds, request): buffers view counts, flushes to DB every 60s
 */
import { getActivePromosForHomepage, incrementPromoMetrics, pool } from '$lib/server/db.js';
import { getClientIp, isBot, isBotIp, hasSuspectHeaders } from '$lib/server/route-analytics.js';

// ---------- promo cache ----------
let cache = null;
let cacheTime = 0;
const CACHE_TTL = 60_000; // 60 seconds

/**
 * Get active promos grouped by slot type.
 * Results are cached in-memory for CACHE_TTL ms.
 * @returns {Promise<{ placements: { left: Array, right: Array }, featuredPosts: Array }>}
 */
export async function getActivePromos() {
  const now = Date.now();
  if (cache && now - cacheTime < CACHE_TTL) return cache;

  const rows = await getActivePromosForHomepage();

  const placements = { left: [], right: [] };
  const featuredPosts = [];

  for (const row of rows) {
    const entry = {
      booking_id: row.booking_id,
      promo_id: row.promo_id,
      name: row.name,
      title: row.title,
      summary: row.summary,
      link: row.link,
      content_html: row.content_html,
      images: row.images
    };

    if (row.slot_type === 'left') {
      placements.left.push(entry);
    } else if (row.slot_type === 'right') {
      placements.right.push(entry);
    } else if (row.slot_type === 'featured_post') {
      featuredPosts.push(entry);
    }
  }

  const result = { placements, featuredPosts };
  cache = result;
  cacheTime = Date.now();
  return result;
}

/**
 * Invalidate the promo cache, forcing a refresh on the next call.
 */
export function invalidatePromoCache() {
  cacheTime = 0;
}

// ---------- view tracking ----------
/** @type {Map<string, number>} key = "bookingId:YYYY-MM-DD" */
const viewBuffer = new Map();
let flushTimer = null;
const VIEW_FLUSH_INTERVAL = 60_000; // 60 seconds

/** @type {Map<string, number>} cached beacon IPs -> timestamp (proven browsers) */
const beaconIpCache = new Map();
const BEACON_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
const BEACON_CACHE_MAX_SIZE = 10_000;

/**
 * Format a Date as YYYY-MM-DD for the metrics date key.
 * @param {Date} d
 * @returns {string}
 */
function toDateStr(d) {
  return d.toISOString().slice(0, 10);
}

/**
 * Check whether the given IP has a beacon hit (proven browser).
 * Results are cached in-memory to avoid repeated DB lookups.
 * @param {string} ip
 * @returns {Promise<boolean>}
 */
async function hasBeaconHit(ip) {
  const now = Date.now();
  const cached = beaconIpCache.get(ip);
  if (cached !== undefined && now - cached < BEACON_CACHE_TTL) return true;
  // Expired or not cached — re-query
  if (cached !== undefined) beaconIpCache.delete(ip);
  try {
    const { rows } = await pool.query(
      `SELECT 1 FROM beacon_hits WHERE ip_address = $1`,
      [ip]
    );
    if (rows.length > 0) {
      // Evict oldest entry if at max size
      if (beaconIpCache.size >= BEACON_CACHE_MAX_SIZE) {
        const oldestKey = beaconIpCache.keys().next().value;
        beaconIpCache.delete(oldestKey);
      }
      beaconIpCache.set(ip, now);
      return true;
    }
  } catch {
    // beacon_hits table may not exist yet
  }
  return false;
}

/**
 * Flush the view buffer to the database.
 */
async function flushViewBuffer() {
  if (viewBuffer.size === 0) return;

  const entries = [...viewBuffer.entries()];
  viewBuffer.clear();

  for (const [key, views] of entries) {
    const sepIdx = key.indexOf(':');
    const bookingId = parseInt(key.slice(0, sepIdx), 10);
    const date = key.slice(sepIdx + 1);
    try {
      await incrementPromoMetrics(bookingId, date, views, 0);
    } catch (e) {
      console.error('[promo-cache] Failed to flush view metrics:', e.message);
    }
  }
}

/**
 * Buffer a promo view for one or more booking IDs.
 * Filters out bots and non-beacon IPs before counting.
 * @param {number[]} bookingIds - booking IDs shown on this page load
 * @param {import('@sveltejs/kit').RequestEvent} event - the SvelteKit request event
 */
export async function bufferPromoView(bookingIds, event) {
  if (!bookingIds || bookingIds.length === 0) return;

  const ua = event.request.headers.get('user-agent') || '';
  const ip = getClientIp(event);

  // Filter bots
  if (isBot(ua, 'GET')) return;
  if (isBotIp(ip)) return;
  if (hasSuspectHeaders(event.request, ua)) return;

  // Only count proven browsers (beacon hit)
  const proven = await hasBeaconHit(ip);
  if (!proven) return;

  const dateStr = toDateStr(new Date());

  for (const bookingId of bookingIds) {
    const key = `${bookingId}:${dateStr}`;
    viewBuffer.set(key, (viewBuffer.get(key) || 0) + 1);
  }

  // Start flush timer on first buffered view
  if (!flushTimer) {
    flushTimer = setInterval(() => {
      flushViewBuffer().catch(e =>
        console.error('[promo-cache] View buffer flush error:', e.message)
      );
    }, VIEW_FLUSH_INTERVAL);
    flushTimer.unref();
  }
}
