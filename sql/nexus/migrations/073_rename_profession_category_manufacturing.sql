-- Rename profession category "Manufacturing" -> "Construction" to match
-- the in-game label, which was changed at some point. All crafting
-- professions (Tailor, Armor Maker, Weapon Smith, etc. plus the new
-- fishing/food profs from migration 072) continue to reference the same
-- CategoryId = 4, so no Professions rows need updating.

UPDATE "ProfessionCategories"
SET "Name" = 'Construction'
WHERE "Id" = 4 AND "Name" = 'Manufacturing';
