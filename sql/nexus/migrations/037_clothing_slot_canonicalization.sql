-- Migration 037: Canonicalize clothing Slot values
-- Assigns Slot (body part) to clothing items where the Type→Slot mapping is unambiguous.
-- Underwear items use "Inner" prefix to avoid blocking outer clothing layers.
-- Must run AFTER migration 036 (type canonicalization).

BEGIN;

-- Step 1: Fix existing incorrect slots
UPDATE ONLY "Clothes" SET "Slot" = 'Legs' WHERE "Name" = 'Frontier Pants';
UPDATE ONLY "Clothes" SET "Slot" = 'Middle Torso' WHERE "Name" = 'Frontier Shirt';
UPDATE ONLY "Clothes" SET "Slot" = 'Outer Torso' WHERE "Name" = 'Frontier Coat';
UPDATE ONLY "Clothes" SET "Slot" = 'Full Body' WHERE "Name" = 'Standard Undersuit';
UPDATE ONLY "Clothes" SET "Slot" = 'Inner Legs' WHERE "Name" = 'Mankini (M, C)';

-- Step 2: Bulk Type → Slot (only where Slot IS NULL, preserving existing values)
UPDATE ONLY "Clothes" SET "Slot" = 'Feet' WHERE "Type" IN ('Boots', 'Shoes') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Hands' WHERE "Type" = 'Gloves' AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Head' WHERE "Type" IN ('Hat', 'Horns', 'Ears') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Face' WHERE "Type" IN ('Facemask', 'Shades') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Legs' WHERE "Type" IN ('Pants', 'Shorts', 'Skirt', 'Dress') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Middle Torso' WHERE "Type" = 'Shirt' AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Outer Torso' WHERE "Type" IN ('Jacket', 'Coat') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Back' WHERE "Type" IN ('Cloak', 'Wings', 'Backpack', 'Rucksack') AND "Slot" IS NULL;
UPDATE ONLY "Clothes" SET "Slot" = 'Full Body' WHERE "Type" = 'Jumpsuit' AND "Slot" IS NULL;

-- Step 3: Underwear sub-types by name pattern

-- Inner Torso: bras, bustiers, tanktops, singlets, tops
UPDATE ONLY "Clothes" SET "Slot" = 'Inner Torso'
WHERE "Type" = 'Underwear' AND "Slot" IS NULL
AND ("Name" LIKE '%Bra' OR "Name" LIKE '%Bra (%'
  OR "Name" LIKE '%Bustier%' OR "Name" LIKE '%Tanktop%'
  OR "Name" LIKE '%Singlet%' OR "Name" LIKE '% Top');

-- Inner Legs: panties, g-strings, briefs, thongs, underpants, undershorts, shorts
UPDATE ONLY "Clothes" SET "Slot" = 'Inner Legs'
WHERE "Type" = 'Underwear' AND "Slot" IS NULL
AND ("Name" LIKE '%Panties%' OR "Name" LIKE '%G-String%'
  OR "Name" LIKE '%Briefs' OR "Name" LIKE '%Thong%'
  OR "Name" LIKE '%Underpants' OR "Name" LIKE '%Undershorts'
  OR "Name" LIKE '%Shorts%' OR "Name" LIKE 'Mankini%'
  OR "Name" = 'Comfy Womfies');

-- Inner Feet: socks, stockings (not bodystocking)
UPDATE ONLY "Clothes" SET "Slot" = 'Inner Feet'
WHERE "Type" = 'Underwear' AND "Slot" IS NULL
AND ("Name" LIKE '%Socks%' OR "Name" = 'Tiger Stockings (C)');

-- Remaining null: Bodystocking (F, C), Rinoa Bikini (F) — left null (ambiguous)

COMMIT;
