// @ts-nocheck
/**
 * GET /api/globals — Paginated, filterable list of confirmed global events.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;
const VALID_GLOBAL_TYPES = new Set(['kill', 'team_kill', 'deposit', 'craft', 'rare_item', 'discovery', 'tier', 'examine', 'pvp']);
const MAX_TYPE_FILTERS = 10;

function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

export async function GET({ url, locals }) {
  const params = [];
  const conditions = ['confirmed = true'];
  let paramIdx = 1;

  // --- Filters ---

  // Type filter (comma-separated, validated against known types)
  const typeFilter = url.searchParams.get('type');
  if (typeFilter) {
    const types = typeFilter.split(',').map(t => t.trim()).filter(t => VALID_GLOBAL_TYPES.has(t));
    if (types.length > 0) {
      conditions.push(`global_type = ANY($${paramIdx})`);
      params.push(types.slice(0, MAX_TYPE_FILTERS));
      paramIdx++;
    }
  }

  // Player filter (case-insensitive substring)
  const playerFilter = url.searchParams.get('player');
  if (playerFilter) {
    conditions.push(`player_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(playerFilter)}%`);
    paramIdx++;
  }

  // Team filter (case-insensitive substring on player_name for team_kill type)
  const teamFilter = url.searchParams.get('team');
  if (teamFilter) {
    conditions.push(`global_type = 'team_kill'`);
    conditions.push(`player_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(teamFilter)}%`);
    paramIdx++;
  }

  // Target filter (case-insensitive substring)
  const targetFilter = url.searchParams.get('target');
  if (targetFilter) {
    conditions.push(`target_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(targetFilter)}%`);
    paramIdx++;
  }

  // Mob ID filter
  const mobIdFilter = url.searchParams.get('mob_id');
  if (mobIdFilter) {
    const mobId = parseInt(mobIdFilter);
    if (!isNaN(mobId)) {
      conditions.push(`mob_id = $${paramIdx}`);
      params.push(mobId);
      paramIdx++;
    }
  }

  // Location filter (exact match — selected from autocomplete)
  const locationFilter = url.searchParams.get('location');
  if (locationFilter) {
    conditions.push(`location = $${paramIdx}`);
    params.push(locationFilter);
    paramIdx++;
  }

  // Min value filter
  const minValue = url.searchParams.get('min_value');
  if (minValue) {
    const val = parseFloat(minValue);
    if (!isNaN(val)) {
      conditions.push(`value >= $${paramIdx}`);
      params.push(val);
      paramIdx++;
    }
  }

  // HoF only
  if (url.searchParams.get('hof') === 'true') {
    conditions.push('is_hof = true');
  }

  // ATH only
  if (url.searchParams.get('ath') === 'true') {
    conditions.push('is_ath = true');
  }

  // Space mining filter (deposit sub-category)
  const spaceFilter = url.searchParams.get('space');
  if (spaceFilter === 'only') {
    conditions.push(`target_name ~* 'asteroid'`);
  } else if (spaceFilter === 'exclude') {
    conditions.push(`(target_name IS NULL OR target_name !~* 'asteroid')`);
  }

  // Since timestamp (for polling — exclusive, returns events after this time)
  const since = url.searchParams.get('since');
  if (since) {
    const sinceDate = new Date(since);
    if (!isNaN(sinceDate.getTime())) {
      conditions.push(`event_timestamp > $${paramIdx}`);
      params.push(sinceDate.toISOString());
      paramIdx++;
    }
  }

  // Before timestamp (for cursor-based pagination)
  const before = url.searchParams.get('before');
  if (before) {
    const beforeDate = new Date(before);
    if (!isNaN(beforeDate.getTime())) {
      conditions.push(`event_timestamp < $${paramIdx}`);
      params.push(beforeDate.toISOString());
      paramIdx++;
    }
  }

  // Limit
  const limit = Math.min(
    Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT),
    MAX_LIMIT
  );
  params.push(limit);
  const limitIdx = paramIdx;
  paramIdx++;

  const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const userId = locals.session?.user ? String(locals.session.user.Id || locals.session.user.id) : null;

  // If authenticated, include per-row user_gz flag via LEFT JOIN
  let userGzSelect = '';
  let userGzJoin = '';
  if (userId) {
    params.push(userId);
    const userIdIdx = paramIdx;
    paramIdx++;
    userGzSelect = `, (ugz.user_id IS NOT NULL) AS user_gz`;
    userGzJoin = `LEFT JOIN globals_gz ugz ON ugz.global_id = ingested_globals.id AND ugz.user_id = $${userIdIdx}`;
  }

  try {
    const { rows } = await pool.query(
      `SELECT id, global_type, player_name, target_name, value, value_unit,
              location, is_hof, is_ath, event_timestamp,
              mob_id, maturity_id, extra,
              media_image_key, media_video_url,
              (SELECT COUNT(*)::int FROM globals_gz WHERE global_id = ingested_globals.id) AS gz_count
              ${userGzSelect}
       FROM ingested_globals
       ${userGzJoin}
       ${whereClause}
       ORDER BY event_timestamp DESC
       LIMIT $${limitIdx}`,
      params
    );

    const globals = rows.map(r => ({
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
      gz_count: r.gz_count || 0,
      ...(userId != null && { user_gz: r.user_gz || false }),
    }));

    const cursor = rows.length > 0
      ? rows[rows.length - 1].event_timestamp
      : null;

    const response = new Response(JSON.stringify({
      globals,
      cursor,
      has_more: rows.length === limit,
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': userId ? 'private, max-age=5' : 'public, max-age=5',
      },
    });
    return response;
  } catch (e) {
    console.error('[api/globals] Error fetching globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
