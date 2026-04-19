-- Migration 086: Fish material dedup + fish oil refining recipes
--
-- applyFishSizesChanges in nexus-bot/changes/entity.js used to INSERT a
-- new Materials row whenever a FishSize was renamed instead of reusing
-- the existing row, leaving orphan Materials with duplicate names. This
-- migration:
--   1. Sets FishOilItemId on three Fish rows that were missing it so every
--      species with size rows has a product item (Catfish Oil for the two
--      catfish, Tuna Fish Oil for Thunderfin Tuna).
--   2. Deletes the 60 orphan duplicate Materials rows (lower-Id copies;
--      the highest-Id row per name is the canonical one referenced by
--      FishSizes.ItemId). No nexus-side FKs point to the orphans --
--      verified across BlueprintMaterials, Blueprints, Effects*,
--      EquipSetItems, ItemProperties, ItemTags, MobLoots,
--      RefiningIngredients, StrongboxLoots, Tiers, Vendor*, AreaMineables,
--      LandAreaMinerals, TierMaterials, Vehicles.FuelMaterialId,
--      Fish.FishOilItemId, MissionRewards, MissionObjectives. User-side
--      refs in nexus_users (user_items, inventory_import_deltas) are
--      repointed in sql/nexus_users/migrations/132_fish_material_repoint.sql.
--   3. Creates a refining recipe per FishSize that has a ScrapsToRefine
--      value: 10 x fish + ScrapsToRefine x Fish Scrap (item 1003285) ->
--      (10 + ScrapsToRefine / 100) x species Fish Oil. Output count keeps
--      TT in balance (fish material 0.01 PED * 10 + Fish Scrap 0.0001 PED
--      * scraps = Fish Oil 0.01 PED * out). Pyrotip Swordfish and
--      Thunderfin Tuna have NULL ScrapsToRefine and are skipped.

BEGIN;

-- 1. Backfill FishOilItemId for fish whose species oil already exists.
UPDATE ONLY "Fish" SET "FishOilItemId" = 1003301 WHERE "Id" IN (18, 31);  -- Catfish Oil
UPDATE ONLY "Fish" SET "FishOilItemId" = 1003311 WHERE "Id" = 34;         -- Tuna Fish Oil

-- 2. Drop the 60 orphan duplicate fish Materials rows.
DELETE FROM ONLY "Materials" WHERE "Id" IN (
  3286, 3288, 3295, 3296, 3299, 3302, 3304, 3306, 3307, 3314,
  3315, 3316, 3317, 3320, 3322, 3323, 3324, 3326, 3405, 3406,
  3407, 3408, 3409, 3410, 3411, 3412, 3413, 3414, 3415, 3416,
  3417, 3418, 3419, 3420, 3421, 3422, 3423, 3424, 3425, 3426,
  3427, 3428, 3429, 3430, 3431, 3432, 3433, 3434, 3435, 3436,
  3437, 3438, 3439, 3440, 3441, 3443, 3444, 3445, 3446, 3450
);

-- 2b. Tag current fish-size Materials (linked from FishSizes.ItemId) with
--     Type='Fish'. The Items VIEW already exposes Type='Fish' via its
--     LEFT JOIN on Fish, but setting Materials.Type keeps raw queries
--     and exchange categorisation aligned.
UPDATE ONLY "Materials"
   SET "Type" = 'Fish'
 WHERE "Id" IN (SELECT "ItemId" - 1000000 FROM ONLY "FishSizes");

-- 3. Refining recipes: one per FishSize where both ScrapsToRefine and the
--    species' FishOilItemId are set. Idempotent: skips any fish size that
--    already has a recipe whose product is the species oil.
DO $$
DECLARE
  r RECORD;
  new_recipe_id integer;
  fish_scrap_item_id constant integer := 1003285;
BEGIN
  FOR r IN
    SELECT fs."ItemId"         AS size_item_id,
           fs."ScrapsToRefine" AS scraps,
           f."FishOilItemId"   AS oil_id,
           10 + fs."ScrapsToRefine" / 100 AS out_amt
      FROM ONLY "FishSizes" fs
      JOIN ONLY "Fish"      f ON f."Id" = fs."FishId"
     WHERE fs."ScrapsToRefine" IS NOT NULL
       AND f."FishOilItemId"   IS NOT NULL
  LOOP
    IF EXISTS (
      SELECT 1
        FROM ONLY "RefiningRecipes"    rr
        JOIN ONLY "RefiningIngredients" ri ON ri."RecipeId" = rr."Id"
       WHERE rr."ProductId" = r.oil_id
         AND ri."ItemId"    = r.size_item_id
    ) THEN
      CONTINUE;
    END IF;

    INSERT INTO "RefiningRecipes" ("ProductId", "Amount")
    VALUES (r.oil_id, r.out_amt)
    RETURNING "Id" INTO new_recipe_id;

    INSERT INTO "RefiningIngredients" ("RecipeId", "ItemId", "Amount") VALUES
      (new_recipe_id, r.size_item_id,      10),
      (new_recipe_id, fish_scrap_item_id,  r.scraps);
  END LOOP;
END $$;

COMMIT;
