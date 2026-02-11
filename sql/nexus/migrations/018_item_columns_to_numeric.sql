-- Migration: Convert Weight, Uses, Decay, MaxTT, MinTT to numeric type
-- Tables affected: Refiners, Scanners, Absorbers (and their audit tables via inheritance)
-- Views affected: Items, Tools, Attachments (must be dropped and recreated)

BEGIN;

------------------------------------------------------
-- 1. Drop dependent views (Items depends on Tools and Attachments)
------------------------------------------------------

DROP VIEW IF EXISTS "Items";
DROP VIEW IF EXISTS "Tools";
DROP VIEW IF EXISTS "Attachments";

------------------------------------------------------
-- 2. Alter column types
------------------------------------------------------

-- Refiners: Weight (int→numeric), Uses (text→numeric), Decay (real→numeric), MaxTT (real→numeric), MinTT (real→numeric)
ALTER TABLE "Refiners"
  ALTER COLUMN "Weight" TYPE numeric,
  ALTER COLUMN "Uses" TYPE numeric USING "Uses"::numeric,
  ALTER COLUMN "Decay" TYPE numeric,
  ALTER COLUMN "MaxTT" TYPE numeric,
  ALTER COLUMN "MinTT" TYPE numeric;

-- Scanners: Weight (int→numeric), Uses (int→numeric), Decay (text→numeric), MaxTT (int→numeric), MinTT (text→numeric)
ALTER TABLE "Scanners"
  ALTER COLUMN "Weight" TYPE numeric,
  ALTER COLUMN "Uses" TYPE numeric,
  ALTER COLUMN "Decay" TYPE numeric USING "Decay"::numeric,
  ALTER COLUMN "MaxTT" TYPE numeric,
  ALTER COLUMN "MinTT" TYPE numeric USING "MinTT"::numeric;

-- Absorbers: MaxTT (int→numeric), MinTT (int→numeric)
ALTER TABLE "Absorbers"
  ALTER COLUMN "MaxTT" TYPE numeric,
  ALTER COLUMN "MinTT" TYPE numeric;

------------------------------------------------------
-- 3. Recreate views
------------------------------------------------------

-- View: public.Tools

-- DROP VIEW public."Tools";

CREATE OR REPLACE VIEW public."Tools"
 AS
 SELECT "MedicalTools"."Id" + 100000 AS "Id",
    "MedicalTools"."Name",
    "MedicalTools"."MaxTT",
    "MedicalTools"."Weight",
    'MedicalTool'::text AS "Type"
   FROM ONLY "MedicalTools"
UNION ALL
 SELECT "MiscTools"."Id" + 200000 AS "Id",
    "MiscTools"."Name",
    "MiscTools"."MaxTT",
    "MiscTools"."Weight",
    'MiscTool'::text AS "Type"
   FROM ONLY "MiscTools"
UNION ALL
 SELECT "Refiners"."Id" + 300000 AS "Id",
    "Refiners"."Name",
    "Refiners"."MaxTT",
    "Refiners"."Weight",
    'Refiner'::text AS "Type"
   FROM ONLY "Refiners"
UNION ALL
 SELECT "Scanners"."Id" + 400000 AS "Id",
    "Scanners"."Name",
    "Scanners"."MaxTT",
    "Scanners"."Weight",
    'Scanner'::text AS "Type"
   FROM ONLY "Scanners"
UNION ALL
 SELECT "Finders"."Id" + 500000 AS "Id",
    "Finders"."Name",
    "Finders"."MaxTT",
    "Finders"."Weight",
    'Finder'::text AS "Type"
   FROM ONLY "Finders"
UNION ALL
 SELECT "Excavators"."Id" + 600000 AS "Id",
    "Excavators"."Name",
    "Excavators"."MaxTT",
    "Excavators"."Weight",
    'Excavator'::text AS "Type"
   FROM ONLY "Excavators"
UNION ALL
 SELECT "BlueprintBooks"."Id" + 700000 AS "Id",
    "BlueprintBooks"."Name",
    "BlueprintBooks"."Value" AS "MaxTT",
    "BlueprintBooks"."Weight",
    'BlueprintBook'::text AS "Type"
   FROM ONLY "BlueprintBooks"
