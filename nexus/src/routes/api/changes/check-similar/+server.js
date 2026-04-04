//@ts-nocheck
import { executeVector } from "$lib/server/db.js";
import { apiCall, getResponse } from "$lib/util.js";

/**
 * Levenshtein distance between two strings (optimized two-row DP).
 */
function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;

  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  let curr = new Array(b.length + 1);

  for (let i = 1; i <= a.length; i++) {
    curr[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1,       // deletion
        curr[j - 1] + 1,   // insertion
        prev[j - 1] + cost  // substitution
      );
    }
    [prev, curr] = [curr, prev];
  }

  return prev[b.length];
}

/**
 * Returns true when the only differences between two names are digits/numbers.
 * e.g. "Armor Mk1" vs "Armor Mk2" → true (skip warning)
 *      "Armor A"   vs "Armor B"   → false (show warning)
 */
function differenceIsOnlyDigits(a, b) {
  return a.replace(/\d+/g, '') === b.replace(/\d+/g, '');
}

/**
 * Maps entity type to API list category.
 * Mirrors the mapping in the changes API endpoint.
 */
function getEntityCategory(entity) {
  switch (entity) {
    case 'Mob': return 'mobs';
    case 'Vendor': return 'vendors';
    case 'Location': case 'Area': case 'Apartment': return 'locations';
    case 'ArmorSet': return 'armorsets';
    case 'Shop': return 'shops';
    case 'Profession': return 'professions';
    case 'Skill': return 'skills';
    case 'Strongbox': return 'strongboxes';
    case 'Mission': return 'missions';
    case 'MissionChain': return 'missionchains';
    default: return 'items';
  }
}

/** In-memory cache: category → { names: string[], ts: number } */
const nameCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function getEntityNames(category) {
  const cached = nameCache.get(category);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.names;
  }

  const entities = await apiCall(fetch, `/${category}`).catch(() => []);
  const names = (Array.isArray(entities) ? entities : [])
    .map(e => e.Name)
    .filter(Boolean);
  nameCache.set(category, { names, ts: Date.now() });
  return names;
}

/**
 * GET /api/changes/check-similar?name=X&entity=Y[&exclude=OriginalName]
 *
 * Returns { similar: string[] } — entity names within Levenshtein distance
 * whose difference is NOT purely numeric.
 */
export async function GET({ url }) {
  const name = url.searchParams.get('name')?.trim();
  const entity = url.searchParams.get('entity');
  const exclude = url.searchParams.get('exclude')?.trim() || null;

  if (!name || !entity) {
    return getResponse({ error: 'name and entity are required.' }, 400);
  }

  // Entities that allow duplicate names — skip check
  if (entity === 'Location' || entity === 'Area' || entity === 'Apartment') {
    return getResponse({ similar: [] });
  }

  if (name.length < 3) {
    return getResponse({ similar: [] });
  }

  const category = getEntityCategory(entity);

  // Fetch existing entity names and pending change names in parallel
  const [apiNames, pendingRows] = await Promise.all([
    getEntityNames(category),
    executeVector(
      `SELECT data->>'Name' AS name, entity FROM changes
       WHERE state IN ('Draft', 'Pending', 'DirectApply', 'ApplyFailed')
         AND data->>'Name' IS NOT NULL`,
      []
    )
  ]);

  // Collect unique names (existing + pending in same category)
  const allNames = new Set(apiNames);
  for (const row of pendingRows) {
    if (row.name && getEntityCategory(row.entity) === category) {
      allNames.add(row.name);
    }
  }

  // Adaptive threshold: 25% of name length, min 2, max 4
  const maxDist = Math.max(2, Math.min(4, Math.ceil(name.length * 0.25)));
  const nameLower = name.toLowerCase();
  const similar = [];

  for (const existing of allNames) {
    if (existing === name || existing === exclude) continue; // skip self / original
    const dist = levenshtein(nameLower, existing.toLowerCase());
    if (dist > 0 && dist <= maxDist && !differenceIsOnlyDigits(name, existing)) {
      similar.push(existing);
    }
  }

  // Sort by name for consistent display
  similar.sort();

  return getResponse({ similar });
}
