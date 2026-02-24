-- Migration 042: Fix missions where skill rewards were stored as item names
--
-- These missions had their reward data imported from CSV with skill descriptions
-- parsed as item names (e.g. "Laser Weaponry Technology skill (eq. 0.09 PED implant)").
-- This migration converts them to proper skill entries with skillItemId and pedValue.
--
-- Source of truth: tools/data import/missions/mission-analysis-results.json
--
-- Categories fixed:
-- 1. Choice rewards with skill descriptions as items → convert to proper skill entries
-- 2. Empty choice rewards (Items: []) → populate from source data
-- 3. Non-choice rewards with truncated item descriptions → add pedValue

DO $$
DECLARE
  _reward_id INTEGER;
BEGIN
  -- =========================================================================
  -- Fix 1: Clear out the digsite (RewardId 168, choice rewards)
  -- Source: Choice of Weapon Cells (2.4 PED), BLP Packs (2.4 PED),
  --         or Laser Weaponry Technology skill (0.09 PED implant)
  -- Current: itemId 1002501 ok, "BLP packs" missing itemId, "Laser Weaponry Technology skill" is a skill
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Clear out the digsite';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [{"itemId": 1002501, "pedValue": 2.4}], "Skills": [], "Unlocks": []},
      {"Items": [{"itemId": 1000337, "pedValue": 2.4}], "Skills": [], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200205, "pedValue": 0.09}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 2: Iron Challenge: Caudatergus Stage II (RewardId 671)
  -- Source: Choice of Aim (0.30 PED), Combat Reflexes (0.30 PED), Clubs (0.19 PED)
  -- Current: Items: [], Skills: null (completely empty)
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Caudatergus Stage II';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200170, "pedValue": 0.30}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200172, "pedValue": 0.30}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200171, "pedValue": 0.19}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 3: Iron Challenge: Caudatergus Stage III (RewardId 672)
  -- Source: Choice of Anatomy (0.45 PED), Power Fist (0.45 PED), Diagnosis (0.14 PED)
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Caudatergus Stage III';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200267, "pedValue": 0.45}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200187, "pedValue": 0.45}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200268, "pedValue": 0.14}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 4: Iron Challenge: Caudatergus Stage IV (RewardId 673)
  -- Source: Choice of Longblades (0.60 PED), Vehicle Repairing (0.38 PED), Evade (0.19 PED)
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Caudatergus Stage IV';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200182, "pedValue": 0.60}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200225, "pedValue": 0.38}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200233, "pedValue": 0.19}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 5: Iron Challenge: Hispidus Stage I (RewardId 699)
  -- Source: Choice of Perception (2.03 PED), Courage (1.31 PED), Bravado (0.65 PED)
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Hispidus Stage I';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200251, "pedValue": 2.03}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200248, "pedValue": 1.31}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200246, "pedValue": 0.65}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 6: Iron Challenge: Oculus Stage III (RewardId 720)
  -- Source: Choice of Aim (18.25 PED), Light Melee Weapons (11.88 PED), Telepathy (5.94 PED)
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Iron Challenge: Oculus Stage III';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200170, "pedValue": 18.25}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200181, "pedValue": 11.88}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200284, "pedValue": 5.94}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 7: Resources for Dolph (RewardId 1022, choice format)
  -- Source: "0.15 Ped of Prospecting" + Surveying skill (pedValue: 0)
  -- Current: has bad item "of Prospecting" (truncated) + Surveying skill
  -- Fix: Replace bad item with proper Prospecting skill entry
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Resources for Dolph';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200298, "pedValue": 0.15}, {"skillItemId": 4200300}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 8: The missing parts (RewardId 1180, choice rewards)
  -- Source: Choice of Universal Ammo (2.40 PED) or Dexterity skill (0.08 PED implant)
  -- Current: itemId 1002428 ok but no pedValue, "Dexterity skill" is a skill
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'The missing parts';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [{"itemId": 1002428, "pedValue": 2.40}], "Skills": [], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200249, "pedValue": 0.08}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 9: The Reaver's Redemption: Stage I (RewardId 1194, choice rewards)
  -- Source: Choice of Longblades (1.55 PED), Vehicle Repairing (1.00 PED),
  --         or Electrokinesis (0.50 PED)
  -- Current: All stored as item names like "Longblades Skill"
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'The Reaver''s Redemption: Stage I';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200182, "pedValue": 1.55}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200225, "pedValue": 1.00}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200277, "pedValue": 0.50}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 10: The Reaver's Redemption: Stage II (RewardId 1195, choice rewards)
  -- Source: Choice of Perception (3.88 PED), Alertness (2.51 PED),
  --         or Diagnosis (1.25 PED)
  -- Current: All stored as item names like "Perception Skill"
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'The Reaver''s Redemption: Stage II';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[
      {"Items": [], "Skills": [{"skillItemId": 4200251, "pedValue": 3.88}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200244, "pedValue": 2.51}], "Unlocks": []},
      {"Items": [], "Skills": [{"skillItemId": 4200268, "pedValue": 1.25}], "Unlocks": []}
    ]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

  -- =========================================================================
  -- Fix 11: Paneleon Hunter Jameson's Mission (RewardId 1348, flat reward)
  -- Source: "1.5 PED Universal Ammo"
  -- Current: itemId 1002428 correct, but missing pedValue
  -- =========================================================================
  SELECT mr."Id" INTO _reward_id
  FROM ONLY "MissionRewards" mr
  JOIN ONLY "Missions" m ON m."Id" = mr."MissionId"
  WHERE m."Name" = 'Paneleon Hunter Jameson''s Mission';

  IF _reward_id IS NOT NULL THEN
    UPDATE ONLY "MissionRewards" SET "Items" = '[{"itemId": 1002428, "pedValue": 1.5}]'::jsonb
    WHERE "Id" = _reward_id;
  END IF;

END $$;