UNION ALL
 SELECT "MedicalChips"."Id" + 800000 AS "Id",
    "MedicalChips"."Name",
    "MedicalChips"."MaxTT",
    "MedicalChips"."Weight",
    'MedicalChip'::text AS "Type"
   FROM ONLY "MedicalChips"
UNION ALL
 SELECT "TeleportationChips"."Id" + 810000 AS "Id",
    "TeleportationChips"."Name",
    "TeleportationChips"."MaxTT",
    "TeleportationChips"."Weight",
    'TeleportationChip'::text AS "Type"
   FROM ONLY "TeleportationChips"
UNION ALL
 SELECT "EffectChips"."Id" + 820000 AS "Id",
    "EffectChips"."Name",
    "EffectChips"."MaxTT",
    "EffectChips"."Weight",
    'EffectChip'::text AS "Type"
   FROM ONLY "EffectChips";

ALTER TABLE public."Tools"
    OWNER TO postgres;

GRANT SELECT ON TABLE public."Tools" TO nexus;
GRANT SELECT ON TABLE public."Tools" TO "nexus-bot";
GRANT ALL ON TABLE public."Tools" TO postgres;

-- =========================================================

CREATE OR REPLACE VIEW public."Attachments"
 AS
 SELECT "WeaponAmplifiers"."Id" + 100000 AS "Id",
    "WeaponAmplifiers"."Name",
    "WeaponAmplifiers"."MaxTT",
    "WeaponAmplifiers"."Weight",
    'WeaponAmplifier'::text AS "Type"
   FROM ONLY "WeaponAmplifiers"
UNION ALL
 SELECT "WeaponVisionAttachments"."Id" + 200000 AS "Id",
    "WeaponVisionAttachments"."Name",
    "WeaponVisionAttachments"."MaxTT",
    "WeaponVisionAttachments"."Weight",
    'WeaponVisionAttachment'::text AS "Type"
   FROM ONLY "WeaponVisionAttachments"
UNION ALL
 SELECT "Absorbers"."Id" + 300000 AS "Id",
    "Absorbers"."Name",
    "Absorbers"."MaxTT",
    "Absorbers"."Weight",
    'Absorber'::text AS "Type"
   FROM ONLY "Absorbers"
UNION ALL
 SELECT "FinderAmplifiers"."Id" + 400000 AS "Id",
    "FinderAmplifiers"."Name",
    "FinderAmplifiers"."MaxTT",
    "FinderAmplifiers"."Weight",
    'FinderAmplifier'::text AS "Type"
   FROM ONLY "FinderAmplifiers"
UNION ALL
 SELECT "ArmorPlatings"."Id" + 500000 AS "Id",
    "ArmorPlatings"."Name",
    "ArmorPlatings"."MaxTT",
    "ArmorPlatings"."Weight",
    'ArmorPlating'::text AS "Type"
   FROM ONLY "ArmorPlatings"
UNION ALL
 SELECT "Enhancers"."Id" + 600000 AS "Id",
    "Enhancers"."Name",
    "Enhancers"."Value" AS "MaxTT",
    "Enhancers"."Weight",
    'Enhancer'::text AS "Type"
   FROM ONLY "Enhancers"
UNION ALL
 SELECT "MindforceImplants"."Id" + 700000 AS "Id",
    "MindforceImplants"."Name",
    "MindforceImplants"."MaxTT",
    "MindforceImplants"."Weight",
    'MindforceImplant'::text AS "Type"
   FROM ONLY "MindforceImplants";

ALTER TABLE public."Attachments"
    OWNER TO postgres;

GRANT SELECT ON TABLE public."Attachments" TO nexus;
GRANT SELECT ON TABLE public."Attachments" TO "nexus-bot";
GRANT ALL ON TABLE public."Attachments" TO postgres;

-- =========================================================

CREATE OR REPLACE VIEW public."Items"
 AS
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
   FROM ONLY "Pets";

ALTER TABLE public."Items"
    OWNER TO postgres;

GRANT SELECT ON TABLE public."Items" TO nexus;
GRANT SELECT ON TABLE public."Items" TO "nexus-bot";
GRANT ALL ON TABLE public."Items" TO postgres;

COMMIT;
