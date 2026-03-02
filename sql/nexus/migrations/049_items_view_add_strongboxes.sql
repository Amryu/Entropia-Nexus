-- Migration: Add Strongboxes to Items view, remove duplicate Material entries
-- Strongboxes were incorrectly stored as Materials. This remaps MobLoots references
-- to the correct Strongbox IDs, deletes the duplicate Materials, and recreates the
-- Items view with a Strongboxes branch (fixed value 0.00001).

BEGIN;

-- Step 1: Remap MobLoots references from Material IDs to Strongbox IDs
UPDATE ONLY "MobLoots" SET "ItemId" = 12000005 WHERE "ItemId" = 1002724;  -- Christmas Strongbox
UPDATE ONLY "MobLoots" SET "ItemId" = 12000002 WHERE "ItemId" = 1002764;  -- Easter Strongbox
UPDATE ONLY "MobLoots" SET "ItemId" = 12000004 WHERE "ItemId" = 1002787;  -- Halloween Strongbox
UPDATE ONLY "MobLoots" SET "ItemId" = 12000003 WHERE "ItemId" = 1002876;  -- Summer Strongbox

-- Step 2: Delete duplicate strongbox entries from Materials
-- (Strongbox Key Id=2875 is NOT a strongbox, it stays)
DELETE FROM ONLY "Materials" WHERE "Id" IN (2713, 2724, 2764, 2787, 2821, 2874, 2876);

-- Step 3: Recreate Items view with Strongboxes
DROP VIEW IF EXISTS public."Items";

CREATE VIEW public."Items" AS
 SELECT "Materials"."Id" + 1000000 AS "Id",
    "Materials"."Name",
    "Materials"."Value",
    "Materials"."Weight",
    'Material'::text AS "Type"
   FROM ONLY "Materials"
UNION ALL
 SELECT "Weapons"."Id" + 2000000 AS "Id",
    "Weapons"."Name",
    "Weapons"."MaxTT" AS "Value",
    "Weapons"."Weight",
    'Weapon'::text AS "Type"
   FROM ONLY "Weapons"
UNION ALL
 SELECT "Armors"."Id" + 3000000 AS "Id",
    "Armors"."Name",
    "Armors"."MaxTT" AS "Value",
    "Armors"."Weight",
    'Armor'::text AS "Type"
   FROM ONLY "Armors"
UNION ALL
 SELECT "Tools"."Id" + 4000000 AS "Id",
    "Tools"."Name",
    "Tools"."MaxTT" AS "Value",
    "Tools"."Weight",
    "Tools"."Type"
   FROM ONLY "Tools"
UNION ALL
 SELECT "Attachments"."Id" + 5000000 AS "Id",
    "Attachments"."Name",
    "Attachments"."MaxTT" AS "Value",
    "Attachments"."Weight",
    "Attachments"."Type"
   FROM ONLY "Attachments"
UNION ALL
 SELECT "Blueprints"."Id" + 6000000 AS "Id",
    "Blueprints"."Name",
    1 AS "Value",
    0.1 AS "Weight",
    'Blueprint'::text AS "Type"
   FROM ONLY "Blueprints"
UNION ALL
 SELECT "Vehicles"."Id" + 7000000 AS "Id",
    "Vehicles"."Name",
    "Vehicles"."MaxTT" AS "Value",
    "Vehicles"."Weight",
    'Vehicle'::text AS "Type"
   FROM ONLY "Vehicles"
UNION ALL
 SELECT "Clothes"."Id" + 8000000 AS "Id",
    "Clothes"."Name",
    "Clothes"."MaxTT" AS "Value",
    "Clothes"."Weight",
    'Clothing'::text AS "Type"
   FROM ONLY "Clothes"
UNION ALL
 SELECT "Furnishings"."Id" + 9000000 AS "Id",
    "Furnishings"."Name",
    "Furnishings"."MaxTT" AS "Value",
    "Furnishings"."Weight",
    "Furnishings"."Type"
   FROM ONLY "Furnishings"
UNION ALL
 SELECT "Consumables"."Id" + 10000000 AS "Id",
    "Consumables"."Name",
    "Consumables"."Value",
    "Consumables"."Weight",
    'Consumable'::text AS "Type"
   FROM ONLY "Consumables"
UNION ALL
 SELECT "CreatureControlCapsules"."Id" + 10100000 AS "Id",
    "CreatureControlCapsules"."Name",
    "CreatureControlCapsules"."MaxTT" AS "Value",
    "CreatureControlCapsules"."Weight",
    'Capsule'::text AS "Type"
   FROM ONLY "CreatureControlCapsules"
UNION ALL
 SELECT "Pets"."Id" + 11000000 AS "Id",
    "Pets"."Name",
    0 AS "Value",
    0 AS "Weight",
    'Pet'::text AS "Type"
   FROM ONLY "Pets"
UNION ALL
 SELECT "Strongboxes"."Id" + 12000000 AS "Id",
    "Strongboxes"."Name",
    0.00001 AS "Value",
    0 AS "Weight",
    'Strongbox'::text AS "Type"
   FROM ONLY "Strongboxes";

ALTER TABLE public."Items" OWNER TO postgres;
GRANT SELECT ON TABLE public."Items" TO nexus;
GRANT SELECT ON TABLE public."Items" TO nexus_bot;
GRANT ALL ON TABLE public."Items" TO postgres;

COMMIT;
