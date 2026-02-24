-- Migration 044: Fix missions with bare skill/attribute names stored as items
--
-- Missions have Items entries like {"itemName": "Athletics"} or {"itemName": "Weapons Handling"}
-- where these are actually skill rewards, not items.
--
-- Two subcategories:
-- A) Missions that already have the correct skill in Skills column — just clear Items
-- B) Missions with Skills=null — create the skill entry from the item name
--
-- Also handles:
-- - Misspellings: "Alterness" → Alertness, "Shortblade" → Shortblades
-- - Variants: "BLP Weapon Technology" → BLP Weaponry Technology,
--             "Heavy Melee Weapons" → Heavy Melee Weapons (full name)
-- - Comma-separated: "Aim, Anatomy" (already has Skills, just clear Items)
-- - Generic "Skills" (clear if Skills exists, leave if not)

DO $$
DECLARE
  _row RECORD;
  _item_name TEXT;
  _skill_id INTEGER;

  -- All known skill/attribute names that appear incorrectly as items
  _skill_names TEXT[] := ARRAY[
    -- Attributes (no skillItemId)
    'Strength', 'Agility', 'Stamina', 'Psyche', 'Intelligence', 'Courage',
    -- Skills with implant IDs
    'Aim', 'Alertness', 'Anatomy', 'Armor Technology', 'Athletics',
    'BLP Weaponry', 'BLP Weapon Technology', 'Clubs', 'Combat Reflexes',
    'Concentration', 'Coolness', 'Dexterity', 'Dodge', 'Engineering',
    'Evade', 'Explosive Projectile Weaponry', 'First Aid', 'Geology',
    'Handgun', 'Heavy Melee', 'Heavy Melee Weapons',
    'Inflict Melee Damage', 'Laser Weaponry', 'Longblades',
    'Manufacture Mechanical Equipment', 'Manufacture Metal Equipment',
    'Manufacture Weapons', 'Melee', 'Perception', 'Power Fist',
    'Probing', 'Ranged Damage', 'Rifle', 'Shortblades', 'Shortblade',
    'Tailoring', 'Weapons Handling', 'Whip',
    -- Misspellings
    'Alterness',
    -- Comma-separated / generic (only clear if Skills exists)
    'Aim, Anatomy', 'Skills'
  ];
BEGIN
  -- =========================================================================
  -- Part A: Missions that already have a skill in Skills — just clear Items
  -- =========================================================================
  UPDATE ONLY "MissionRewards"
  SET "Items" = NULL
  WHERE "Items" IS NOT NULL
    AND "Skills" IS NOT NULL
    AND jsonb_array_length("Items") = 1
    AND ("Items" -> 0 -> 'itemId') IS NULL
    AND ("Items" -> 0 -> 'Items') IS NULL
    AND ("Items" -> 0 ->> 'itemName') = ANY(_skill_names);

  -- =========================================================================
  -- Part B: Missions with bare skill name in Items and Skills=null
  -- Convert the item name to a proper skill entry
  -- =========================================================================
  FOR _row IN
    SELECT mr."Id", mr."Items" -> 0 ->> 'itemName' AS item_name
    FROM ONLY "MissionRewards" mr
    WHERE mr."Items" IS NOT NULL
      AND mr."Skills" IS NULL
      AND jsonb_array_length(mr."Items") = 1
      AND (mr."Items" -> 0 -> 'itemId') IS NULL
      AND (mr."Items" -> 0 -> 'Items') IS NULL
      AND (mr."Items" -> 0 ->> 'itemName') = ANY(_skill_names)
      -- Skip generic "Skills" when Skills is null — too vague to fix
      AND (mr."Items" -> 0 ->> 'itemName') != 'Skills'
  LOOP
    _item_name := _row.item_name;
    _skill_id := NULL;

    -- Map skill names (including variants/misspellings) to Skill Implant IDs
    CASE _item_name
      WHEN 'Aim' THEN _skill_id := 4200170;
      WHEN 'Alertness' THEN _skill_id := 4200244;
      WHEN 'Alterness' THEN _skill_id := 4200244;  -- misspelling
      WHEN 'Anatomy' THEN _skill_id := 4200267;
      WHEN 'Armor Technology' THEN _skill_id := 4200195;
      WHEN 'Athletics' THEN _skill_id := 4200245;
      WHEN 'BLP Weaponry' THEN _skill_id := 4200197;
      WHEN 'BLP Weapon Technology' THEN _skill_id := 4200197;  -- variant
      WHEN 'Clubs' THEN _skill_id := 4200171;
      WHEN 'Combat Reflexes' THEN _skill_id := 4200172;
      WHEN 'Concentration' THEN _skill_id := 4200275;
      WHEN 'Coolness' THEN _skill_id := 4200247;
      WHEN 'Dexterity' THEN _skill_id := 4200249;
      WHEN 'Dodge' THEN _skill_id := 4200232;
      WHEN 'Engineering' THEN _skill_id := 4200310;
      WHEN 'Evade' THEN _skill_id := 4200233;
      WHEN 'Explosive Projectile Weaponry' THEN _skill_id := 4200202;
      WHEN 'First Aid' THEN _skill_id := 4200270;
      WHEN 'Geology' THEN _skill_id := 4200291;
      WHEN 'Handgun' THEN _skill_id := 4200175;
      WHEN 'Heavy Melee' THEN _skill_id := 4200176;
      WHEN 'Heavy Melee Weapons' THEN _skill_id := 4200176;
      WHEN 'Inflict Melee Damage' THEN _skill_id := 4200178;
      WHEN 'Laser Weaponry' THEN _skill_id := 4200205;
      WHEN 'Longblades' THEN _skill_id := 4200182;
      WHEN 'Manufacture Mechanical Equipment' THEN _skill_id := 4200211;
      WHEN 'Manufacture Metal Equipment' THEN _skill_id := 4200212;
      WHEN 'Manufacture Weapons' THEN _skill_id := 4200216;
      WHEN 'Melee' THEN _skill_id := 4200185;
      WHEN 'Perception' THEN _skill_id := 4200251;
      WHEN 'Power Fist' THEN _skill_id := 4200187;
      WHEN 'Probing' THEN _skill_id := 4200255;
      WHEN 'Ranged Damage' THEN _skill_id := 4200188;
      WHEN 'Rifle' THEN _skill_id := 4200189;
      WHEN 'Shortblades' THEN _skill_id := 4200190;
      WHEN 'Shortblade' THEN _skill_id := 4200190;  -- variant
      WHEN 'Tailoring' THEN _skill_id := 4200242;
      WHEN 'Weapons Handling' THEN _skill_id := 4200192;
      WHEN 'Whip' THEN _skill_id := 4200193;
      ELSE _skill_id := NULL;
    END CASE;

    IF _skill_id IS NOT NULL THEN
      -- Proper skill with skillItemId
      UPDATE ONLY "MissionRewards"
      SET "Items" = NULL,
          "Skills" = jsonb_build_array(jsonb_build_object('skillItemId', _skill_id))
      WHERE "Id" = _row."Id";
    ELSE
      -- Attribute (Strength, Agility, etc.) — use skillName
      UPDATE ONLY "MissionRewards"
      SET "Items" = NULL,
          "Skills" = jsonb_build_array(jsonb_build_object('skillName', _item_name))
      WHERE "Id" = _row."Id";
    END IF;
  END LOOP;
END $$;
