// @ts-nocheck
/**
 * GET /api/globals/search — Search for players, teams, and targets in globals.
 * Public endpoint, no auth required.
 *
 * Returns results compatible with the SearchInput component format:
 *   { Id, Name, Type, SubType, Score }
 *
 * Type values: "Player", "Team", "Hunting", "Mining", "Crafting", "Fishing",
 *              "Rare Find", "Discovery", "Tier"
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { scoreSearchResult } from '$lib/search.js';

const MAX_RESULTS_PER_CATEGORY = 10;
const MAX_RAW_TARGETS = 80;

const GLOBAL_TYPE_LABELS = {
  kill: 'Hunting',
  team_kill: 'Hunting',
  deposit: 'Mining',
  craft: 'Crafting',
  fish: 'Fishing',
  rare_item: 'Rare Find',
  discovery: 'Discovery',
  tier: 'Tier',
  examine: 'Instance',
  pvp: 'PvP',
};

/**
 * Extract the mob base name by stripping the maturity suffix.
 * Handles "Gen XX" multi-word maturities and single-word maturities.
 */
function extractMobName(targetName) {
  const parts = targetName.split(' ');
  if (parts.length < 2) return null;

  // Handle "Elite Gen XX" pattern (e.g., "Defender Elite Gen 02" → "Defender")
  if (parts.length >= 4 && /^Gen$/i.test(parts[parts.length - 2]) && /^Elite$/i.test(parts[parts.length - 3])) {
    return parts.slice(0, -3).join(' ');
  }

  // Handle "Gen XX" pattern (e.g., "Big Bulk Gen 10" → "Big Bulk")
  if (parts.length >= 3 && /^Gen$/i.test(parts[parts.length - 2])) {
    return parts.slice(0, -2).join(' ');
  }

  // Strip last word (single-word maturity like Young, Mature, Stalker, etc.)
  return parts.slice(0, -1).join(' ');
}

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
    // Fuzzy match: substring ILIKE + trigram/word similarity with low thresholds
    // to allow typos and partial matches. Aggregation tables are small enough
    // that explicit function comparisons are fast without index support.
    const [playersResult, targetsResult] = await Promise.all([
      // Players & Teams — from pre-aggregated table
      pool.query(
        `SELECT player_name AS name, has_team, has_solo, event_count AS cnt
         FROM globals_player_agg
         WHERE period = 'all'
           AND (player_name ILIKE $1
                OR similarity(player_name, $2) > 0.15
                OR word_similarity($2, player_name) > 0.2)
         ORDER BY
           CASE WHEN player_name ILIKE $1 THEN 0 ELSE 1 END,
           GREATEST(similarity(player_name, $2), word_similarity($2, player_name)) DESC,
           event_count DESC
         LIMIT $3`,
        [escaped, query, MAX_RESULTS_PER_CATEGORY]
      ),

      // Targets — from pre-aggregated table
      pool.query(
        `SELECT target_name AS name, primary_type, event_count AS cnt
         FROM globals_target_agg
         WHERE period = 'all'
           AND (target_name ILIKE $1
                OR similarity(target_name, $2) > 0.15
                OR word_similarity($2, target_name) > 0.2)
         ORDER BY
           CASE WHEN target_name ILIKE $1 THEN 0 ELSE 1 END,
           GREATEST(similarity(target_name, $2), word_similarity($2, target_name)) DESC,
           event_count DESC
         LIMIT $3`,
        [escaped, query, MAX_RAW_TARGETS]
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

    // Build mob group results by extracting base names from hunting targets
    const mobGroups = {};
    for (const row of targetsResult.rows) {
      if (row.primary_type === 'kill' || row.primary_type === 'team_kill') {
        const baseName = extractMobName(row.name);
        if (!baseName || baseName.length < 2) continue;
        if (!mobGroups[baseName]) mobGroups[baseName] = { cnt: 0, variants: 0 };
        mobGroups[baseName].cnt += parseInt(row.cnt);
        mobGroups[baseName].variants++;
      }
    }

    const addedNames = new Set();

    // Add mob group results (only if >1 maturity variant and base name fuzzy-matches query)
    for (const [name, group] of Object.entries(mobGroups)) {
      if (group.variants > 1 && scoreSearchResult(name, query) > 0) {
        results.push({
          Id: id++,
          Name: name,
          Type: 'Mob',
          SubType: null,
          Score: scoreMatch(name, query) + 50,
        });
        addedNames.add(name);
      }
    }

    // Targets (skip if identical to a mob group)
    for (const row of targetsResult.rows) {
      if (addedNames.has(row.name)) continue;
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
