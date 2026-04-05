// @ts-nocheck
/**
 * GET /api/globals/locations — Autocomplete for location names in globals.
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
    // Fuzzy match: substring ILIKE OR trigram/word similarity (same as menu-bar search).
    // % catches short-name typos; <% catches query words appearing within longer names.
    // Uses idx_ingested_globals_location_trgm (migration 126).
    const result = await pool.query(
      `SELECT location AS name, count(*) AS cnt
       FROM ingested_globals
       WHERE confirmed = true AND location IS NOT NULL
         AND (location ILIKE $1 OR location % $2 OR $2 <% location)
       GROUP BY location
       ORDER BY
         CASE WHEN location ILIKE $1 THEN 0 ELSE 1 END,
         GREATEST(similarity(location, $2), word_similarity($2, location)) DESC,
         count(*) DESC
       LIMIT $3`,
      [escaped, query, MAX_RESULTS]
    );

    const results = result.rows.map((row, i) => ({
      Id: i + 1,
      Name: row.name,
      Type: 'Location',
      SubType: null,
      Score: scoreMatch(row.name, query),
    }));

    results.sort((a, b) => b.Score - a.Score);

    return new Response(JSON.stringify(results), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/locations] Error:', e);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
