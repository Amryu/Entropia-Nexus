// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * GET /api/admin/analytics/bots/ip-analysis
 *
 * Analyzes IP patterns in route_visits to detect potential crawler networks.
 * Groups IPs by /24 subnet and scores based on:
 *   - Request volume from the subnet
 *   - Number of distinct IPs (distributed crawling signal)
 *   - Number of distinct user agents (UA rotation signal)
 *   - Bot ratio already flagged
 *   - Request rate (requests per IP — high = automated)
 *   - Diversity of routes hit (crawlers tend to hit many different pages)
 *
 * Returns subnets ranked by suspicion score, excluding already-blocked ranges.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const days = Math.min(30, Math.max(1, parseInt(url.searchParams.get('days') || '7', 10)));

  try {
    // Get existing blocked ranges to exclude
    const { rows: blocked } = await pool.query(
      `SELECT cidr::text FROM bot_ip_ranges WHERE enabled = true`
    );
    const blockedCidrs = blocked.map(r => r.cidr);

    // Analyze /24 subnets (IPv4 only)
    // network(ip::cidr) truncates to the subnet, but we need /24 specifically
    const { rows: subnets } = await pool.query(
      `WITH subnet_stats AS (
         SELECT
           -- Extract /24 subnet: set last octet to 0
           set_masklen(ip_address, 24) AS subnet,
           count(*)::integer AS total_requests,
           count(DISTINCT ip_address)::integer AS distinct_ips,
           count(DISTINCT user_agent)::integer AS distinct_uas,
           count(DISTINCT route_path)::integer AS distinct_routes,
           count(*) FILTER (WHERE is_bot)::integer AS bot_count,
           count(DISTINCT CASE WHEN NOT is_bot THEN ip_address END)::integer AS non_bot_ips,
           min(visited_at) AS first_seen,
           max(visited_at) AS last_seen
         FROM route_visits
         WHERE visited_at >= now() - interval '${days} days'
           AND ip_address IS NOT NULL
           AND family(ip_address) = 4
         GROUP BY set_masklen(ip_address, 24)
         HAVING count(*) >= 10  -- minimum activity threshold
       )
       SELECT
         subnet::text,
         total_requests,
         distinct_ips,
         distinct_uas,
         distinct_routes,
         bot_count,
         non_bot_ips,
         first_seen,
         last_seen,
         -- Suspicion score: higher = more likely a crawler network
         (
           -- High request volume per IP suggests automation
           CASE WHEN distinct_ips > 0 THEN least(total_requests::float / distinct_ips, 100) ELSE 0 END * 2
           -- Many distinct UAs from same subnet = UA rotation
           + CASE WHEN distinct_uas > distinct_ips * 2 THEN 30 ELSE
               CASE WHEN distinct_uas > distinct_ips THEN 15 ELSE 0 END END
           -- Many IPs in same /24 hitting the site = distributed crawling
           + least(distinct_ips, 50) * 1.5
           -- High existing bot ratio
           + CASE WHEN total_requests > 0 THEN (bot_count::float / total_requests * 40) ELSE 0 END
           -- Hitting many distinct routes = systematic crawling
           + CASE WHEN distinct_routes > 50 THEN 20
               WHEN distinct_routes > 20 THEN 10 ELSE 0 END
         )::integer AS suspicion_score
       FROM subnet_stats
       ORDER BY suspicion_score DESC
       LIMIT 50`
    );

    // Filter out already-blocked subnets
    const results = subnets.filter(s => {
      const subnetStr = s.subnet;
      return !blockedCidrs.some(cidr => {
        // Simple check: if the blocked CIDR covers this /24
        // This is approximate — for exact matching we'd use PG's >> operator
        return subnetStr.startsWith(cidr.split('/')[0].split('.').slice(0, 2).join('.'));
      });
    });

    // For the top suspicious subnets, fetch sample IPs + UAs
    const topSubnets = results.slice(0, 20);
    const samples = {};
    if (topSubnets.length > 0) {
      for (const subnet of topSubnets.slice(0, 5)) {
        const subnetBase = subnet.subnet.split('/')[0];
        const { rows: ips } = await pool.query(
          `SELECT ip_address::text AS ip, user_agent, count(*)::integer AS requests,
                  bool_or(is_bot) AS flagged_bot
           FROM route_visits
           WHERE visited_at >= now() - interval '${days} days'
             AND ip_address << $1::cidr
           GROUP BY ip_address, user_agent
           ORDER BY requests DESC
           LIMIT 10`,
          [subnet.subnet]
        );
        samples[subnetBase] = ips;
      }
    }

    return json({ subnets: results, samples, days });
  } catch (e) {
    console.error('[analytics] IP analysis error:', e);
    return json({ error: 'Failed to analyze IP patterns' }, { status: 500 });
  }
}
