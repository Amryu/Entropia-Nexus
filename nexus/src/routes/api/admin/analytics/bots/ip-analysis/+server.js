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

    // Find smallest CIDR covering groups of suspicious /24s.
    // Group by progressively wider prefixes (/23, /22, ... /16) and pick
    // the tightest grouping that contains 2+ suspicious subnets.
    function ipToInt(ip) {
      const p = ip.split('.').map(Number);
      return ((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]) >>> 0;
    }
    function intToIp(n) {
      return `${(n >>> 24) & 0xFF}.${(n >>> 16) & 0xFF}.${(n >>> 8) & 0xFF}.${n & 0xFF}`;
    }
    function smallestCovering(subnetCidrs) {
      const ips = subnetCidrs.map(s => ipToInt(s.split('/')[0]));
      let diff = 0;
      for (let i = 1; i < ips.length; i++) diff |= (ips[0] ^ ips[i]);
      const prefixLen = diff === 0 ? 24 : Math.min(24, 31 - Math.floor(Math.log2(diff)));
      const mask = prefixLen === 0 ? 0 : (~0 << (32 - prefixLen)) >>> 0;
      return `${intToIp((ips[0] & mask) >>> 0)}/${prefixLen}`;
    }

    const unblockedSubnets = results.filter(s => !s.already_blocked);
    // Try grouping at each prefix length from /23 down to /16
    const supernets = [];
    const used = new Set();
    for (let bits = 23; bits >= 16; bits--) {
      const groups = {};
      for (const s of unblockedSubnets) {
        if (used.has(s.subnet)) continue;
        const ip = ipToInt(s.subnet.split('/')[0]);
        const mask = (~0 << (32 - bits)) >>> 0;
        const key = `${intToIp((ip & mask) >>> 0)}/${bits}`;
        if (!groups[key]) groups[key] = [];
        groups[key].push(s);
      }
      for (const [, group] of Object.entries(groups)) {
        if (group.length >= 2) {
          const cidrs = group.map(g => g.subnet);
          const covering = smallestCovering(cidrs);
          supernets.push({
            cidr: covering,
            subnets: cidrs,
            totalRequests: group.reduce((a, g) => a + g.total_requests, 0),
            totalIps: group.reduce((a, g) => a + g.distinct_ips, 0),
            totalScore: group.reduce((a, g) => a + g.suspicion_score, 0),
          });
          cidrs.forEach(c => used.add(c));
        }
      }
    }
    supernets.sort((a, b) => b.subnets.length - a.subnets.length);

    return json({ subnets: results, samples, supernets, days });
  } catch (e) {
    console.error('[analytics] IP analysis error:', e);
    return json({ error: 'Failed to analyze IP patterns' }, { status: 500 });
  }
}
