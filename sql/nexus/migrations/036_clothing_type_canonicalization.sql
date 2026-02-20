-- Migration 036: Canonicalize clothing Type values
-- Normalizes pluralization, fixes misclassifications, assigns types to untyped items,
-- and removes duplicate empty-shell entries.

BEGIN;

-- Step 1: Delete duplicate empty-shell items
-- These "Cap" variants have no data (null type, slot, gender, weight, value)
-- alongside fully populated "Hat" variants with the same name pattern
DELETE FROM ONLY "Clothes" WHERE "Id" IN (204, 305);

-- Step 2: Normalize plural types to singular (single-piece garments use singular)
UPDATE ONLY "Clothes" SET "Type" = 'Cloak' WHERE "Type" = 'Cloaks';
UPDATE ONLY "Clothes" SET "Type" = 'Coat' WHERE "Type" = 'Coats';
UPDATE ONLY "Clothes" SET "Type" = 'Dress' WHERE "Type" = 'Dresses';
UPDATE ONLY "Clothes" SET "Type" = 'Hat' WHERE "Type" = 'Hats';
UPDATE ONLY "Clothes" SET "Type" = 'Jacket' WHERE "Type" = 'Jackets';
UPDATE ONLY "Clothes" SET "Type" = 'Jumpsuit' WHERE "Type" = 'Jumpsuits';
UPDATE ONLY "Clothes" SET "Type" = 'Shirt' WHERE "Type" = 'Shirts';

-- Step 3: Eliminate non-standard types
UPDATE ONLY "Clothes" SET "Type" = 'Pants' WHERE "Type" = 'Slacks';
UPDATE ONLY "Clothes" SET "Type" = 'Coat' WHERE "Type" = 'Back';

-- Step 4: Reclassify items whose type doesn't match their name

-- "Common" is not a clothing type
UPDATE ONLY "Clothes" SET "Type" = 'Hat' WHERE "Name" = 'Christmas Swirl Hat';
UPDATE ONLY "Clothes" SET "Type" = 'Underwear' WHERE "Name" = 'Mankini (M, C)';

-- Cloaks miscategorized as Coat
UPDATE ONLY "Clothes" SET "Type" = 'Cloak' WHERE "Name" IN (
  'Vampiric Cloak of Lifesteal',
  'Vampiric Cloak of Vitality'
);

-- Horns miscategorized as Shades
UPDATE ONLY "Clothes" SET "Type" = 'Horns' WHERE "Name" = 'The Horns of Z''agol';

-- Boots↔Shoes name mismatches
UPDATE ONLY "Clothes" SET "Type" = 'Shoes' WHERE "Name" IN (
  'Imperium Common Shoes',
  'Imperium Noble Shoes',
  'Motamared Shoe (C)'
);
UPDATE ONLY "Clothes" SET "Type" = 'Boots' WHERE "Name" IN (
  'Haruspex Voodoo Boots (C)',
  'Haruspex Voodoo Boots (M)',
  'Turrelia Touched Boots'
);

-- Ram Horns miscategorized as Hat → Horns
UPDATE ONLY "Clothes" SET "Type" = 'Horns' WHERE "Name" LIKE '%Ram Horns';

-- Bunny Ears miscategorized as Hat → Ears
UPDATE ONLY "Clothes" SET "Type" = 'Ears' WHERE "Name" LIKE '%Bunny Ears%';

-- Step 5: Assign types to null/empty-typed items
UPDATE ONLY "Clothes" SET "Type" = 'Suit' WHERE "Name" LIKE 'Ark Formal Tuxedo%';
UPDATE ONLY "Clothes" SET "Type" = 'Dress' WHERE "Name" = 'Evening Gown';
UPDATE ONLY "Clothes" SET "Type" = 'Gloves' WHERE "Name" = 'Guardian Nurse Gloves (F)';
UPDATE ONLY "Clothes" SET "Type" = 'Hat' WHERE "Name" = 'Guardian Nurse Tiara (F)';
UPDATE ONLY "Clothes" SET "Type" = 'Coat' WHERE "Name" = 'Habkeh (C)';
UPDATE ONLY "Clothes" SET "Type" = 'Shirt' WHERE "Name" = 'IFN Combat Uniform Arctic Shirt' AND "Type" IS NULL;
UPDATE ONLY "Clothes" SET "Type" = 'Shirt' WHERE "Name" IN (
  'La Fleur Sexy Top (C)',
  'Motorhead ROCK T-Shirt (C)',
  'Nuclear Blast ROCK T-Shirt (C)',
  'Nuclear Blast Sexy Top (C)',
  'Staff Shirt (F)'
);
UPDATE ONLY "Clothes" SET "Type" = 'Hat' WHERE "Name" = 'Travellers Hood (M)';
UPDATE ONLY "Clothes" SET "Type" = 'Coat' WHERE "Name" = 'Travellers Robe (M)';
UPDATE ONLY "Clothes" SET "Type" = 'Other' WHERE "Name" = 'True Islander Magic Flower';

COMMIT;
