// @ts-nocheck
/**
 * GET /api/globals/target/[name] — Target-specific global event statistics.
 * Public endpoint, no auth required.
 *
 * Returns summary stats, top players, activity timeline, recent globals,
 * available maturities, and wiki link (for mobs).
 *
 * Query params:
 *   maturities — comma-separated target names to filter by specific maturities
 */
import { pool } from '$lib/server/db.js';
import { getResponse, encodeURIComponentSafe, decodeURIComponentSafe } from '$lib/util.js';
import { PERIOD_INTERVALS, getActivityBucket, fillActivityGaps, chooseRollupGranularity, buildRollupPeriodFilter, VALUE_PED } from '../../stats/filter-utils.js';
import { isRollupReady } from '$lib/server/globals-rollup.js';
import { initMobResolver, resolveMob, resolveMobByName } from '$lib/server/mobResolver.js';

// In-memory mob target resolution cache
const MOB_TARGET_CACHE_TTL = 5 * 60_000; // 5 min — mob associations rarely change
const MOB_TARGET_CACHE_MAX = 2000;
const mobTargetCache = new Map(); // key → { mobId, targets, cachedAt }

function getCachedMobTargets(targetName) {
  const key = targetName.toLowerCase();
  const entry = mobTargetCache.get(key);
  if (entry && Date.now() - entry.cachedAt < MOB_TARGET_CACHE_TTL) return entry;
  return null;
}

function cacheMobTargets(targetName, mobId, targets) {
  if (mobTargetCache.size >= MOB_TARGET_CACHE_MAX) {
    // Evict expired entries
    const cutoff = Date.now() - MOB_TARGET_CACHE_TTL;
    for (const [k, v] of mobTargetCache) {
      if (v.cachedAt < cutoff) mobTargetCache.delete(k);
    }
    // If still full, clear half
    if (mobTargetCache.size >= MOB_TARGET_CACHE_MAX) {
      const entries = [...mobTargetCache.keys()];
      for (let i = 0; i < entries.length / 2; i++) mobTargetCache.delete(entries[i]);
    }
  }
  const key = targetName.toLowerCase();
  const entry = { mobId, targets, cachedAt: Date.now() };
  mobTargetCache.set(key, entry);
  // Also cache each individual target name pointing to the same entry
  if (targets) {
    for (const t of targets) {
      mobTargetCache.set(t, entry);
    }
  }
}

// Server-side response cache (anonymous users only)
const RESPONSE_CACHE_TTL = 60_000; // 60 seconds
const RESPONSE_CACHE_MAX = 500;
const responseCache = new Map(); // key → { response, cachedAt }

/**
 * Extract the mob base name by stripping the maturity suffix.
 */
function extractMobName(targetName) {
  const parts = targetName.split(' ');
  if (parts.length < 2) return targetName;

  if (parts.length >= 4 && /^Gen$/i.test(parts[parts.length - 2]) && /^Elite$/i.test(parts[parts.length - 3])) {
    return parts.slice(0, -3).join(' ');
  }
  if (parts.length >= 3 && /^Gen$/i.test(parts[parts.length - 2])) {
    return parts.slice(0, -2).join(' ');
  }
  return parts.slice(0, -1).join(' ');
}

