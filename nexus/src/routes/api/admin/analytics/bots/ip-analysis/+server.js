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
           min(visited_at) AS first_seen,
           max(visited_at) AS last_seen
         FROM route_visits
         WHERE visited_at >= now() - $1 * interval '1 day'
           AND ip_address IS NOT NULL
           AND family(ip_address) = 4
         GROUP BY network(set_masklen(ip_address, 24))
         HAVING count(*) >= 10
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
         (
           CASE WHEN distinct_ips > 0 THEN least(total_requests::float / distinct_ips, 100) ELSE 0 END * 2
           + CASE WHEN distinct_uas > distinct_ips * 2 THEN 30
               WHEN distinct_uas > distinct_ips THEN 15 ELSE 0 END
           + least(distinct_ips, 50) * 1.5
           + CASE WHEN total_requests > 0 THEN (bot_count::float / total_requests * 40) ELSE 0 END
           + CASE WHEN distinct_routes > 50 THEN 20
               WHEN distinct_routes > 20 THEN 10 ELSE 0 END
         )::integer AS suspicion_score,
         -- Check if this subnet is already covered by an enabled bot_ip_range
         EXISTS(
           SELECT 1 FROM bot_ip_ranges br
           WHERE br.enabled = true AND subnet << br.cidr
         ) AS already_blocked
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
         GROUP BY ip_address, user_agent
         ORDER BY requests DESC
         LIMIT 10`,
        [days, subnet.subnet]
      );
      const subnetBase = subnet.subnet.split('/')[0];
      samples[subnetBase] = ips;
    }

    return json({ subnets: results, samples, days });
  } catch (e) {
    console.error('[analytics] IP analysis error:', e);
    return json({ error: 'Failed to analyze IP patterns' }, { status: 500 });
  }
}
