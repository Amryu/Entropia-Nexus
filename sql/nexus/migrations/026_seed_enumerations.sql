-- Migration 026: Seed custom Enumerations data
-- Adds baseline custom enumerations from in-game tables/screenshots.
-- Idempotent: safe to re-run.

BEGIN;

-- ============================================================================
-- Deposit Sizes
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Metadata")
VALUES (
  'Deposit Sizes',
  'Size of found deposits. Approximate values.',
  '{"columns":["Level","From","Expires"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Deposit Sizes'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Minimal', '{"Level":"I","From":0.05,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Tiny', '{"Level":"II","From":0.25,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Very Poor', '{"Level":"III","From":1,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Poor', '{"Level":"IV","From":2,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Small', '{"Level":"V","From":3,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Modest', '{"Level":"VI","From":4.5,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Average', '{"Level":"VII","From":6,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '{"Level":"VIII","From":8,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Ample', '{"Level":"IX","From":12,"Expires":"2h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Considerable', '{"Level":"X","From":18,"Expires":"3h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Sizable', '{"Level":"XI","From":25,"Expires":"6h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Large', '{"Level":"XII","From":35,"Expires":"10h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Abundant', '{"Level":"XIII","From":50,"Expires":"18h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '{"Level":"XIV","From":75,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Substantial', '{"Level":"XV","From":125,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Significant', '{"Level":"XVI","From":200,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Plentiful', '{"Level":"XVII","From":300,"Expires":"36h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Huge', '{"Level":"XVIII","From":450,"Expires":"36h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Extremely Large', '{"Level":"XIX","From":650,"Expires":"48h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Massive', '{"Level":"XX","From":800,"Expires":"72h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Vast', '{"Level":"XXI","From":1200,"Expires":"96h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Enormous', '{"Level":"XXII","From":2500,"Expires":"120h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Rich', '{"Level":"XXIII","From":5000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Gigantic', '{"Level":"XXIV","From":25000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Mammoth', '{"Level":"XXV","From":100000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Colossal', '{"Level":"XXVI","From":250000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Immense', '{"Level":"XXVII","From":500000,"Expires":null}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Durability
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Metadata")
VALUES (
  'Durability',
  'Durability levels used to hint at decay behavior.',
  '{"columns":["From"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Durability'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Exceptional', '{"From":0}'::jsonb),
  ((SELECT "Id" FROM e), 'Excellent', '{"From":0.1}'::jsonb),
  ((SELECT "Id" FROM e), 'Very Good', '{"From":0.5}'::jsonb),
  ((SELECT "Id" FROM e), 'Good', '{"From":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Above Average', '{"From":2.5}'::jsonb),
  ((SELECT "Id" FROM e), 'Average', '{"From":5}'::jsonb),
  ((SELECT "Id" FROM e), 'Below Average', '{"From":10}'::jsonb),
  ((SELECT "Id" FROM e), 'Mediocre', '{"From":25}'::jsonb),
  ((SELECT "Id" FROM e), 'Inferior', '{"From":45}'::jsonb),
  ((SELECT "Id" FROM e), 'Fragile', '{"From":100}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Damage Potential
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Metadata")
VALUES (
  'Damage Potential',
  'Damage potential ranges.',
  '{"columns":["From"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Damage Potential'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Minimal', '{"From":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Small', '{"From":20}'::jsonb),
  ((SELECT "Id" FROM e), 'Limited', '{"From":30}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '{"From":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Large', '{"From":60}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '{"From":101}'::jsonb),
  ((SELECT "Id" FROM e), 'Huge', '{"From":161}'::jsonb),
  ((SELECT "Id" FROM e), 'Immense', '{"From":271}'::jsonb),
  ((SELECT "Id" FROM e), 'Gigantic', '{"From":356}'::jsonb),
  ((SELECT "Id" FROM e), 'Colossal', '{"From":500}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Health Ranks
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Metadata")
VALUES (
  'Health Ranks',
  'Avatar health level ranks.',
  '{"columns":["Level"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Health Ranks'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Puny', '{"Level":0}'::jsonb),
  ((SELECT "Id" FROM e), 'Frail', '{"Level":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Weak', '{"Level":90}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '{"Level":150}'::jsonb),
  ((SELECT "Id" FROM e), 'Tough', '{"Level":250}'::jsonb),
  ((SELECT "Id" FROM e), 'Strong', '{"Level":500}'::jsonb),
  ((SELECT "Id" FROM e), 'Massive', '{"Level":1000}'::jsonb),
  ((SELECT "Id" FROM e), 'Extremely high', '{"Level":2500}'::jsonb),
  ((SELECT "Id" FROM e), 'Enormous', '{"Level":5000}'::jsonb),
  ((SELECT "Id" FROM e), 'Mammoth', '{"Level":10000}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Skill Ranks (Skill column only)
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Metadata")
VALUES (
  'Skill Ranks',
  'Skill rank names mapped to skill levels (profession column omitted).',
  '{"columns":["Skill"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Skill Ranks'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Newbie', '{"Skill":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Inept', '{"Skill":10}'::jsonb),
  ((SELECT "Id" FROM e), 'Poor', '{"Skill":20}'::jsonb),
  ((SELECT "Id" FROM e), 'Weak', '{"Skill":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Mediocre', '{"Skill":67}'::jsonb),
  ((SELECT "Id" FROM e), 'Unskilled', '{"Skill":110}'::jsonb),
  ((SELECT "Id" FROM e), 'Green', '{"Skill":160}'::jsonb),
  ((SELECT "Id" FROM e), 'Beginner', '{"Skill":260}'::jsonb),
  ((SELECT "Id" FROM e), 'Novice', '{"Skill":360}'::jsonb),
  ((SELECT "Id" FROM e), 'Amateur', '{"Skill":460}'::jsonb),
  ((SELECT "Id" FROM e), 'Apprentice', '{"Skill":600}'::jsonb),
  ((SELECT "Id" FROM e), 'Initiated', '{"Skill":800}'::jsonb),
  ((SELECT "Id" FROM e), 'Qualified', '{"Skill":1000}'::jsonb),
  ((SELECT "Id" FROM e), 'Trained', '{"Skill":1200}'::jsonb),
  ((SELECT "Id" FROM e), 'Able', '{"Skill":1400}'::jsonb),
  ((SELECT "Id" FROM e), 'Competent', '{"Skill":1600}'::jsonb),
  ((SELECT "Id" FROM e), 'Adept', '{"Skill":1800}'::jsonb),
  ((SELECT "Id" FROM e), 'Capable', '{"Skill":2000}'::jsonb),
  ((SELECT "Id" FROM e), 'Skilled', '{"Skill":2200}'::jsonb),
  ((SELECT "Id" FROM e), 'Experienced', '{"Skill":2400}'::jsonb),
  ((SELECT "Id" FROM e), 'Proficient', '{"Skill":2600}'::jsonb),
  ((SELECT "Id" FROM e), 'Good', '{"Skill":2800}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '{"Skill":3000}'::jsonb),
  ((SELECT "Id" FROM e), 'Inspiring', '{"Skill":3200}'::jsonb),
  ((SELECT "Id" FROM e), 'Impressive', '{"Skill":3400}'::jsonb),
  ((SELECT "Id" FROM e), 'Veteran', '{"Skill":3600}'::jsonb),
  ((SELECT "Id" FROM e), 'Professional', '{"Skill":3800}'::jsonb),
  ((SELECT "Id" FROM e), 'Specialist', '{"Skill":4000}'::jsonb),
  ((SELECT "Id" FROM e), 'Advanced', '{"Skill":4200}'::jsonb),
  ((SELECT "Id" FROM e), 'Remarkable', '{"Skill":4500}'::jsonb),
  ((SELECT "Id" FROM e), 'Expert', '{"Skill":4800}'::jsonb),
  ((SELECT "Id" FROM e), 'Exceptional', '{"Skill":5100}'::jsonb),
  ((SELECT "Id" FROM e), 'Amazing', '{"Skill":5400}'::jsonb),
  ((SELECT "Id" FROM e), 'Incredible', '{"Skill":5700}'::jsonb),
  ((SELECT "Id" FROM e), 'Marvelous', '{"Skill":6000}'::jsonb),
  ((SELECT "Id" FROM e), 'Astonishing', '{"Skill":6300}'::jsonb),
  ((SELECT "Id" FROM e), 'Outstanding', '{"Skill":6600}'::jsonb),
  ((SELECT "Id" FROM e), 'Champion', '{"Skill":6900}'::jsonb),
  ((SELECT "Id" FROM e), 'Elite', '{"Skill":7200}'::jsonb),
  ((SELECT "Id" FROM e), 'Superior', '{"Skill":7500}'::jsonb),
  ((SELECT "Id" FROM e), 'Supreme', '{"Skill":7800}'::jsonb),
  ((SELECT "Id" FROM e), 'Master', '{"Skill":8100}'::jsonb),
  ((SELECT "Id" FROM e), 'Grand Master', '{"Skill":8400}'::jsonb),
  ((SELECT "Id" FROM e), 'Arch Master', '{"Skill":8700}'::jsonb),
  ((SELECT "Id" FROM e), 'Supreme Master', '{"Skill":9100}'::jsonb),
  ((SELECT "Id" FROM e), 'Ultimate Master', '{"Skill":9500}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Master', '{"Skill":10000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Grand Master', '{"Skill":12000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Arch Master', '{"Skill":14000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Supreme Master', '{"Skill":16000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Ultimate Master', '{"Skill":18000}'::jsonb),
  ((SELECT "Id" FROM e), 'Entropia Master', '{"Skill":20000}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Data" = EXCLUDED."Data";

COMMIT;
