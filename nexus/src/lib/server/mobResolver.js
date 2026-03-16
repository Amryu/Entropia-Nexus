// @ts-nocheck
/**
 * Mob/maturity name resolver for global events.
 *
 * Loads all Mobs + MobMaturities from the nexus entity database into an
 * in-memory lookup. Used at ingestion time to resolve kill/team_kill
 * target names (e.g. "Atrox Young") into mob_id + maturity_id.
 *
 * Refreshes hourly. Uses its own DB pool (not nexusPool from db.js).
 */

import pg from 'pg';
const { Pool } = pg;

/** @type {pg.Pool | null} */
let entityPool = null;

/**
 * Map<lowercase "mob maturity", { mobId, maturityId, mobName, maturityName }>
 * For Default-only mobs, also keyed as just lowercase mob name.
 * Swapped atomically on refresh (reassigned, not mutated).
 */
let exactLookup = new Map();

/**
 * Map<lowercase mob_name, { id, name, maturities: Map<lowercase_mat, { id, name }>, hasDefault: bool }>
 * Swapped atomically on refresh (reassigned, not mutated).
 */
let mobsByName = new Map();

let initialized = false;
let refreshTimer = null;

const REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

// ---------------------------------------------------------------------------

function getPool() {
  if (!entityPool) {
    const connStr = process.env.POSTGRES_NEXUS_CONNECTION_STRING;
    if (!connStr) return null;
    entityPool = new Pool({ connectionString: connStr, max: 2 });
  }
  return entityPool;
}

/**
 * Load mob + maturity data from the nexus entity database.
 * Safe to call multiple times (idempotent refresh).
 */
export async function loadMobData() {
  const pool = getPool();
  if (!pool) return;

  try {
    // Fetch all mobs
    const { rows: mobs } = await pool.query(
      `SELECT "Id", "Name" FROM ONLY "Mobs" ORDER BY "Id"`
    );
    // Fetch all maturities
    const { rows: mats } = await pool.query(
      `SELECT "Id", "MobId", "Name", "NameMode" FROM ONLY "MobMaturities" ORDER BY "MobId", "Id"`
    );

    // Build lookup structures
    const newMobsByName = new Map();
    const newExactLookup = new Map();
    const mobsById = new Map(); // O(1) lookup by ID for maturity assignment

    for (const mob of mobs) {
      const key = mob.Name.toLowerCase();
      const entry = {
        id: mob.Id,
        name: mob.Name,
        maturities: new Map(),
        hasDefault: false,
      };
      newMobsByName.set(key, entry);
      mobsById.set(mob.Id, entry);
    }

    for (const mat of mats) {
      const mobEntry = mobsById.get(mat.MobId);
      if (!mobEntry) continue;

      const matKey = mat.Name.toLowerCase();
      mobEntry.maturities.set(matKey, { id: mat.Id, name: mat.Name });

      if (matKey === 'default') {
        mobEntry.hasDefault = true;
      }

      // Index the full in-game name based on NameMode
      let fullName;
      switch (mat.NameMode) {
        case 'Prefix':   fullName = `${mat.Name} ${mobEntry.name}`; break;
        case 'Verbatim': fullName = mat.Name; break;
        case 'Empty':    fullName = mobEntry.name; break;
        case 'Suffix':
        default:         fullName = `${mobEntry.name} ${mat.Name}`; break;
      }
      const fullKey = fullName.toLowerCase();
      newExactLookup.set(fullKey, {
        mobId: mobEntry.id,
        maturityId: mat.Id,
        mobName: mobEntry.name,
        maturityName: mat.Name,
      });
    }

    // For Default-only mobs, also index by just the mob name
    for (const [mobKey, mob] of newMobsByName) {
      if (mob.hasDefault && mob.maturities.size === 1) {
        const defaultMat = mob.maturities.get('default');
        if (defaultMat) {
          newExactLookup.set(mobKey, {
            mobId: mob.id,
            maturityId: defaultMat.id,
            mobName: mob.name,
            maturityName: 'Default',
          });
        }
      }
    }

    // Swap references atomically (single assignment = no partial state)
    exactLookup = newExactLookup;
    mobsByName = newMobsByName;

    initialized = true;
  } catch (err) {
    console.error('[mobResolver] Failed to load mob data:', err.message);
  }
}

/**
 * Initialize the resolver: load data and start hourly refresh.
 * Safe to call multiple times.
 */
export async function initMobResolver() {
  if (initialized) return;
  await loadMobData();
  if (!refreshTimer) {
    refreshTimer = setInterval(loadMobData, REFRESH_INTERVAL_MS);
    refreshTimer.unref();
  }
}

/**
 * Resolve a target name (e.g. "Atrox Young") into mob_id + maturity_id.
 *
 * @param {string} targetName - The target name from a kill/team_kill global.
 * @returns {{ mobId: number, maturityId: number, mobName: string, maturityName: string } | null}
 */
export function resolveMob(targetName) {
  if (!initialized || !targetName) return null;

  const key = targetName.toLowerCase().trim();

  // 1. Exact match (covers "Mob Maturity" and Default-only mobs)
  const exact = exactLookup.get(key);
  if (exact) return exact;

  // 2. Suffix splitting: try progressively shorter maturity suffixes
  //    e.g. "Oratan Lancer Bandit" → try mob="Oratan Lancer", mat="Bandit"
  //    then mob="Oratan", mat="Lancer Bandit"
  const words = key.split(/\s+/);
  if (words.length < 2) {
    // Single word, check if it's a known mob with Default maturity
    const mob = mobsByName.get(key);
    if (mob && mob.hasDefault) {
      const defaultMat = mob.maturities.get('default');
      if (defaultMat) {
        return {
          mobId: mob.id,
          maturityId: defaultMat.id,
          mobName: mob.name,
          maturityName: 'Default',
        };
      }
    }
    return null;
  }

  // Try splitting from the right: last N words as maturity, rest as mob name
  for (let splitAt = words.length - 1; splitAt >= 1; splitAt--) {
    const mobPart = words.slice(0, splitAt).join(' ');
    const matPart = words.slice(splitAt).join(' ');

    const mob = mobsByName.get(mobPart);
    if (!mob) continue;

    const mat = mob.maturities.get(matPart);
    if (mat) {
      return {
        mobId: mob.id,
        maturityId: mat.id,
        mobName: mob.name,
        maturityName: mat.name,
      };
    }
  }

  // 3. No maturity match — check if the whole string is a mob with Default maturity
  const mob = mobsByName.get(key);
  if (mob && mob.hasDefault) {
    const defaultMat = mob.maturities.get('default');
    if (defaultMat) {
      return {
        mobId: mob.id,
        maturityId: defaultMat.id,
        mobName: mob.name,
        maturityName: 'Default',
      };
    }
  }

  return null;
}

/**
 * Resolve a base mob name (e.g. "Atrox") into a mob_id, even if the mob
 * has no Default maturity. Used by the target page to find all maturities.
 *
 * @param {string} name - The base mob name.
 * @returns {{ mobId: number, mobName: string } | null}
 */
export function resolveMobByName(name) {
  if (!initialized || !name) return null;
  const mob = mobsByName.get(name.toLowerCase().trim());
  if (mob) return { mobId: mob.id, mobName: mob.name };
  return null;
}

/**
 * Get the count of loaded mobs (for diagnostics).
 */
export function getMobCount() {
  return mobsByName.size;
}
