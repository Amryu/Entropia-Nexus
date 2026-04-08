// @ts-nocheck
/**
 * GET /api/globals/targets — Autocomplete for target names in globals.
 * Returns both mob base names (all maturities) and specific mob+maturity combos.
 * Results are compatible with SearchInput component format.
 */
import { pool } from '$lib/server/db.js';
import { scoreSearchResult } from '$lib/search.js';

const MAX_RESULTS = 20;
const MAX_RAW_RESULTS = 80;

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

/**
 * Extract the mob base name by stripping the maturity suffix.
 * Handles "Gen XX" multi-word maturities and single-word maturities.
 */
function extractMobName(targetName) {
  const parts = targetName.split(' ');
  if (parts.length < 2) return null;

  // Handle "Gen XX" pattern (e.g., "Big Bulk Gen 10" → "Big Bulk")
  if (parts.length >= 3 && /^Gen$/i.test(parts[parts.length - 2])) {
    return parts.slice(0, -2).join(' ');
  }

  // Handle "Elite Gen XX" pattern (e.g., "Defender Elite Gen 02" → "Defender")
  if (parts.length >= 4 && /^Gen$/i.test(parts[parts.length - 2]) && /^Elite$/i.test(parts[parts.length - 3])) {
    return parts.slice(0, -3).join(' ');
  }

  // Strip last word (single-word maturity like Young, Mature, Stalker, etc.)
  return parts.slice(0, -1).join(' ');
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
      `SELECT target_name AS name, event_count AS cnt
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
      [escaped, query, MAX_RAW_RESULTS]
    );

    // Build mob group results by extracting base names
    const mobGroups = {};
    for (const row of result.rows) {
      const baseName = extractMobName(row.name);
      if (!baseName || baseName.length < 2) continue;
      if (!mobGroups[baseName]) mobGroups[baseName] = { cnt: 0, variants: 0 };
      mobGroups[baseName].cnt += parseInt(row.cnt);
      mobGroups[baseName].variants++;
    }

    const results = [];
    let id = 1;
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

    // Add specific target name results (skip if identical to a mob group)
    for (const row of result.rows) {
      if (addedNames.has(row.name)) continue;
      results.push({
        Id: id++,
        Name: row.name,
        Type: 'Target',
        SubType: null,
        Score: scoreMatch(row.name, query),
      });
    }

    results.sort((a, b) => b.Score - a.Score);
    const limited = results.slice(0, MAX_RESULTS);

    return new Response(JSON.stringify(limited), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/targets] Error:', e);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
