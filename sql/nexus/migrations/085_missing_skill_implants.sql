-- Migration 085: Add missing skill implant items for extractable skills
--
-- Some skills added to the Skills table after the initial MiscTools seed
-- (currently Chemistry and Strength, but the query is generic so any future
-- additions get picked up too) lack their "<SkillName> Skill Implant (L)"
-- counterpart. Mission rewards and other features that reference skills by
-- implant Item id fall back to raw "Skill #<id>" without this entry.
--
-- Implants are stored in "MiscTools" with Type='Skill Implant'. The "Items"
-- view unions them through "Tools", so inserting here automatically surfaces
-- them in /api/items. Values follow existing implant conventions
-- (Weight=1, MaxTT=1250, MinTT=0.000001).

BEGIN;

INSERT INTO "MiscTools" ("Name", "Type", "Weight", "MaxTT", "MinTT")
SELECT s."Name" || ' Skill Implant (L)', 'Skill Implant', 1, 1250, 0.000001
FROM ONLY "Skills" s
WHERE s."IsExtractable" = true
  AND NOT EXISTS (
    SELECT 1 FROM ONLY "MiscTools" mt
    WHERE mt."Type" = 'Skill Implant'
      AND mt."Name" = s."Name" || ' Skill Implant (L)'
  );

COMMIT;
