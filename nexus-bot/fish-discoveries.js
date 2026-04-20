// Sync first-time discovery globals from nexus_users.ingested_globals into
// nexus."FishDiscoveries". Until a fish (or its linked fish-oil material)
// has a confirmed discovery global, the fish and its materials are hidden
// from all public listings. The sync is additive — once a fish is marked
// discovered, we keep it that way even if the global row is later removed.
//
// Since migration 090 each Fish row already represents a specific in-game
// size (the old FishSizes table is gone), so matching by Fish.Name and by
// the oil item name is sufficient.

import { poolUsers } from './db.js';
import pg from 'pg';

const poolNexus = new pg.Pool({
  connectionString: process.env.POSTGRES_NEXUS_CONNECTION_STRING,
});

async function loadFishNameMap() {
  const [fishRes, oilRes] = await Promise.all([
    poolNexus.query(`SELECT "Id", "Name" FROM ONLY "Fish"`),
    // Fish oil is resolved by naming convention: `{Species.Name} Fish Oil`.
    // A discovery global whose target_name matches the family oil marks
    // every fish in the family as discovered, so one oil name can map to
    // many FishIds here.
    poolNexus.query(`
      SELECT f."Id" AS "FishId", (ms."Name" || ' Fish Oil') AS "Name"
        FROM ONLY "Fish" f
        JOIN ONLY "MobSpecies" ms ON ms."Id" = f."SpeciesId"
       WHERE ms."CodexType" = 'Fish'::"CodexType"
    `),
  ]);

  // name (lowercased) -> Set of FishIds. An oil name can map to many fish
  // (all Cod fish share "Cod Fish Oil"); Fish.Name is unique per in-game
  // size since migration 090 split them out. Kept as a Set for safety.
  const nameToFishIds = new Map();
  function add(name, fishId) {
    if (!name || fishId == null) return;
    const key = String(name).trim().toLowerCase();
    if (!key) return;
    let s = nameToFishIds.get(key);
    if (!s) { s = new Set(); nameToFishIds.set(key, s); }
    s.add(fishId);
  }
  for (const r of fishRes.rows) add(r.Name, r.Id);
  for (const r of oilRes.rows) add(r.Name, r.FishId);
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
