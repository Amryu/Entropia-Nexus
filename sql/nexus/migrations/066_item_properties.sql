-- ItemProperties: cross-entity item flags (IsUntradeable, IsRare).
-- ItemId is the global item ID (entity Id + offset from constants.js).
-- Only rows where at least one flag is TRUE need to exist.

CREATE TABLE IF NOT EXISTS "ItemProperties" (
  "ItemId"        INTEGER PRIMARY KEY,
  "IsUntradeable" BOOLEAN NOT NULL DEFAULT FALSE,
  "IsRare"        BOOLEAN NOT NULL DEFAULT FALSE
);

GRANT SELECT, INSERT, UPDATE, DELETE ON "ItemProperties" TO nexus;
GRANT SELECT ON "ItemProperties" TO nexus_bot;

-- Seed IsUntradeable from existing item descriptions.
-- Each source table uses its own offset to compute the global ItemId.

INSERT INTO "ItemProperties" ("ItemId", "IsUntradeable")
SELECT "Id" + 1000000,  TRUE FROM ONLY "Materials"               WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 2000000,  TRUE FROM ONLY "Weapons"                 WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 3000000,  TRUE FROM ONLY "Armors"                  WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4100000,  TRUE FROM ONLY "MedicalTools"            WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4200000,  TRUE FROM ONLY "MiscTools"               WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4300000,  TRUE FROM ONLY "Refiners"                WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4400000,  TRUE FROM ONLY "Scanners"                WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4500000,  TRUE FROM ONLY "Finders"                 WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4600000,  TRUE FROM ONLY "Excavators"              WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4800000,  TRUE FROM ONLY "MedicalChips"            WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4810000,  TRUE FROM ONLY "TeleportationChips"      WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 4820000,  TRUE FROM ONLY "EffectChips"             WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5100000,  TRUE FROM ONLY "WeaponAmplifiers"        WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5200000,  TRUE FROM ONLY "WeaponVisionAttachments" WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5300000,  TRUE FROM ONLY "Absorbers"               WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5400000,  TRUE FROM ONLY "FinderAmplifiers"        WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5500000,  TRUE FROM ONLY "ArmorPlatings"           WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 5700000,  TRUE FROM ONLY "MindforceImplants"       WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 6000000,  TRUE FROM ONLY "Blueprints"              WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 7000000,  TRUE FROM ONLY "Vehicles"                WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 8000000,  TRUE FROM ONLY "Clothes"                 WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 10000000, TRUE FROM ONLY "Consumables"             WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 10100000, TRUE FROM ONLY "CreatureControlCapsules" WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 11000000, TRUE FROM ONLY "Pets"                    WHERE "Description" ILIKE '%Untradeable%'
UNION ALL
SELECT "Id" + 12000000, TRUE FROM ONLY "Strongboxes"             WHERE "Description" ILIKE '%Untradeable%'
ON CONFLICT ("ItemId") DO UPDATE SET "IsUntradeable" = TRUE;
