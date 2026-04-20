// Sync first-time discovery globals from nexus_users.ingested_globals into
// nexus."FishDiscoveries". Until a fish has its own confirmed discovery
// global, it and its materials are hidden from all public listings. The
// sync is additive — once a fish is marked discovered, we keep it that
// way even if the global row is later removed.
//
// Matching is on Fish.Name only. Earlier logic also matched the family oil
// (`{Species.Name} Fish Oil`) and marked every fish in that family as
// discovered on first oil loot, which leaked undiscovered sizes through
// the public listings.

import { poolUsers } from './db.js';
import pg from 'pg';

const poolNexus = new pg.Pool({
  connectionString: process.env.POSTGRES_NEXUS_CONNECTION_STRING,
});

async function loadFishNameMap() {
  const { rows } = await poolNexus.query(`SELECT "Id", "Name" FROM ONLY "Fish"`);

  const nameToFishIds = new Map();
  for (const r of rows) {
    if (!r.Name || r.Id == null) continue;
    const key = String(r.Name).trim().toLowerCase();
    if (!key) continue;
    let s = nameToFishIds.get(key);
    if (!s) { s = new Set(); nameToFishIds.set(key, s); }
    s.add(r.Id);
  }
  return nameToFishIds;
}

async function loadDiscoveryGlobals() {
  // target_name is the plain item/creature name after migration 118.
  // Unconfirmed globals are excluded — we do not want a single unverified
  // report to reveal an undiscovered fish.
  const { rows } = await poolUsers.query(`
    SELECT target_name, player_name, event_timestamp
      FROM ingested_globals
     WHERE global_type = 'discovery'
       AND confirmed = TRUE
       AND target_name IS NOT NULL
  `);
  return rows;
}

export async function syncFishDiscoveries() {
  const [nameToFishIds, globals] = await Promise.all([
    loadFishNameMap(),
    loadDiscoveryGlobals(),
  ]);

  // For each fish id, keep the earliest event_timestamp + that row's player_name.
  const firstByFishId = new Map();
  for (const g of globals) {
    const key = String(g.target_name).trim().toLowerCase();
    const fishIds = nameToFishIds.get(key);
    if (!fishIds) continue;
    const ts = g.event_timestamp ? new Date(g.event_timestamp) : null;
    for (const fid of fishIds) {
      const prev = firstByFishId.get(fid);
      if (!prev || (ts && prev.ts && ts < prev.ts) || (ts && !prev.ts)) {
        firstByFishId.set(fid, { ts, player: g.player_name });
      }
    }
  }

  if (firstByFishId.size === 0) return { inserted: 0, updated: 0, total: 0 };

  const ids = Array.from(firstByFishId.keys());
  const timestamps = ids.map(id => firstByFishId.get(id).ts ?? null);
  const players = ids.map(id => firstByFishId.get(id).player ?? null);

  // Bulk upsert. ON CONFLICT keeps the earliest known timestamp so we never
  // silently bump the discovery date forward if we later re-sync and pick
  // up a different global as the winner.
  const result = await poolNexus.query(
    `INSERT INTO "FishDiscoveries" ("FishId", "DiscoveredAt", "DiscovererName")
     SELECT * FROM UNNEST($1::int[], $2::timestamp[], $3::text[])
     ON CONFLICT ("FishId") DO UPDATE SET
       "DiscoveredAt" = LEAST(
         "FishDiscoveries"."DiscoveredAt",
         COALESCE(EXCLUDED."DiscoveredAt", "FishDiscoveries"."DiscoveredAt")
       ),
       "DiscovererName" = CASE
         WHEN EXCLUDED."DiscoveredAt" IS NOT NULL
          AND (
            "FishDiscoveries"."DiscoveredAt" IS NULL
            OR EXCLUDED."DiscoveredAt" < "FishDiscoveries"."DiscoveredAt"
          )
         THEN EXCLUDED."DiscovererName"
         ELSE "FishDiscoveries"."DiscovererName"
       END`,
    [ids, timestamps, players]
  );

  return { total: ids.length, affected: result.rowCount };
}
