-- Drop the "Misc" fish family. It was only seeded to house a single
-- catalog outlier (Baitfish), which isn't a real fish species — it's a
-- bait/junk catch item. The seed script (nexus-bot/scripts/seed-fish-catalog.mjs)
-- no longer emits a Fish row for Baitfish, so the Misc species is
-- unreferenced and can be removed. The "Misc Fish Oil" Materials row
-- (never referenced by the refining pipeline) goes with it.
--
-- Idempotent: the DELETEs are guarded and no-op on a fresh DB where
-- Misc was never seeded.

BEGIN;

DELETE FROM ONLY "Materials"
 WHERE "Name" = 'Misc Fish Oil'
   AND "Id" NOT IN (
     -- Defensive: keep it if anything (refining recipes, ingredients)
     -- already references the material via Items.Id.
     SELECT "ItemId" - 1000000 FROM ONLY "RefiningIngredients" WHERE "ItemId" IS NOT NULL
     UNION
     SELECT "ProductId" - 1000000 FROM ONLY "RefiningRecipes"  WHERE "ProductId" IS NOT NULL
   );

DELETE FROM ONLY "MobSpecies"
 WHERE "Name" = 'Misc'
   AND "CodexType" = 'Fish'::"CodexType"
   AND "Id" NOT IN (SELECT "SpeciesId" FROM ONLY "Fish" WHERE "SpeciesId" IS NOT NULL);

COMMIT;
