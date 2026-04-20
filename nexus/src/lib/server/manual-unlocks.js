// @ts-nocheck
/**
 * Registry of "manual unlock" groups for the admin page. Each group
 * describes a set of entities that are hidden from public listings behind
 * some gate (e.g. Fish require a discovery global) and exposes two hooks:
 *
 *   list(pool)           -> array of { id, name, subtitle? } locked entries
 *   unlock(pool, id, actor) -> unlocks a single entry (idempotent)
 *
 * Adding a new group only needs a new entry here. The API route and UI
 * iterate this registry without knowing group specifics.
 */

import { nexusPool } from './db.js';

// Bot-signature used when an admin manual-unlocks an entry. Makes the
// manual path distinguishable from a real bot-synced discovery in audit
// columns (e.g. FishDiscoveries.DiscovererName) without needing a new
// schema column.
const ADMIN_UNLOCK_PLAYER_LABEL = 'Manually unlocked';

export const MANUAL_UNLOCK_GROUPS = {
  fish: {
    key: 'fish',
    label: 'Fishes',
    description: 'Fish hidden from public listings because no confirmed discovery global has been ingested yet.',
    entryLabel: 'fish',
    async list() {
      if (!nexusPool) return [];
      const { rows } = await nexusPool.query(`
        SELECT f."Id" AS id,
               f."Name" AS name,
               ms."Name" AS subtitle
          FROM ONLY "Fish" f
          LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
          LEFT JOIN ONLY "MobSpecies" ms ON ms."Id" = f."SpeciesId"
         WHERE fd."FishId" IS NULL
         ORDER BY ms."Name" NULLS LAST, f."Name"
      `);
      return rows;
    },
    async unlock(id, actorName) {
      if (!nexusPool) throw new Error('nexus DB not configured');
      await nexusPool.query(
        `INSERT INTO "FishDiscoveries" ("FishId", "DiscoveredAt", "DiscovererName")
         VALUES ($1, NOW(), $2)
         ON CONFLICT ("FishId") DO NOTHING`,
        [id, `${ADMIN_UNLOCK_PLAYER_LABEL} by ${actorName || 'admin'}`]
      );
    },
  },
};

export function getGroup(key) {
  return MANUAL_UNLOCK_GROUPS[key] || null;
}

export function listGroups() {
  return Object.values(MANUAL_UNLOCK_GROUPS).map(g => ({
    key: g.key,
    label: g.label,
    description: g.description,
    entryLabel: g.entryLabel,
  }));
}
