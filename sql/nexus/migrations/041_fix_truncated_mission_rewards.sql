-- Migration 041: Fix truncated mission reward data from bot import
--
-- Fixes two categories of bad data:
-- 1. Items with itemName "PED TT)" — truncated skill descriptions that aren't real items.
--    These missions already have proper skill entries with skillItemId, so the item is redundant.
-- 2. Skills with single-character skillName (e.g. "P", "A", "H") and no skillItemId —
--    truncated first letter of the actual skill name. Only removed when the same reward row
--    already has a proper skill entry with skillItemId.

DO $$
DECLARE
  _row RECORD;
  _new_items JSONB;
  _new_skills JSONB;
  _elem JSONB;
  _i INTEGER;
  _changed BOOLEAN;
  _has_proper_skill BOOLEAN;
BEGIN
  -- =========================================================================
  -- Fix 1: Remove "PED TT)" items
  -- =========================================================================
  FOR _row IN
    SELECT mr."Id", mr."Items"
    FROM ONLY "MissionRewards" mr
    WHERE mr."Items" IS NOT NULL
      AND mr."Items"::text LIKE '%"PED TT)"%'
  LOOP
    _new_items := '[]'::jsonb;
    _changed := FALSE;

    FOR _i IN 0 .. jsonb_array_length(_row."Items") - 1
    LOOP
      _elem := _row."Items" -> _i;
      IF (_elem ->> 'itemName') = 'PED TT)' THEN
        _changed := TRUE; -- skip this element
      ELSE
        _new_items := _new_items || jsonb_build_array(_elem);
      END IF;
    END LOOP;

    IF _changed THEN
      -- If no items remain, set to null
      IF jsonb_array_length(_new_items) = 0 THEN
        _new_items := NULL;
      END IF;
      UPDATE ONLY "MissionRewards" SET "Items" = _new_items WHERE "Id" = _row."Id";
    END IF;
  END LOOP;

  -- =========================================================================
  -- Fix 2: Remove single-letter truncated skill entries
  -- Only when the same row also has a proper skill with skillItemId
  -- =========================================================================
  FOR _row IN
    SELECT mr."Id", mr."Skills"
    FROM ONLY "MissionRewards" mr
    WHERE mr."Skills" IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM jsonb_array_elements(mr."Skills") elem
        WHERE length(elem ->> 'skillName') = 1
          AND elem -> 'skillItemId' IS NULL
      )
  LOOP
    -- Check if this row has at least one proper skill entry
    _has_proper_skill := EXISTS (
      SELECT 1 FROM jsonb_array_elements(_row."Skills") elem
      WHERE elem -> 'skillItemId' IS NOT NULL
    );

    IF NOT _has_proper_skill THEN
      CONTINUE; -- Don't touch rows that only have the truncated entry
    END IF;

    _new_skills := '[]'::jsonb;
    _changed := FALSE;

    FOR _i IN 0 .. jsonb_array_length(_row."Skills") - 1
    LOOP
      _elem := _row."Skills" -> _i;
      IF length(_elem ->> 'skillName') = 1 AND (_elem -> 'skillItemId') IS NULL THEN
        _changed := TRUE; -- skip truncated entry
      ELSE
        _new_skills := _new_skills || jsonb_build_array(_elem);
      END IF;
    END LOOP;

    IF _changed THEN
      IF jsonb_array_length(_new_skills) = 0 THEN
        _new_skills := NULL;
      END IF;
      UPDATE ONLY "MissionRewards" SET "Skills" = _new_skills WHERE "Id" = _row."Id";
    END IF;
  END LOOP;
END $$;
