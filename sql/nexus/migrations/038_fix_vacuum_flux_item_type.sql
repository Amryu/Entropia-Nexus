BEGIN;

-- Move Vacuum Flux Energy Generator from MiscTools to Materials
-- Old: MiscTools Id=121 (global 4200121), Type="Hangar Part", Weight=8.5, MaxTT=25
-- New: Materials Id=3204 (global 1003204), Type="Hangar Part", Stackable=1

ALTER TABLE "Materials" DISABLE TRIGGER ALL;
ALTER TABLE "MiscTools" DISABLE TRIGGER ALL;

INSERT INTO "Materials" ("Id", "Name", "Type", "Weight", "Stackable", "MaxStack", "Value")
VALUES (3204, 'Vacuum Flux Energy Generator', 'Hangar Part', 8.5, 1, 0, 25);

DELETE FROM ONLY "MiscTools" WHERE "Id" = 121;

-- Rename "Old Hangar Part" to "Hangar Part" (Rad Conveyor, Id=1828)
UPDATE ONLY "Materials" SET "Type" = 'Hangar Part' WHERE "Type" = 'Old Hangar Part';

ALTER TABLE "Materials" ENABLE TRIGGER ALL;
ALTER TABLE "MiscTools" ENABLE TRIGGER ALL;

COMMIT;
