// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * GET /api/admin/analytics/bots/ip-analysis
 *
 * Analyzes IP patterns in route_visits to detect potential crawler networks.
 * Groups IPs by /24 subnet and computes a breakdown of suspicion signals.
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
         HAVING count(*) >= 3
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
         EXISTS(
           SELECT 1 FROM bot_ip_ranges br
           WHERE br.enabled = true AND subnet <<= br.cidr
         ) AS already_blocked,
         (SELECT br.cidr::text FROM bot_ip_ranges br
          WHERE br.enabled = true AND subnet <<= br.cidr
          ORDER BY masklen(br.cidr) DESC LIMIT 1
         ) AS blocked_by
       FROM subnet_stats
       ORDER BY total_requests DESC
       LIMIT 100`,
      [days]
    );

    // Compute score breakdown in JS for transparency
    const scored = subnets.map(s => {
      const breakdown = {};

      // Requests per IP (capped at 100)
      const reqPerIp = s.distinct_ips > 0 ? Math.min(s.total_requests / s.distinct_ips, 100) : 0;
      breakdown.req_per_ip = Math.round(reqPerIp * 2);

      // UA rotation
      if (s.distinct_uas > s.distinct_ips * 2) breakdown.ua_rotation = 30;
      else if (s.distinct_uas > s.distinct_ips) breakdown.ua_rotation = 15;
      else breakdown.ua_rotation = 0;

      // Distributed IPs
      breakdown.distributed_ips = Math.round(Math.min(s.distinct_ips, 50) * 1.5);

      // Existing bot ratio
      breakdown.bot_ratio = s.total_requests > 0 ? Math.round((s.bot_count / s.total_requests) * 40) : 0;

      // Route diversity
      if (s.distinct_routes > 50) breakdown.route_diversity = 20;
      else if (s.distinct_routes > 20) breakdown.route_diversity = 10;
      else breakdown.route_diversity = 0;

      // Active hours — exponential: 2^(hours/4) capped at 100
      // 1h=1, 2h=1, 4h=2, 8h=4, 12h=8, 16h=16, 20h=32, 24h=64
      // This means even 30min of constant activity (1 active hour) contributes
      // minimally, but 12+ hours ramps up fast
      breakdown.active_hours = Math.min(Math.round(Math.pow(2, s.active_hours / 4)), 100);

      const suspicion_score = Object.values(breakdown).reduce((a, b) => a + b, 0);

      return { ...s, suspicion_score, breakdown };
    });

    // Sort: unblocked by score desc, then blocked
    scored.sort((a, b) => {
      if (a.already_blocked !== b.already_blocked) return a.already_blocked ? 1 : -1;
      return b.suspicion_score - a.suspicion_score;
    });

    // Filter out very low scores (< 10) unless blocked
    const results = scored.filter(s => s.already_blocked || s.suspicion_score >= 10);

    // Fetch sample IPs for all results
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

    // Detect /16 supernets
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
