// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getClientIp } from '$lib/server/route-analytics.js';

// In-memory dedup to avoid DB writes on every page load
const recentIps = new Map();
const DEDUP_MS = 60 * 60_000; // 1 hour

export async function POST(event) {
  const ip = getClientIp(event);
  if (!ip || ip === '0.0.0.0') return new Response(null, { status: 204 });

  const now = Date.now();
  const last = recentIps.get(ip);
  if (last && now - last < DEDUP_MS) return new Response(null, { status: 204 });
  recentIps.set(ip, now);

  // Periodic cleanup
  if (recentIps.size > 5000) {
    for (const [k, v] of recentIps) {
      if (now - v > DEDUP_MS) recentIps.delete(k);
    }
  }

  pool.query(
    `INSERT INTO beacon_hits (ip_address, last_seen) VALUES ($1, now())
     ON CONFLICT (ip_address) DO UPDATE SET last_seen = now()`,
    [ip]
  ).catch(() => {});

  return new Response(null, { status: 204 });
}
