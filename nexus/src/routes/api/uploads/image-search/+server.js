/**
 * API endpoint for searching entities with approved images.
 * Used by the "Use Existing" image linking feature.
 *
 * GET /api/uploads/image-search?query=...&entityType=...&excludeId=...
 *
 * Enriches approved images with entity names from the internal API
 * when metadata.json doesn't have the name (older uploads).
 */
import { error } from '@sveltejs/kit';
import { getCachedApprovedImages, isValidEntityType } from '$lib/server/imageProcessor.js';

const API_BASE = process.env.INTERNAL_API_URL || 'http://api:3000';

// Maps image entityType to internal API endpoint
const TYPE_ENDPOINT_MAP = {
  'weapon': '/weapons',
  'mob': '/mobs',
  'armorset': '/armorsets',
  'material': '/materials',
  'blueprint': '/blueprints',
  'skill': '/skills',
  'profession': '/professions',
  'vendor': '/vendors',
  'clothing': '/clothings',
  'consumable': '/stimulants',
  'capsule': '/capsules',
  'medicaltool': '/medicaltools',
  'medicalchip': '/medicalchips',
  'vehicle': '/vehicles',
  'pet': '/pets',
  'strongbox': '/strongboxes',
  'shop': '/shops',
  'location': '/locations',
  'refiner': '/refiners',
  'scanner': '/scanners',
  'finder': '/finders',
  'excavator': '/excavators',
  'teleportationchip': '/teleportationchips',
  'effectchip': '/effectchips',
  'misctool': '/misctools',
  'tool': '/tools',
  'weaponamplifier': '/weaponamplifiers',
  'weaponvisionattachment': '/weaponvisionattachments',
  'absorber': '/absorbers',
  'armorplating': '/armorplatings',
  'finderamplifier': '/finderamplifiers',
  'enhancer': '/enhancers',
  'mindforceimplant': '/mindforceimplants',
  'furniture': '/furniture',
  'decoration': '/decorations',
  'storagecontainer': '/storagecontainers',
  'sign': '/signs'
};

// Persistent name cache — survives across requests, refreshed alongside approved images cache
const _nameCache = new Map();
let _nameCacheTime = 0;
const NAME_CACHE_TTL = 120_000; // 2 minutes

/**
 * Look up entity name from internal API.
 * @param {string} entityType
 * @param {string} entityId
 * @returns {Promise<string|null>}
 */
async function fetchEntityName(entityType, entityId) {
  const endpoint = TYPE_ENDPOINT_MAP[entityType];
  if (!endpoint) return null;

  try {
    const response = await fetch(`${API_BASE}${endpoint}/${entityId}`);
    if (!response.ok) return null;
    const data = await response.json();
    return data?.Name || data?.Properties?.Name || null;
  } catch {
    return null;
  }
}

/**
 * Get approved images enriched with entity names.
 * Names come from metadata.json first, then from internal API (cached).
 */
async function getEnrichedApprovedImages() {
  const approved = await getCachedApprovedImages();
  const now = Date.now();

  // Refresh name cache if stale
  if (now - _nameCacheTime > NAME_CACHE_TTL) {
    const missing = approved.filter(img =>
      !img.entityName && !_nameCache.has(`${img.entityType}/${img.entityId}`)
    );

    // Batch lookups (10 concurrent max)
    const BATCH_SIZE = 10;
    for (let i = 0; i < missing.length; i += BATCH_SIZE) {
      const batch = missing.slice(i, i + BATCH_SIZE);
      await Promise.all(batch.map(async (img) => {
        const name = await fetchEntityName(img.entityType, img.entityId);
        if (name) {
          _nameCache.set(`${img.entityType}/${img.entityId}`, name);
        }
      }));
    }
    _nameCacheTime = now;
  }

  return approved.map(img => ({
    ...img,
    entityName: img.entityName || _nameCache.get(`${img.entityType}/${img.entityId}`) || null
  }));
}

/**
 * Score a name against a search query (substring/prefix scoring).
 * @param {string} name
 * @param {string} query
 * @returns {number} 0 = no match, higher = better
 */
function scoreMatch(name, query) {
  if (!name) return 0;
  const nameLower = name.toLowerCase();
  const queryLower = query.toLowerCase();

  if (nameLower === queryLower) return 1000;
  if (nameLower.startsWith(queryLower)) return 900 - nameLower.length;

  const words = nameLower.split(/\s+/);
  for (let i = 0; i < words.length; i++) {
    if (words[i].startsWith(queryLower)) return 800 - i * 5 - nameLower.length;
  }

  const idx = nameLower.indexOf(queryLower);
  if (idx !== -1) return 700 - Math.min(idx, 50) - nameLower.length;

  return 0;
}

const MAX_RESULTS = 20;

/** @type {import('./$types').RequestHandler} */
export async function GET({ url, locals }) {
  const user = /** @type {any} */ (locals.session?.user);
  if (!user) throw error(401, 'Authentication required');
  if (!user.verified) throw error(403, 'Account verification required');

  const query = url.searchParams.get('query')?.trim();
  const entityType = url.searchParams.get('entityType')?.toLowerCase();
  const excludeId = url.searchParams.get('excludeId');

  if (!query || query.length < 2) {
    return new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } });
  }

  if (!entityType || !isValidEntityType(entityType)) {
    throw error(400, 'Valid entityType parameter required');
  }

  const enriched = await getEnrichedApprovedImages();

  const results = enriched
    .filter(img =>
      img.entityType === entityType &&
      (!excludeId || String(img.entityId) !== String(excludeId))
    )
    .map(img => ({ ...img, _score: scoreMatch(img.entityName, query) }))
    .filter(img => img._score > 0)
    .sort((a, b) => b._score - a._score)
    .slice(0, MAX_RESULTS)
    .map(img => ({
      entityType: img.entityType,
      entityId: img.entityId,
      entityName: img.entityName || img.entityId,
      thumbUrl: `/api/img/${img.entityType}/${img.entityId}?type=thumb`
    }));

  return new Response(JSON.stringify(results), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'private, no-cache'
    }
  });
}
