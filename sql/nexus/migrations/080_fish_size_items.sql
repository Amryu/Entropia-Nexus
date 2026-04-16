-- Move item identity from Fish to FishSizes. In the game each fish size
-- is its own item, so every FishSize row gets a dedicated Materials backing
-- row (hardcoded Weight 0.01 kg, Value 0.01 PED). Fish.ItemId is dropped.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Add ItemId to FishSizes
-- ---------------------------------------------------------------------------

ALTER TABLE "FishSizes" ADD COLUMN "ItemId" integer;

CREATE UNIQUE INDEX "FishSizes_ItemId_idx" ON "FishSizes" ("ItemId") WHERE "ItemId" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Create a Materials row for each existing FishSize
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  rec RECORD;
  new_mat_id integer;
BEGIN
  FOR rec IN
    SELECT fs."Id" AS fish_size_id, fs."Name" AS size_name
    FROM "FishSizes" fs
    WHERE fs."ItemId" IS NULL
  LOOP
    INSERT INTO "Materials" ("Name", "Weight", "Value")
    VALUES (rec.size_name, 0.01, 0.01)
    RETURNING "Id" INTO new_mat_id;

    UPDATE "FishSizes" SET "ItemId" = new_mat_id + 1000000
    WHERE "Id" = rec.fish_size_id;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Rebuild Items VIEW first (breaks dependency on Fish.ItemId)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "Items" AS
 SELECT ("Materials"."Id" + 1000000) AS "Id",
        "Materials"."Name",
        "Materials"."Value",
        "Materials"."Weight",
        CASE WHEN fs."Id" IS NOT NULL THEN 'Fish'::text ELSE 'Material'::text END AS "Type"
   FROM ONLY "Materials"
   LEFT JOIN ONLY "FishSizes" fs ON fs."ItemId" = ("Materials"."Id" + 1000000)
UNION ALL
 SELECT ("Weapons"."Id" + 2000000) AS "Id", "Weapons"."Name", "Weapons"."MaxTT" AS "Value", "Weapons"."Weight", 'Weapon'::text AS "Type"
   FROM ONLY "Weapons"
UNION ALL
 SELECT ("Armors"."Id" + 3000000) AS "Id", "Armors"."Name", "Armors"."MaxTT" AS "Value", "Armors"."Weight", 'Armor'::text AS "Type"
   FROM ONLY "Armors"
UNION ALL
 SELECT ("Tools"."Id" + 4000000) AS "Id", "Tools"."Name", "Tools"."MaxTT" AS "Value", "Tools"."Weight", "Tools"."Type"
   FROM "Tools"
UNION ALL
 SELECT ("Attachments"."Id" + 5000000) AS "Id", "Attachments"."Name", "Attachments"."MaxTT" AS "Value", "Attachments"."Weight", "Attachments"."Type"
   FROM "Attachments"
UNION ALL
 SELECT ("Blueprints"."Id" + 6000000) AS "Id", "Blueprints"."Name", 1 AS "Value", 0.1 AS "Weight", 'Blueprint'::text AS "Type"
   FROM ONLY "Blueprints"
UNION ALL
 SELECT ("Vehicles"."Id" + 7000000) AS "Id", "Vehicles"."Name", "Vehicles"."MaxTT" AS "Value", "Vehicles"."Weight", 'Vehicle'::text AS "Type"
   FROM ONLY "Vehicles"
UNION ALL
 SELECT ("Clothes"."Id" + 8000000) AS "Id", "Clothes"."Name", "Clothes"."MaxTT" AS "Value", "Clothes"."Weight", 'Clothing'::text AS "Type"
   FROM ONLY "Clothes"
UNION ALL
 SELECT ("Furnishings"."Id" + 9000000) AS "Id", "Furnishings"."Name", "Furnishings"."MaxTT" AS "Value", "Furnishings"."Weight", "Furnishings"."Type"
   FROM "Furnishings"
UNION ALL
 SELECT ("Consumables"."Id" + 10000000) AS "Id",
        "Consumables"."Name",
        "Consumables"."Value",
        "Consumables"."Weight",
        CASE WHEN "Consumables"."Type" = 'Food' THEN 'Food'::text ELSE 'Consumable'::text END AS "Type"
   FROM ONLY "Consumables"
UNION ALL
 SELECT ("CreatureControlCapsules"."Id" + 10100000) AS "Id", "CreatureControlCapsules"."Name", "CreatureControlCapsules"."MaxTT" AS "Value", "CreatureControlCapsules"."Weight", 'Capsule'::text AS "Type"
   FROM ONLY "CreatureControlCapsules"
UNION ALL
 SELECT ("Pets"."Id" + 11000000) AS "Id", "Pets"."Name", 0 AS "Value", 0 AS "Weight", 'Pet'::text AS "Type"
   FROM ONLY "Pets"
UNION ALL
 SELECT ("Strongboxes"."Id" + 12000000) AS "Id", "Strongboxes"."Name", 0.00001 AS "Value", 0 AS "Weight", 'Strongbox'::text AS "Type"
   FROM ONLY "Strongboxes";

GRANT SELECT ON "Items" TO "nexus", nexus_bot;

-- ---------------------------------------------------------------------------
-- 4. Now safe to drop Fish.ItemId
-- ---------------------------------------------------------------------------

DROP INDEX IF EXISTS "Fish_ItemId_idx";
ALTER TABLE "Fish" DROP COLUMN "ItemId";

COMMIT;
