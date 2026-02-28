// @ts-nocheck
/**
 * GET /api/globals/search — Search for players, teams, and targets in globals.
 * Public endpoint, no auth required.
 *
 * Returns results compatible with the SearchInput component format:
 *   { Id, Name, Type, SubType, Score }
 *
 * Type values: "Player", "Team", "Hunting", "Mining", "Crafting",
 *              "Rare Find", "Discovery", "Tier"
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

const MAX_RESULTS_PER_CATEGORY = 10;

const GLOBAL_TYPE_LABELS = {
  kill: 'Hunting',
  team_kill: 'Hunting',
  deposit: 'Mining',
  craft: 'Crafting',
  rare_item: 'Rare Find',
  discovery: 'Discovery',
  tier: 'Tier',
};

function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

/**
 * Simple server-side scoring that mirrors the client-side algorithm.
 * Exact > prefix > word-start > contains.
 */
function scoreMatch(name, query) {
  const nameLower = name.toLowerCase();
  const queryLower = query.toLowerCase();

  if (nameLower === queryLower) return 1000;
  if (nameLower.startsWith(queryLower)) return 900 - nameLower.length;

  const words = nameLower.split(/\s+/);
  for (let i = 0; i < words.length; i++) {
    if (words[i].startsWith(queryLower)) {
      return 800 - i * 5 - nameLower.length;
    }
  }

  const index = nameLower.indexOf(queryLower);
  if (index !== -1) return 700 - Math.min(index, 50) - nameLower.length;

  return 500;
}

export async function GET({ url }) {
  const query = url.searchParams.get('query')?.trim();
  if (!query || query.length < 2) {
    return getResponse([], 200);
  }

  if (query.length > 200) {
    return getResponse({ error: 'Query too long' }, 400);
  }

  const escaped = `%${escapeLike(query)}%`;

  try {
    const [playersResult, targetsResult] = await Promise.all([
      // Players & Teams — grouped by player_name
      pool.query(
        `SELECT player_name AS name,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo,
                count(*) AS cnt
         FROM ingested_globals
         WHERE confirmed = true AND player_name ILIKE $1
         GROUP BY player_name
         ORDER BY count(*) DESC
         LIMIT $2`,
        [escaped, MAX_RESULTS_PER_CATEGORY]
      ),

      // Targets — grouped by target_name with most common type
      pool.query(
        `SELECT target_name AS name,
                mode() WITHIN GROUP (ORDER BY global_type) AS primary_type,
                count(*) AS cnt
         FROM ingested_globals
         WHERE confirmed = true AND target_name ILIKE $1
         GROUP BY target_name
         ORDER BY count(*) DESC
         LIMIT $2`,
        [escaped, MAX_RESULTS_PER_CATEGORY]
      ),
    ]);

    const results = [];
    let id = 1;

    // Players
    for (const row of playersResult.rows) {
      const isTeamOnly = row.has_team && !row.has_solo;
      results.push({
        Id: id++,
        Name: row.name,
        Type: isTeamOnly ? 'Team' : 'Player',
        SubType: null,
        Score: scoreMatch(row.name, query),
      });
    }

    // Targets
    for (const row of targetsResult.rows) {
      results.push({
        Id: id++,
        Name: row.name,
        Type: GLOBAL_TYPE_LABELS[row.primary_type] || row.primary_type,
        SubType: null,
        Score: scoreMatch(row.name, query),
      });
    }

    // Sort by score descending
    results.sort((a, b) => b.Score - a.Score);

    return new Response(JSON.stringify(results), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=30',
      },
    });
  } catch (e) {
    console.error('[api/globals/search] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
