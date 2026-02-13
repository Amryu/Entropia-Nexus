-- Migration 026: Seed custom Enumerations data
-- Adds baseline custom enumerations from in-game tables/screenshots.
-- Idempotent: safe to re-run.

BEGIN;

-- ============================================================================
-- Deposit Sizes
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Unit", "Metadata")
VALUES (
  'Deposit Sizes',
  'Size of found deposits. Approximate values.',
  'PED',
  '{"columns":["Level","From","Expires"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Unit" = EXCLUDED."Unit",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Deposit Sizes'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Value", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Minimal', '0.05', '{"Level":"I","From":0.05,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Tiny', '0.25', '{"Level":"II","From":0.25,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Very Poor', '1', '{"Level":"III","From":1,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Poor', '2', '{"Level":"IV","From":2,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Small', '3', '{"Level":"V","From":3,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Modest', '4.5', '{"Level":"VI","From":4.5,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Average', '6', '{"Level":"VII","From":6,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '8', '{"Level":"VIII","From":8,"Expires":"1h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Ample', '12', '{"Level":"IX","From":12,"Expires":"2h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Considerable', '18', '{"Level":"X","From":18,"Expires":"3h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Sizable', '25', '{"Level":"XI","From":25,"Expires":"6h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Large', '35', '{"Level":"XII","From":35,"Expires":"10h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Abundant', '50', '{"Level":"XIII","From":50,"Expires":"18h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '75', '{"Level":"XIV","From":75,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Substantial', '125', '{"Level":"XV","From":125,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Significant', '200', '{"Level":"XVI","From":200,"Expires":"24h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Plentiful', '300', '{"Level":"XVII","From":300,"Expires":"36h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Huge', '450', '{"Level":"XVIII","From":450,"Expires":"36h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Extremely Large', '650', '{"Level":"XIX","From":650,"Expires":"48h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Massive', '800', '{"Level":"XX","From":800,"Expires":"72h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Vast', '1200', '{"Level":"XXI","From":1200,"Expires":"96h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Enormous', '2500', '{"Level":"XXII","From":2500,"Expires":"120h"}'::jsonb),
  ((SELECT "Id" FROM e), 'Rich', '5000', '{"Level":"XXIII","From":5000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Gigantic', '25000', '{"Level":"XXIV","From":25000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Mammoth', '100000', '{"Level":"XXV","From":100000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Colossal', '250000', '{"Level":"XXVI","From":250000,"Expires":null}'::jsonb),
  ((SELECT "Id" FROM e), 'Immense', '500000', '{"Level":"XXVII","From":500000,"Expires":null}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Value" = EXCLUDED."Value",
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Durability
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Unit", "Metadata")
VALUES (
  'Durability',
  'Durability levels used to hint at decay behavior.',
  'PEC',
  '{"columns":["From"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Unit" = EXCLUDED."Unit",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Durability'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Value", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Exceptional', '0', '{"From":0}'::jsonb),
  ((SELECT "Id" FROM e), 'Excellent', '0.1', '{"From":0.1}'::jsonb),
  ((SELECT "Id" FROM e), 'Very Good', '0.5', '{"From":0.5}'::jsonb),
  ((SELECT "Id" FROM e), 'Good', '1', '{"From":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Above Average', '2.5', '{"From":2.5}'::jsonb),
  ((SELECT "Id" FROM e), 'Average', '5', '{"From":5}'::jsonb),
  ((SELECT "Id" FROM e), 'Below Average', '10', '{"From":10}'::jsonb),
  ((SELECT "Id" FROM e), 'Mediocre', '25', '{"From":25}'::jsonb),
  ((SELECT "Id" FROM e), 'Inferior', '45', '{"From":45}'::jsonb),
  ((SELECT "Id" FROM e), 'Fragile', '100', '{"From":100}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Value" = EXCLUDED."Value",
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Damage Potential
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Unit", "Metadata")
VALUES (
  'Damage Potential',
  'Damage potential ranges.',
  'HP',
  '{"columns":["From"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Unit" = EXCLUDED."Unit",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Damage Potential'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Value", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Minimal', '1', '{"From":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Small', '20', '{"From":20}'::jsonb),
  ((SELECT "Id" FROM e), 'Limited', '30', '{"From":30}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '40', '{"From":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Large', '60', '{"From":60}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '101', '{"From":101}'::jsonb),
  ((SELECT "Id" FROM e), 'Huge', '161', '{"From":161}'::jsonb),
  ((SELECT "Id" FROM e), 'Immense', '271', '{"From":271}'::jsonb),
  ((SELECT "Id" FROM e), 'Gigantic', '356', '{"From":356}'::jsonb),
  ((SELECT "Id" FROM e), 'Colossal', '500', '{"From":500}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Value" = EXCLUDED."Value",
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Health Ranks
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Unit", "Metadata")
VALUES (
  'Health Ranks',
  'Avatar health level ranks.',
  'Level',
  '{"columns":["Level"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Unit" = EXCLUDED."Unit",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Health Ranks'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Value", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Puny', '0', '{"Level":0}'::jsonb),
  ((SELECT "Id" FROM e), 'Frail', '40', '{"Level":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Weak', '90', '{"Level":90}'::jsonb),
  ((SELECT "Id" FROM e), 'Medium', '150', '{"Level":150}'::jsonb),
  ((SELECT "Id" FROM e), 'Tough', '250', '{"Level":250}'::jsonb),
  ((SELECT "Id" FROM e), 'Strong', '500', '{"Level":500}'::jsonb),
  ((SELECT "Id" FROM e), 'Massive', '1000', '{"Level":1000}'::jsonb),
  ((SELECT "Id" FROM e), 'Extremely high', '2500', '{"Level":2500}'::jsonb),
  ((SELECT "Id" FROM e), 'Enormous', '5000', '{"Level":5000}'::jsonb),
  ((SELECT "Id" FROM e), 'Mammoth', '10000', '{"Level":10000}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Value" = EXCLUDED."Value",
  "Data" = EXCLUDED."Data";

-- ============================================================================
-- Skill Ranks (Skill column only)
-- ============================================================================

INSERT INTO "Enumerations" ("Name", "Description", "Unit", "Metadata")
VALUES (
  'Skill Ranks',
  'Skill rank names mapped to skill levels (profession column omitted).',
  'Level',
  '{"columns":["Skill"]}'::jsonb
)
ON CONFLICT ("Name") DO UPDATE
SET
  "Description" = EXCLUDED."Description",
  "Unit" = EXCLUDED."Unit",
  "Metadata" = EXCLUDED."Metadata";

WITH e AS (
  SELECT "Id" FROM ONLY "Enumerations" WHERE "Name" = 'Skill Ranks'
)
INSERT INTO "EnumerationValues" ("EnumerationId", "Name", "Value", "Data")
VALUES
  ((SELECT "Id" FROM e), 'Newbie', '1', '{"Skill":1}'::jsonb),
  ((SELECT "Id" FROM e), 'Inept', '10', '{"Skill":10}'::jsonb),
  ((SELECT "Id" FROM e), 'Poor', '20', '{"Skill":20}'::jsonb),
  ((SELECT "Id" FROM e), 'Weak', '40', '{"Skill":40}'::jsonb),
  ((SELECT "Id" FROM e), 'Mediocre', '67', '{"Skill":67}'::jsonb),
  ((SELECT "Id" FROM e), 'Unskilled', '110', '{"Skill":110}'::jsonb),
  ((SELECT "Id" FROM e), 'Green', '160', '{"Skill":160}'::jsonb),
  ((SELECT "Id" FROM e), 'Beginner', '260', '{"Skill":260}'::jsonb),
  ((SELECT "Id" FROM e), 'Novice', '360', '{"Skill":360}'::jsonb),
  ((SELECT "Id" FROM e), 'Amateur', '460', '{"Skill":460}'::jsonb),
  ((SELECT "Id" FROM e), 'Apprentice', '600', '{"Skill":600}'::jsonb),
  ((SELECT "Id" FROM e), 'Initiated', '800', '{"Skill":800}'::jsonb),
  ((SELECT "Id" FROM e), 'Qualified', '1000', '{"Skill":1000}'::jsonb),
  ((SELECT "Id" FROM e), 'Trained', '1200', '{"Skill":1200}'::jsonb),
  ((SELECT "Id" FROM e), 'Able', '1400', '{"Skill":1400}'::jsonb),
  ((SELECT "Id" FROM e), 'Competent', '1600', '{"Skill":1600}'::jsonb),
  ((SELECT "Id" FROM e), 'Adept', '1800', '{"Skill":1800}'::jsonb),
  ((SELECT "Id" FROM e), 'Capable', '2000', '{"Skill":2000}'::jsonb),
  ((SELECT "Id" FROM e), 'Skilled', '2200', '{"Skill":2200}'::jsonb),
  ((SELECT "Id" FROM e), 'Experienced', '2400', '{"Skill":2400}'::jsonb),
  ((SELECT "Id" FROM e), 'Proficient', '2600', '{"Skill":2600}'::jsonb),
  ((SELECT "Id" FROM e), 'Good', '2800', '{"Skill":2800}'::jsonb),
  ((SELECT "Id" FROM e), 'Great', '3000', '{"Skill":3000}'::jsonb),
  ((SELECT "Id" FROM e), 'Inspiring', '3200', '{"Skill":3200}'::jsonb),
  ((SELECT "Id" FROM e), 'Impressive', '3400', '{"Skill":3400}'::jsonb),
  ((SELECT "Id" FROM e), 'Veteran', '3600', '{"Skill":3600}'::jsonb),
  ((SELECT "Id" FROM e), 'Professional', '3800', '{"Skill":3800}'::jsonb),
  ((SELECT "Id" FROM e), 'Specialist', '4000', '{"Skill":4000}'::jsonb),
  ((SELECT "Id" FROM e), 'Advanced', '4200', '{"Skill":4200}'::jsonb),
  ((SELECT "Id" FROM e), 'Remarkable', '4500', '{"Skill":4500}'::jsonb),
  ((SELECT "Id" FROM e), 'Expert', '4800', '{"Skill":4800}'::jsonb),
  ((SELECT "Id" FROM e), 'Exceptional', '5100', '{"Skill":5100}'::jsonb),
  ((SELECT "Id" FROM e), 'Amazing', '5400', '{"Skill":5400}'::jsonb),
  ((SELECT "Id" FROM e), 'Incredible', '5700', '{"Skill":5700}'::jsonb),
  ((SELECT "Id" FROM e), 'Marvelous', '6000', '{"Skill":6000}'::jsonb),
  ((SELECT "Id" FROM e), 'Astonishing', '6300', '{"Skill":6300}'::jsonb),
  ((SELECT "Id" FROM e), 'Outstanding', '6600', '{"Skill":6600}'::jsonb),
  ((SELECT "Id" FROM e), 'Champion', '6900', '{"Skill":6900}'::jsonb),
  ((SELECT "Id" FROM e), 'Elite', '7200', '{"Skill":7200}'::jsonb),
  ((SELECT "Id" FROM e), 'Superior', '7500', '{"Skill":7500}'::jsonb),
  ((SELECT "Id" FROM e), 'Supreme', '7800', '{"Skill":7800}'::jsonb),
  ((SELECT "Id" FROM e), 'Master', '8100', '{"Skill":8100}'::jsonb),
  ((SELECT "Id" FROM e), 'Grand Master', '8400', '{"Skill":8400}'::jsonb),
  ((SELECT "Id" FROM e), 'Arch Master', '8700', '{"Skill":8700}'::jsonb),
  ((SELECT "Id" FROM e), 'Supreme Master', '9100', '{"Skill":9100}'::jsonb),
  ((SELECT "Id" FROM e), 'Ultimate Master', '9500', '{"Skill":9500}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Master', '10000', '{"Skill":10000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Grand Master', '12000', '{"Skill":12000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Arch Master', '14000', '{"Skill":14000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Supreme Master', '16000', '{"Skill":16000}'::jsonb),
  ((SELECT "Id" FROM e), 'Great Ultimate Master', '18000', '{"Skill":18000}'::jsonb),
  ((SELECT "Id" FROM e), 'Entropia Master', '20000', '{"Skill":20000}'::jsonb)
ON CONFLICT ("EnumerationId", "Name") DO UPDATE
SET
  "Value" = EXCLUDED."Value",
  "Data" = EXCLUDED."Data";

COMMIT;
