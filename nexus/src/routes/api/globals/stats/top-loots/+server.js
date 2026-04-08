// @ts-nocheck
/**
 * GET /api/globals/stats/top-loots — Top globals by value per category (paginated).
 * Public endpoint, no auth required.
 *
 * Returns { items: [...], page, pages, total }
 * Each entry: { player, target, value, hof, ath, timestamp, mob_id }
 *
 * Query params:
 *   category — hunting|mining|crafting|rare_item|discovery|tier|pvp (default: hunting)
 *   page     — 1-based page number (default: 1)
 *   limit    — items per page (default: 20, max: 50)
 *   Plus all standard globals filters.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter } from '../filter-utils.js';
import { TOP_LOOTS_TABS } from '$lib/data/globals-constants.js';

const MAX_LIMIT = 50;
const DEFAULT_LIMIT = 20;
const MAX_PAGE = 500;

function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

export async function GET({ url, locals }) {
  const category = url.searchParams.get('category') || 'hunting';
  const tabConfig = TOP_LOOTS_TABS.find(t => t.value === category);
  if (!tabConfig) {
    return getResponse({ error: 'Invalid category' }, 400);
  }

  const { conditions, params, paramIdx: nextIdx } = buildGlobalsFilter(url);
  let paramIdx = nextIdx;

  // Fuzzy search on target/item name (used by discovery tab search)
  const search = url.searchParams.get('search')?.trim();
  if (search && search.length >= 2) {
    conditions.push(
      `(target_name ILIKE $${paramIdx} OR similarity(target_name, $${paramIdx + 1}) > 0.15 OR word_similarity($${paramIdx + 1}, target_name) > 0.2)`
    );
    params.push(`%${escapeLike(search)}%`, search);
    paramIdx += 2;
  }

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const limitParam = parseInt(url.searchParams.get('limit') || '');
  const limit = Math.min(Math.max(limitParam || DEFAULT_LIMIT, 1), MAX_LIMIT);
  const pageParam = parseInt(url.searchParams.get('page') || '1');
  const page = Math.min(Math.max(pageParam || 1, 1), MAX_PAGE);
  const offset = (page - 1) * limit;

  // Sort — allow client override, default by value for value-based, recency for others
  const SORT_COLUMNS = {
    value: 'value',
    player: 'player_name',
    target: 'target_name',
    time: 'event_timestamp',
  };
  const sortParam = url.searchParams.get('sort') || '';
  const sortAsc = url.searchParams.get('sort_dir') === 'asc';
  const sortCol = SORT_COLUMNS[sortParam];
  const dir = sortAsc ? 'ASC' : 'DESC';
  const defaultOrder = tabConfig.hasValue ? 'value DESC, event_timestamp DESC' : 'event_timestamp DESC';
  const orderBy = sortCol ? `${sortCol} ${dir}, event_timestamp DESC` : defaultOrder;

  const userId = locals.session?.user ? String(locals.session.user.Id || locals.session.user.id) : null;

  // If authenticated, include per-row user_gz flag via LEFT JOIN
  let userGzSelect = '';
  let userGzJoin = '';
  const dataParams = [...params];
  if (userId) {
    dataParams.push(userId);
    const userIdIdx = dataParams.length;
    userGzSelect = `, (ugz.user_id IS NOT NULL) AS user_gz`;
    userGzJoin = `LEFT JOIN globals_gz ugz ON ugz.global_id = ingested_globals.id AND ugz.user_id = $${userIdIdx}`;
  }

  const limitIdx = dataParams.length + 1;
  const offsetIdx = dataParams.length + 2;

  try {
    const [countResult, dataResult] = await Promise.all([
      pool.query(
        `SELECT count(*) AS total
         FROM ingested_globals
         ${whereClause} AND global_type IN ${tabConfig.types}`,
        params
      ),
      pool.query(
        `SELECT id, player_name AS player, target_name AS target, value, value_unit, mob_id,
                is_hof AS hof, is_ath AS ath, event_timestamp AS timestamp,
                media_image_key, media_video_url,
                (SELECT COUNT(*)::int FROM globals_gz WHERE global_id = ingested_globals.id) AS gz_count
                ${userGzSelect}
         FROM ingested_globals
         ${userGzJoin}
         ${whereClause} AND global_type IN ${tabConfig.types}
         ORDER BY ${orderBy}
         LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
        [...dataParams, limit, offset]
      ),
    ]);

    const total = parseInt(countResult.rows[0].total);
    const pages = Math.max(1, Math.ceil(total / limit));

    const items = dataResult.rows.map(r => ({
      id: r.id,
      player: r.player,
      target: r.target,
      value: parseFloat(r.value),
      unit: r.value_unit,
      mob_id: r.mob_id,
      hof: r.hof,
      ath: r.ath,
      timestamp: r.timestamp,
      media_image: r.media_image_key || null,
      media_video: r.media_video_url || null,
      gz_count: r.gz_count || 0,
      ...(userId != null && { user_gz: r.user_gz || false }),
    }));

    return new Response(JSON.stringify({ items, page, pages, total }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': userId ? 'private, max-age=60' : 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/stats/top-loots] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
