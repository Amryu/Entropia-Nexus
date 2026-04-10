// @ts-nocheck
/**
 * GET /api/globals/players — Autocomplete for player names in globals.
 * Returns results compatible with SearchInput component format.
 */
import { pool } from '$lib/server/db.js';

const MAX_RESULTS = 20;

function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

function scoreMatch(name, query) {
  const nameLower = name.toLowerCase();
  const queryLower = query.toLowerCase();
  if (nameLower === queryLower) return 1000;
  if (nameLower.startsWith(queryLower)) return 900 - nameLower.length;
  const index = nameLower.indexOf(queryLower);
  if (index !== -1) return 700 - Math.min(index, 50) - nameLower.length;
  return 500;
}

export async function GET({ url }) {
  const query = url.searchParams.get('query')?.trim();
  if (!query || query.length < 2) {
    return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
  }

  const escaped = `%${escapeLike(query)}%`;

  try {
    // Fuzzy match: substring ILIKE + trigram/word similarity with low thresholds
    // to allow typos and partial matches. The aggregation table is small enough
    // that explicit function comparisons are fast without index support.
    const result = await pool.query(
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
      [escaped, query, MAX_RESULTS]
    );

    const results = result.rows.map((row, i) => {
      const isTeamOnly = row.has_team && !row.has_solo;
      return {
        Id: i + 1,
        Name: row.name,
        Type: isTeamOnly ? 'Team' : 'Player',
        SubType: null,
        Score: scoreMatch(row.name, query),
      };
    });

    // Solo players (and mixed) always sort before team-only entries, then by score.
    results.sort((a, b) => {
      const teamA = a.Type === 'Team' ? 1 : 0;
      const teamB = b.Type === 'Team' ? 1 : 0;
      if (teamA !== teamB) return teamA - teamB;
      return b.Score - a.Score;
    });

    return new Response(JSON.stringify(results), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/players] Error:', e);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
