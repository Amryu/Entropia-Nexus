-- Migration 045: Fix missions with PED skill descriptions stored as item names
--
-- These missions have Items entries like:
--   "0.30 PED Perception" — skill reward description
--   "0.57 PED Skill + 5 Attribute Tokens" — compound reward description
--   "Approx 0.5 PED Courage" — approximate skill description
--   "Combat Reflexes 0.11 PED Perception 0.11 PED..." — multi-skill description
--   "PED Athletics" — truncated PED amount + skill
--   "(eq. 0.09 PED implant)" style descriptions
--   "5.12 ped" — bare PED amount
--   "31.56, 20.31,10.16. skill of choice" — choice skill description
--
-- Most of these already have the correct skill reward in the Skills column;
-- the item text is redundant. For those, just clear Items.
--
-- Special cases handled individually when Skills is null.

DO $$
DECLARE
  _reward_id INTEGER;
BEGIN
  -- =========================================================================
  -- Part A: Clear redundant PED-description items when Skills already exists
  -- Pattern: item text describes skills that are already in the Skills column
  -- =========================================================================
  UPDATE ONLY "MissionRewards"
  SET "Items" = NULL
  WHERE "Items" IS NOT NULL
    AND "Skills" IS NOT NULL
    AND jsonb_array_length("Items") = 1
    AND ("Items" -> 0 -> 'itemId') IS NULL
    AND ("Items" -> 0 -> 'Items') IS NULL
    AND (
      -- "N.NN PED SkillName" or "N.NN PED Skill + ..." or "N.NN PED Handgun, Longblades"
      ("Items" -> 0 ->> 'itemName') ~ '^\d+\.?\d*\s*PED\s'
      -- "Approx N.NN PED SkillName"
      OR ("Items" -> 0 ->> 'itemName') LIKE 'Approx%PED%'
      -- "PED SkillName" (truncated amount)
      OR ("Items" -> 0 ->> 'itemName') ~ '^PED\s+\w'
      -- "SkillName N.NN PED SkillName N.NN PED..." (multi-skill)
      OR ("Items" -> 0 ->> 'itemName') ~ '^\w+.*\d+\.\d+\s*PED\s+\w+.*\d+\.\d+\s*PED'
    );

  -- =========================================================================
  -- Part B: Clear "(eq. N PED implant)" style items when Skills already exists
  -- =========================================================================
  UPDATE ONLY "MissionRewards"
  SET "Items" = NULL
  WHERE "Items" IS NOT NULL
    AND "Skills" IS NOT NULL
    AND jsonb_array_length("Items") = 1
    AND ("Items" -> 0 -> 'itemId') IS NULL
    AND ("Items" -> 0 -> 'Items') IS NULL
    AND ("Items" -> 0 ->> 'itemName') ~ '\(eq\.?\s*\d';

  -- =========================================================================
  -- Part C: Specific fixes for missions with Skills=null
  -- =========================================================================

  -- "A.R.C. Prestige - Judgement of the Serpent"
  -- Item: "0.5 PED of Texture Pattern Matching"
  -- → Texture Pattern Matching skill (4200243) with pedValue 0.5
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'A.R.C. Prestige - Judgement of the Serpent'
    AND mr."Skills" IS NULL;

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards"
    SET "Items" = NULL,
        "Skills" = '[{"skillItemId": 4200243, "pedValue": 0.5}]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- "The Will and Testament of Vampire Nostra #2"
  -- Item: "5.12 ped" — bare PED amount, no skill info. Clear it.
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'The Will and Testament of Vampire Nostra #2'
    AND mr."Items" IS NOT NULL
    AND (mr."Items" -> 0 ->> 'itemName') = '5.12 ped';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = NULL WHERE "Id" = _reward_id;
  END IF;

  -- "? PED of Dexterity" — unknown PED amount skill reward
  -- A.R.C. Prestige - The Enemy of my Enemy
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'A.R.C. Prestige - The Enemy of my Enemy'
    AND mr."Items" IS NOT NULL
    AND (mr."Items" -> 0 ->> 'itemName') = '? PED of Dexterity';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards"
    SET "Items" = NULL,
        "Skills" = '[{"skillItemId": 4200249}]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- "Iron Challenge: Harbinger Stage IV"
  -- Item: "31.56, 20.31,10.16. skill of choice"
  -- This is a choice of skill rewards at different PED values. No structured data possible.
  -- Clear the unstructured text.
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Harbinger Stage IV'
    AND mr."Items" IS NOT NULL
    AND (mr."Items" -> 0 ->> 'itemName') LIKE '%skill of choice%';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = NULL WHERE "Id" = _reward_id;
  END IF;

  -- "(L)" truncated item name — "Herbal Remedies"
  -- Item: "(L)" — truncated blueprint or item name. Clear it.
  UPDATE ONLY "MissionRewards"
  SET "Items" = NULL
  WHERE "Items" IS NOT NULL
    AND jsonb_array_length("Items") = 1
    AND ("Items" -> 0 -> 'itemId') IS NULL
    AND ("Items" -> 0 ->> 'itemName') = '(L)';

  -- "PED TT)" truncated items — already handled by migration 041
  -- but catch any remaining ones
  UPDATE ONLY "MissionRewards"
  SET "Items" = NULL
  WHERE "Items" IS NOT NULL
    AND jsonb_array_length("Items") = 1
    AND ("Items" -> 0 -> 'itemId') IS NULL
    AND ("Items" -> 0 ->> 'itemName') LIKE 'PED TT)%';

END $$;
