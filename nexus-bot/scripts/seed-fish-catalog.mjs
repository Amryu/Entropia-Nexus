// One-shot seeder for the 101 fish from `fish-catalog.mjs`. Idempotent:
// safe to re-run. Upserts everything by Name, then runs the discovery
// sync so already-discovered fish flip visible before the next bot cycle.
//
// Usage:
//   node nexus-bot/scripts/seed-fish-catalog.mjs
//
// Needs POSTGRES_NEXUS_CONNECTION_STRING and, for the discovery sync
// step, POSTGRES_USERS_CONNECTION_STRING.

import dotenv from 'dotenv';
import pg from 'pg';
import { CATALOG, FAMILIES, tierToDifficulty } from './fish-catalog.mjs';
import { syncFishDiscoveries } from '../fish-discoveries.js';

dotenv.config();

const poolNexus = new pg.Pool({
  connectionString: process.env.POSTGRES_NEXUS_CONNECTION_STRING,
});

const MATERIAL_OFFSET = 1000000;

async function ensureFamilySpecies(client) {
  for (const family of FAMILIES) {
    await client.query(
      `INSERT INTO "MobSpecies" ("Name", "CodexBaseCost", "CodexType")
       VALUES ($1, 6, 'Fish'::"CodexType")
       ON CONFLICT ("Name") DO UPDATE SET
         "CodexType" = 'Fish'::"CodexType",
         "CodexBaseCost" = COALESCE("MobSpecies"."CodexBaseCost", 6)`,
      [family]
    );
  }
}

// The API resolves fish oil via the name convention `{Family} Fish Oil`
// (no FK column). This ensures the expected Materials rows exist so the
// lookup always resolves.
async function ensureFamilyOils(client) {
  for (const family of FAMILIES) {
    const oilName = `${family} Fish Oil`;
    await client.query(
      `INSERT INTO "Materials" ("Name", "Weight", "Value", "Type")
       SELECT $1, 0.01, 0.01, 'Fish Oil'
        WHERE NOT EXISTS (SELECT 1 FROM ONLY "Materials" WHERE "Name" = $1)`,
      [oilName]
    );
  }
}

async function upsertFishMaterial(client, name) {
  const existing = await client.query(
    `SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`,
    [name]
  );
  if (existing.rows[0]) return existing.rows[0].Id + MATERIAL_OFFSET;
  const inserted = await client.query(
    `INSERT INTO "Materials" ("Name", "Weight", "Value", "Type")
     VALUES ($1, 0.01, 0.01, 'Fish')
     RETURNING "Id"`,
    [name]
  );
  return inserted.rows[0].Id + MATERIAL_OFFSET;
}

