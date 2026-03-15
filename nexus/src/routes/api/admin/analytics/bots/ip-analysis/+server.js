// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * GET /api/admin/analytics/bots/ip-analysis
 *
 * Analyzes IP patterns in route_visits to detect potential crawler networks.
 * Groups IPs by /24 subnet and scores by request rate, UA rotation,
 * distributed IPs, existing bot ratio, and route diversity.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const days = Math.min(30, Math.max(1, parseInt(url.searchParams.get('days') || '7', 10)));

  try {
    const { rows: subnets } = await pool.query(
      `WITH subnet_stats AS (
         SELECT
           network(set_masklen(ip_address, 24)) AS subnet,
           count(*)::integer AS total_requests,
           count(DISTINCT ip_address)::integer AS distinct_ips,
           count(DISTINCT user_agent)::integer AS distinct_uas,
           count(DISTINCT route_path)::integer AS distinct_routes,
           count(*) FILTER (WHERE is_bot)::integer AS bot_count,
           count(DISTINCT CASE WHEN NOT is_bot THEN ip_address END)::integer AS non_bot_ips,
           count(DISTINCT date_trunc('hour', visited_at))::integer AS active_hours,
           min(visited_at) AS first_seen,
           max(visited_at) AS last_seen
         FROM route_visits
         WHERE visited_at >= now() - $1 * interval '1 day'
           AND ip_address IS NOT NULL
           AND family(ip_address) = 4
           AND is_api = false
         GROUP BY network(set_masklen(ip_address, 24))
         HAVING count(*) >= 50
       )
       SELECT
         subnet::text,
         total_requests,
         distinct_ips,
         distinct_uas,
         distinct_routes,
         bot_count,
         non_bot_ips,
         active_hours,
         first_seen,
         last_seen,
         (
           -- High request volume per IP = automation
           CASE WHEN distinct_ips > 0 THEN least(total_requests::float / distinct_ips, 100) ELSE 0 END * 2
           -- UA rotation (more UAs than IPs)
           + CASE WHEN distinct_uas > distinct_ips * 2 THEN 30
               WHEN distinct_uas > distinct_ips THEN 15 ELSE 0 END
           -- Many IPs in same /24 = distributed crawling
           + least(distinct_ips, 50) * 1.5
           -- Already flagged as bots
           + CASE WHEN total_requests > 0 THEN (bot_count::float / total_requests * 40) ELSE 0 END
           -- Hitting many routes = systematic crawling
           + CASE WHEN distinct_routes > 50 THEN 20
               WHEN distinct_routes > 20 THEN 10 ELSE 0 END
           -- Constant activity across many hours = automated (humans sleep/work)
           + CASE WHEN active_hours > 20 THEN 30
               WHEN active_hours > 12 THEN 20
               WHEN active_hours > 6 THEN 10 ELSE 0 END
         )::integer AS suspicion_score,
         -- Check if this subnet is already covered by an enabled bot_ip_range
         -- <<= means "contained within or equal" (so /24 matches itself or a wider range)
         EXISTS(
           SELECT 1 FROM bot_ip_ranges br
           WHERE br.enabled = true AND subnet <<= br.cidr
         ) AS already_blocked,
         -- If blocked, show which range covers it
         (SELECT br.cidr::text FROM bot_ip_ranges br
          WHERE br.enabled = true AND subnet <<= br.cidr
          ORDER BY masklen(br.cidr) DESC LIMIT 1
         ) AS blocked_by
       FROM subnet_stats
       ORDER BY suspicion_score DESC
       LIMIT 50`,
      [days]
    );

    // Keep all subnets, sort: unblocked first (by score), then blocked
    const results = [
      ...subnets.filter(s => !s.already_blocked),
      ...subnets.filter(s => s.already_blocked)
    ];

    // Fetch sample IPs for ALL detected subnets
    const samples = {};
    for (const subnet of results) {
      const { rows: ips } = await pool.query(
        `SELECT ip_address::text AS ip, user_agent, count(*)::integer AS requests,
                bool_or(is_bot) AS flagged_bot
         FROM route_visits
         WHERE visited_at >= now() - $1 * interval '1 day'
           AND ip_address << $2::cidr
           AND is_api = false
         GROUP BY ip_address, user_agent
         ORDER BY requests DESC
         LIMIT 10`,
        [days, subnet.subnet]
      );
      const subnetBase = subnet.subnet.split('/')[0];
      samples[subnetBase] = ips;
    }

    // Detect larger subnets: group /24s by their /16 prefix and flag
    // when multiple suspicious /24s share the same /16
    const supernetMap = {};
    for (const s of results) {
      if (s.already_blocked) continue;
      const parts = s.subnet.split('.');
      const slash16 = `${parts[0]}.${parts[1]}.0.0/16`;
      if (!supernetMap[slash16]) supernetMap[slash16] = { subnets: [], totalRequests: 0, totalIps: 0, totalScore: 0 };
      supernetMap[slash16].subnets.push(s.subnet);
      supernetMap[slash16].totalRequests += s.total_requests;
      supernetMap[slash16].totalIps += s.distinct_ips;
      supernetMap[slash16].totalScore += s.suspicion_score;
    }
    // Only report /16s with 2+ suspicious /24s
    const supernets = Object.entries(supernetMap)
      .filter(([, v]) => v.subnets.length >= 2)
      .map(([cidr, v]) => ({ cidr, ...v }))
      .sort((a, b) => b.subnets.length - a.subnets.length);

    return json({ subnets: results, samples, supernets, days });
  } catch (e) {
    console.error('[analytics] IP analysis error:', e);
    return json({ error: 'Failed to analyze IP patterns' }, { status: 500 });
  }
}