export async function GET({ params, url, locals }) {
  const targetName = decodeURIComponentSafe(params.name);

  if (!targetName || targetName.length > 300) {
    return getResponse({ error: 'Invalid target name' }, 400);
  }

  // Maturity filter: comma-separated list of specific target_name variants
  const maturityParam = url.searchParams.get('maturities');
  const maturityFilter = maturityParam
    ? maturityParam.split(',').map(m => m.trim()).filter(Boolean).slice(0, 50)
    : null;

  // Period / custom date range filter
  const period = url.searchParams.get('period') || 'all';
  const from = url.searchParams.get('from');
  const to = url.searchParams.get('to');

  const { sqlUnit: bucketUnit } = getActivityBucket(period, from, to);

  // Resolve mob: find all maturity target names sharing the same mob_id.
  // Uses the in-memory mobResolver for instant mob_id lookup (no DB subquery),
  // then queries by mob_id (indexed) for the actual target names in globals.
  let resolvedMobId = null;
  let resolvedTargets = null;
  if (!maturityFilter) {
    const cached = getCachedMobTargets(targetName);
    if (cached) {
      resolvedMobId = cached.mobId;
      resolvedTargets = cached.targets;
    } else {
      await initMobResolver();
      // Try exact target name first (e.g. "Atrox Young"), then base mob name (e.g. "Atrox")
      const resolved = resolveMob(targetName) || resolveMobByName(targetName);
      if (resolved) {
        // Got mob_id from in-memory resolver — just fetch sibling target names (indexed by mob_id)
        const mobLookup = await pool.query(
          `SELECT DISTINCT mob_id, lower(target_name) AS name FROM ingested_globals
           WHERE confirmed = true AND mob_id = $1`,
          [resolved.mobId]
        );
        if (mobLookup.rows.length > 0) {
          resolvedMobId = mobLookup.rows[0].mob_id;
          resolvedTargets = mobLookup.rows.map(r => r.name);
        }
      }
      cacheMobTargets(targetName, resolvedMobId, resolvedTargets);
    }
  }

  // Build the target name condition — resolved mob targets, maturity filter, or exact match
  let targetCond;
  let targetParams;
  if (maturityFilter && maturityFilter.length > 0) {
    targetCond = 'lower(target_name) = ANY($1)';
    targetParams = [maturityFilter.map(m => m.toLowerCase())];
  } else if (resolvedTargets) {
    targetCond = 'lower(target_name) = ANY($1)';
    targetParams = [resolvedTargets];
  } else {
    targetCond = 'lower(target_name) = lower($1)';
    targetParams = [targetName];
  }

  // Build period condition - custom date range appends params after $1
  let periodCond = '';
  if (from && to) {
    periodCond = ` AND event_timestamp >= $2 AND event_timestamp < $3`;
    targetParams.push(new Date(from), new Date(to + 'T23:59:59.999Z'));
  } else {
    const intervalSql = PERIOD_INTERVALS[period];
    if (intervalSql) {
      periodCond = ` AND event_timestamp > now() - ${intervalSql}`;
    }
  }

  // Determine if rollup tables can serve summary/activity queries
  const rollupGranularity = chooseRollupGranularity(period, from, to);
  const useRollup = rollupGranularity && isRollupReady() && (periodCond || period === 'all') && !maturityFilter;

  // Build rollup query for summary+activity (uses target_name from resolvedTargets or exact match)
  let rollupTargetCond, rollupTargetParams;
  if (useRollup) {
    if (resolvedTargets) {
      rollupTargetCond = 'lower(target_name) = ANY($1)';
      rollupTargetParams = [resolvedTargets];
    } else {
      rollupTargetCond = 'lower(target_name) = lower($1)';
      rollupTargetParams = [targetName];
    }
    const rpf = buildRollupPeriodFilter(rollupGranularity, period, from, to, 3);
    rollupTargetParams = [...rollupTargetParams, rollupGranularity, ...rpf.periodParams];
    var rollupPeriodWhere = rpf.periodWhere;
  }

  // Server-side response cache (anonymous users only — logged-in users get personalized gz data)
  const targetUserId = locals.session?.user ? String(locals.session.user.Id || locals.session.user.id) : null;
  const cacheKey = `${targetName}|${period}|${from || ''}|${to || ''}|${maturityParam || ''}`;
  if (!targetUserId) {
    const cached = responseCache.get(cacheKey);
    if (cached && Date.now() - cached.cachedAt < RESPONSE_CACHE_TTL) {
      return new Response(cached.json, {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=60' },
      });
    }
  }

  const q = pool.query.bind(pool);

  try {

    const [
      summaryResult,
      topPlayersResult,
      activityResult,
      recentResult,
      maturitiesResult,
      highestResult,
    ] = await Promise.all([
      // Summary stats (rollup or raw)
      useRollup
        ? q(
            `SELECT COALESCE(SUM(event_count), 0) AS total_count,
                    COALESCE(SUM(sum_value), 0) AS total_value,
                    COALESCE(SUM(sum_value), 0) / NULLIF(COALESCE(SUM(event_count), 0), 0) AS avg_value,
                    COALESCE(MAX(max_value), 0) AS max_value,
                    COALESCE(SUM(hof_count), 0) AS hof_count,
                    COALESCE(SUM(ath_count), 0) AS ath_count,
                    (SELECT global_type FROM globals_rollup_target
                     WHERE granularity = $2 AND ${rollupTargetCond}${rollupPeriodWhere}
                     GROUP BY global_type ORDER BY SUM(event_count) DESC LIMIT 1) AS primary_type,
                    MAX(mob_id) AS mob_id
             FROM globals_rollup_target
             WHERE granularity = $2 AND ${rollupTargetCond}${rollupPeriodWhere}`,
            rollupTargetParams
          )
        : q(
            `SELECT count(*) AS total_count,
                    COALESCE(sum(${VALUE_PED}), 0) AS total_value,
                    COALESCE(avg(${VALUE_PED}), 0) AS avg_value,
                    COALESCE(max(${VALUE_PED}), 0) AS max_value,
                    count(*) FILTER (WHERE is_hof) AS hof_count,
                    count(*) FILTER (WHERE is_ath) AS ath_count,
                    MIN(global_type) AS primary_type,
                    min(event_timestamp) AS first_seen,
                    max(event_timestamp) AS last_seen,
                    MAX(mob_id) AS mob_id
             FROM ingested_globals
             WHERE confirmed = true AND ${targetCond}${periodCond}`,
            targetParams
          ),

      // Top players by total value
      q(
        `SELECT player_name AS player, count(*) AS count,
                COALESCE(sum(${VALUE_PED}), 0) AS value,
                COALESCE(max(${VALUE_PED}), 0) AS best_value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}
         GROUP BY player_name
         ORDER BY sum(${VALUE_PED}) DESC
         LIMIT 50`,
        targetParams
      ),

      // Activity (rollup or raw)
      useRollup
        ? q(
            `SELECT period_start AS bucket, SUM(event_count) AS count,
                    COALESCE(SUM(sum_value), 0) AS total_value
             FROM globals_rollup_target
             WHERE granularity = $2 AND ${rollupTargetCond}${rollupPeriodWhere}
             GROUP BY period_start
             ORDER BY period_start
             LIMIT 2555`,
            rollupTargetParams
          )
        : q(
            `SELECT date_trunc('${bucketUnit}', event_timestamp) AS bucket,
                    count(*) AS count,
                    COALESCE(sum(${VALUE_PED}), 0) AS total_value
             FROM ingested_globals
             WHERE confirmed = true AND ${targetCond}${periodCond}
             GROUP BY 1
             ORDER BY 1
             LIMIT 2555`,
            targetParams
          ),

      // Recent globals (last 50)
      q(
        `SELECT id, global_type, player_name, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra,
                media_image_key, media_video_url
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}
         ORDER BY event_timestamp DESC
         LIMIT 50`,
        targetParams
      ),

      // Available maturities for this target (find all variants sharing the same mob_id)
      // Uses raw table — mob_id in rollup/agg tables has incomplete coverage
      resolvedMobId
        ? q(
            `SELECT target_name, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value
             FROM ingested_globals
             WHERE confirmed = true AND mob_id = $1
             GROUP BY target_name
             ORDER BY count(*) DESC`,
            [resolvedMobId]
          )
        : q(
            `SELECT target_name, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value
             FROM ingested_globals
             WHERE confirmed = true AND lower(target_name) = lower($1)
             GROUP BY target_name
             ORDER BY count(*) DESC`,
            [targetName]
          ),

      // Highest loot per timespan (always uses all-time data, ignoring period filter)
      q(
        `SELECT COALESCE(max(${VALUE_PED}), 0) AS highest_all,
                COALESCE(max(${VALUE_PED}) FILTER (WHERE event_timestamp > now() - interval '24 hours'), 0) AS highest_24h,
                COALESCE(max(${VALUE_PED}) FILTER (WHERE event_timestamp > now() - interval '7 days'), 0) AS highest_7d,
                COALESCE(max(${VALUE_PED}) FILTER (WHERE event_timestamp > now() - interval '30 days'), 0) AS highest_30d,
                COALESCE(max(${VALUE_PED}) FILTER (WHERE event_timestamp > now() - interval '1 year'), 0) AS highest_1y
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}`,
        maturityFilter ? [maturityFilter.map(m => m.toLowerCase())] : resolvedTargets ? [resolvedTargets] : [targetName]
      ),
    ]);

    const summary = summaryResult.rows[0];

    if (parseInt(summary.total_count) === 0) {
      return getResponse({ error: 'Target not found' }, 404);
    }

    // Derive wiki URL for mob targets (hunting types with mob_id)
    let wikiUrl = null;
    const mobId = resolvedMobId || summary.mob_id;
    const isHunting = summary.primary_type === 'kill' || summary.primary_type === 'team_kill';
    if (mobId && isHunting) {
      const mobName = maturitiesResult.rows.length > 1
        ? extractMobName(maturitiesResult.rows[0].target_name)
        : targetName;
      wikiUrl = `/information/mobs/${encodeURIComponentSafe(mobName)}`;
    }

    // Build maturities list (only if there are multiple variants)
    const maturities = maturitiesResult.rows.length > 1
      ? maturitiesResult.rows.map(r => ({
          target: r.target_name,
          count: parseInt(r.count),
          value: parseFloat(r.value),
        }))
      : [];

    // Batch lookup: gz counts for recent globals (replaces per-row correlated subqueries)
    const recentGlobalIds = recentResult.rows.map(r => r.id).filter(Boolean);
    const gzCountMap = new Map();
    if (recentGlobalIds.length > 0) {
      const { rows: gzCountRows } = await pool.query(
        `SELECT global_id, COUNT(*)::int AS gz_count FROM globals_gz WHERE global_id = ANY($1) GROUP BY global_id`,
        [recentGlobalIds]
      );
      for (const r of gzCountRows) gzCountMap.set(r.global_id, r.gz_count);
    }

    // Batch lookup: which globals has the current user GZ'd?
    const targetUserGzSet = new Set();
    if (targetUserId) {
      if (recentGlobalIds.length > 0) {
        const { rows: gzRows } = await pool.query(
          `SELECT global_id FROM globals_gz WHERE user_id = $1 AND global_id = ANY($2)`,
          [targetUserId, recentGlobalIds]
        );
        for (const r of gzRows) targetUserGzSet.add(r.global_id);
      }
    }

    const responseJson = JSON.stringify({
      target: targetName,
      primary_type: summary.primary_type,
      mob_id: mobId,
      wiki_url: wikiUrl,
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        avg_value: parseFloat(summary.avg_value),
        max_value: parseFloat(summary.max_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        first_seen: summary.first_seen,
        last_seen: summary.last_seen,
      },
      highest: {
        all: parseFloat(highestResult.rows[0].highest_all),
        '24h': parseFloat(highestResult.rows[0].highest_24h),
        '7d': parseFloat(highestResult.rows[0].highest_7d),
        '30d': parseFloat(highestResult.rows[0].highest_30d),
        '1y': parseFloat(highestResult.rows[0].highest_1y),
      },
      maturities,
      top_players: topPlayersResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        best_value: parseFloat(r.best_value),
        is_team: r.has_team && !r.has_solo,
      })),
      bucket_unit: bucketUnit,
      activity: fillActivityGaps(
        activityResult.rows.map(r => ({ bucket: new Date(r.bucket).toISOString(), count: parseInt(r.count), value: parseFloat(r.total_value || 0) })),
        bucketUnit, from, to, period
      ),
      recent: (() => {
        return recentResult.rows.map(r => ({
          id: r.id,
          type: r.global_type,
          player: r.player_name,
          target: r.target_name,
          value: parseFloat(r.value),
          unit: r.value_unit,
          location: r.location,
          hof: r.is_hof,
          ath: r.is_ath,
          timestamp: r.event_timestamp,
          mob_id: r.mob_id,
          maturity_id: r.maturity_id,
          extra: r.extra,
          media_image: r.media_image_key || null,
          media_video: r.media_video_url || null,
          gz_count: gzCountMap.get(r.id) || 0,
          ...(targetUserId != null && { user_gz: targetUserGzSet.has(r.id) }),
        }));
      })(),
    });

    // Cache JSON for anonymous users
    if (!targetUserId) {
      if (responseCache.size >= RESPONSE_CACHE_MAX) {
        const cutoff = Date.now() - RESPONSE_CACHE_TTL;
        for (const [k, v] of responseCache) {
          if (v.cachedAt < cutoff) responseCache.delete(k);
        }
      }
      responseCache.set(cacheKey, { json: responseJson, cachedAt: Date.now() });
    }
    return new Response(responseJson, {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': targetUserId ? 'private, max-age=60' : 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/target] Error fetching target globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