async function upsertFish(client, entry, speciesIdByName) {
  const speciesId = speciesIdByName.get(entry.family);
  if (speciesId == null) {
    throw new Error(`Unknown family "${entry.family}" for fish "${entry.name}"`);
  }
  const itemId = await upsertFishMaterial(client, entry.name);
  const difficulty = tierToDifficulty(entry.tier);

  // Look up existing Fish by Name; upsert by (Name). Fish.Name is not
  // unique-constrained in the schema, so we SELECT first and pick the
  // lowest Id (oldest row) as canonical — matches how the flatten
  // migration left things.
  const existing = await client.query(
    `SELECT "Id" FROM ONLY "Fish" WHERE "Name" = $1 ORDER BY "Id" LIMIT 1`,
    [entry.name]
  );

  let fishId;
  if (existing.rows[0]) {
    fishId = existing.rows[0].Id;
    await client.query(
      `UPDATE ONLY "Fish"
          SET "SpeciesId"      = $2,
              "Difficulty"     = $3::"FishTier",
              "MinDepth"       = $4,
              "Strength"       = $5,
              "ScrapsToRefine" = COALESCE("ScrapsToRefine", NULL),
              "Weight"         = $6,
              "TimeOfDayStart" = $7,
              "TimeOfDayEnd"   = $8,
              "ItemId"         = $9
        WHERE "Id" = $1`,
      [
        fishId, speciesId, difficulty, entry.minDepth, entry.strength,
        entry.weight, entry.timeStart, entry.timeEnd, itemId
      ]
    );
  } else {
    const inserted = await client.query(
      `INSERT INTO "Fish"
        ("Name", "SpeciesId", "Difficulty", "MinDepth", "Strength",
         "Weight", "TimeOfDayStart", "TimeOfDayEnd", "ItemId")
       VALUES ($1, $2, $3::"FishTier", $4, $5, $6, $7, $8, $9)
       RETURNING "Id"`,
      [
        entry.name, speciesId, difficulty, entry.minDepth, entry.strength,
        entry.weight, entry.timeStart, entry.timeEnd, itemId
      ]
    );
    fishId = inserted.rows[0].Id;
  }

  // Junctions — wholesale replace for idempotency.
  await client.query(`DELETE FROM "FishRodTypes" WHERE "FishId" = $1`, [fishId]);
  for (const rod of entry.rods) {
    await client.query(
      `INSERT INTO "FishRodTypes" ("FishId", "RodType")
       VALUES ($1, $2::"FishingRodType")
       ON CONFLICT DO NOTHING`,
      [fishId, rod]
    );
  }

  await client.query(`DELETE FROM "FishBiomes" WHERE "FishId" = $1`, [fishId]);
  for (const water of entry.waters) {
    await client.query(
      `INSERT INTO "FishBiomes" ("FishId", "Biome")
       VALUES ($1, $2::"FishBiome")
       ON CONFLICT DO NOTHING`,
      [fishId, water]
    );
  }

  await client.query(`DELETE FROM "FishPlanets" WHERE "FishId" = $1`, [fishId]);
  for (const planet of entry.planets) {
    const pr = await client.query(
      `SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [planet]
    );
    const planetId = pr.rows[0]?.Id;
    if (planetId == null) {
      console.warn(`[seed] planet "${planet}" not found for "${entry.name}" — skipping`);
      continue;
    }
    await client.query(
      `INSERT INTO "FishPlanets" ("FishId", "PlanetId") VALUES ($1, $2)
       ON CONFLICT DO NOTHING`,
      [fishId, planetId]
    );
  }

  return fishId;
}

async function cleanupLegacySpecies(client) {
  // Delete any MobSpecies row with CodexType='Fish' that is neither one of
  // the 11 canonical families nor referenced by a Fish row. Post-seed,
  // every Fish.SpeciesId points at a family, so the old per-fish species
  // rows (e.g. "Calypsocod", "Catfish") are orphans.
  const res = await client.query(
    `DELETE FROM ONLY "MobSpecies"
      WHERE "CodexType" = 'Fish'::"CodexType"
        AND "Name" <> ALL($1::text[])
        AND "Id" NOT IN (SELECT "SpeciesId" FROM ONLY "Fish" WHERE "SpeciesId" IS NOT NULL)
      RETURNING "Id", "Name"`,
    [FAMILIES]
  );
  return res.rows;
}

async function main() {
  const client = await poolNexus.connect();
  let seeded = 0;
  let skipped = 0;
  try {
    await client.query('BEGIN');

    await ensureFamilySpecies(client);
    await ensureFamilyOils(client);

    const speciesRes = await client.query(
      `SELECT "Id", "Name" FROM ONLY "MobSpecies"
        WHERE "CodexType" = 'Fish'::"CodexType" AND "Name" = ANY($1::text[])`,
      [FAMILIES]
    );
    const speciesIdByName = new Map(speciesRes.rows.map(r => [r.Name, r.Id]));

    for (const entry of CATALOG) {
      try {
        await upsertFish(client, entry, speciesIdByName);
        seeded++;
      } catch (e) {
        console.error(`[seed] ${entry.name}: ${e.message}`);
        skipped++;
      }
    }

    const removed = await cleanupLegacySpecies(client);

    await client.query('COMMIT');

    console.log(`[seed] ${seeded} fish upserted, ${skipped} skipped, ${removed.length} legacy species removed:`, removed.map(r => r.Name));
  } catch (e) {
    await client.query('ROLLBACK');
    console.error('[seed] transaction rolled back:', e);
    process.exitCode = 1;
  } finally {
    client.release();
  }

  // After the catalog is in place, ask the discovery sync to run so any
  // existing globals whose target_name matches a seeded Fish.Name flip
  // the fish visible immediately rather than on the next bot cycle.
  try {
    const result = await syncFishDiscoveries();
    console.log(`[seed] FishDiscoveries synced:`, result);
  } catch (e) {
    console.error('[seed] discovery sync failed (fish will become visible on next bot cycle):', e.message);
  }

  await poolNexus.end();
}

main();
