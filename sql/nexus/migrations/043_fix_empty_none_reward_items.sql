-- Migration 043: Remove fake "None"/"Unknown"/"Nothing"/"?" reward items
--
-- These missions had their reward items imported with placeholder text like
-- "None", "Unknown", "Nothing", or "?" instead of actual items.
-- They have no other item or skill rewards — these are missions that genuinely
-- have no item rewards. Set Items to null.
--
-- 60 missions with "None"/"Unknown"/"Nothing" + 2 missions with "?"
-- Source of truth: tools/data import/missions/mission-analysis-results.json

UPDATE ONLY "MissionRewards"
SET "Items" = NULL
WHERE "Items" IS NOT NULL
  AND jsonb_array_length("Items") = 1
  AND (
    ("Items" -> 0 ->> 'itemName') IN ('None', 'Unknown', 'Nothing', '?')
  )
  AND ("Items" -> 0 -> 'itemId') IS NULL;
