-- Migration: AI Daily Mission NPCs
-- Adds 7 new NPC locations on Calypso, creates "Calypso AI Dailies" mission chain,
-- and 10 missions (7 Calypso + 3 Mork) with AIKillCycle/AIHandIn objectives and rewards.

BEGIN;

-- =============================================================================
-- 0. Fix audit trigger column order
-- =============================================================================
-- Audit tables may have (operation, stamp, userid) before or after the
-- inherited columns depending on when they were created. Using explicit
-- column names in the INSERT makes the trigger work regardless of order.

DO $$
DECLARE
  _tables TEXT[] := ARRAY[
    'Locations',
    'MissionChains',
    'Missions',
    'MissionSteps',
    'MissionObjectives',
    'MissionRewards'
  ];
  _t TEXT;
  _cols TEXT;
BEGIN
  FOREACH _t IN ARRAY _tables LOOP
    -- Get parent table column names in ordinal order
    SELECT string_agg('"' || column_name || '"', ', ' ORDER BY ordinal_position)
    INTO _cols
    FROM information_schema.columns
    WHERE table_name = _t AND table_schema = 'public';

    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I() RETURNS TRIGGER AS $trig$
      BEGIN
        IF (TG_OP = 'DELETE') THEN
          INSERT INTO %I (%s, "operation", "stamp", "userid")
          SELECT OLD.*, 'D', now(), current_user;
          RETURN OLD;
        ELSIF (TG_OP = 'UPDATE') THEN
          INSERT INTO %I (%s, "operation", "stamp", "userid")
          SELECT NEW.*, 'U', now(), current_user;
          RETURN NEW;
        ELSIF (TG_OP = 'INSERT') THEN
          INSERT INTO %I (%s, "operation", "stamp", "userid")
          SELECT NEW.*, 'I', now(), current_user;
          RETURN NEW;
        END IF;
        RETURN NULL;
      END;
      $trig$ LANGUAGE plpgsql;
    $f$, _t || '_audit_trigger',
         _t || '_audit', _cols,
         _t || '_audit', _cols,
         _t || '_audit', _cols);
  END LOOP;
END $$;

-- =============================================================================
-- 1. Insert NPC Locations (7 new Calypso NPCs)
-- =============================================================================
-- Using DO block with upsert pattern: UPDATE first, INSERT if no row returned.

DO $$
DECLARE
  _alice_id    INTEGER;
  _boris_id    INTEGER;
  _lauren_id   INTEGER;
  _hanna_id    INTEGER;
  _hans_id     INTEGER;
  _leia_id     INTEGER;
  _thorleif_id INTEGER;
BEGIN
  -- Alice Laurent
  UPDATE ONLY "Locations"
  SET "Longitude" = 63225, "Latitude" = 74453, "Altitude" = 131
  WHERE "Name" = 'Alice Laurent' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _alice_id;
  IF _alice_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Alice Laurent', 'Npc', 1, 63225, 74453, 131)
    RETURNING "Id" INTO _alice_id;
  END IF;

  -- Boris
  UPDATE ONLY "Locations"
  SET "Longitude" = 61955, "Latitude" = 76163, "Altitude" = 138
  WHERE "Name" = 'Boris' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _boris_id;
  IF _boris_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Boris', 'Npc', 1, 61955, 76163, 138)
    RETURNING "Id" INTO _boris_id;
  END IF;

  -- Lauren Ashford
  UPDATE ONLY "Locations"
  SET "Longitude" = 63344, "Latitude" = 87480, "Altitude" = 126
  WHERE "Name" = 'Lauren Ashford' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _lauren_id;
  IF _lauren_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Lauren Ashford', 'Npc', 1, 63344, 87480, 126)
    RETURNING "Id" INTO _lauren_id;
  END IF;

  -- Hanna Hendrix
  UPDATE ONLY "Locations"
  SET "Longitude" = 35469, "Latitude" = 60113, "Altitude" = 240
  WHERE "Name" = 'Hanna Hendrix' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _hanna_id;
  IF _hanna_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Hanna Hendrix', 'Npc', 1, 35469, 60113, 240)
    RETURNING "Id" INTO _hanna_id;
  END IF;

  -- Hans Kaufman
  UPDATE ONLY "Locations"
  SET "Longitude" = 37054, "Latitude" = 53560, "Altitude" = 179
  WHERE "Name" = 'Hans Kaufman' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _hans_id;
  IF _hans_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Hans Kaufman', 'Npc', 1, 37054, 53560, 179)
    RETURNING "Id" INTO _hans_id;
  END IF;

  -- Leia Cassidy
  UPDATE ONLY "Locations"
  SET "Longitude" = 80538, "Latitude" = 68314, "Altitude" = 160
  WHERE "Name" = 'Leia Cassidy' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _leia_id;
  IF _leia_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Leia Cassidy', 'Npc', 1, 80538, 68314, 160)
    RETURNING "Id" INTO _leia_id;
  END IF;

  -- Thorleif Schtoll
  UPDATE ONLY "Locations"
  SET "Longitude" = 80459, "Latitude" = 68299, "Altitude" = 163
  WHERE "Name" = 'Thorleif Schtoll' AND "PlanetId" = 1 AND "Type" = 'Npc'
  RETURNING "Id" INTO _thorleif_id;
  IF _thorleif_id IS NULL THEN
    INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")
    VALUES ('Thorleif Schtoll', 'Npc', 1, 80459, 68299, 163)
    RETURNING "Id" INTO _thorleif_id;
  END IF;

  -- Store location IDs in a temp table for use in subsequent statements
  CREATE TEMP TABLE _npc_locations (npc_name TEXT PRIMARY KEY, location_id INTEGER) ON COMMIT DROP;
  INSERT INTO _npc_locations VALUES
    ('Alice Laurent',    _alice_id),
    ('Boris',            _boris_id),
    ('Lauren Ashford',   _lauren_id),
    ('Hanna Hendrix',    _hanna_id),
    ('Hans Kaufman',     _hans_id),
    ('Leia Cassidy',     _leia_id),
    ('Thorleif Schtoll', _thorleif_id);
END $$;

-- =============================================================================
-- 2. Create Mission Chain
-- =============================================================================

INSERT INTO "MissionChains" ("Name", "PlanetId", "Type", "Description")
SELECT 'Calypso AI Dailies', 1, 'AI Daily', 'AI-driven daily missions from Calypso NPCs'
WHERE NOT EXISTS (
  SELECT 1 FROM ONLY "MissionChains" WHERE "Name" = 'Calypso AI Dailies'
);

-- =============================================================================
-- 3. Create Missions, Steps, Objectives, and Rewards
-- =============================================================================

DO $$
DECLARE
  _chain_id    INTEGER;
  _mission_id  INTEGER;
  _step_id     INTEGER;
  _loc_id      INTEGER;
  -- Calypso NPC reward items (JSONB)
  _calypso_reward_items JSONB;
  -- Mork NPC reward items (JSONB)
  _mork_reward_items JSONB;
BEGIN
  -- Get chain ID
  SELECT "Id" INTO _chain_id FROM ONLY "MissionChains" WHERE "Name" = 'Calypso AI Dailies';

  -- Build Calypso reward items array (always + sometimes + rare)
  _calypso_reward_items := '[
    {"itemId": 1002428, "itemName": "Universal Ammo", "pedValue": 50},
    {"itemId": 1000331, "itemName": "Blazar Fragment", "quantity": 1000},
    {"itemId": 1001546, "itemName": "Nova Fragment", "quantity": 1000},

    {"itemId": 10000019, "itemName": "AccuStim 5mg"},
    {"itemId": 10000020, "itemName": "AccuStim 10mg"},
    {"itemId": 10000021, "itemName": "AccuStim 15mg"},
    {"itemId": 10000024, "itemName": "DevaStim 5mg"},
    {"itemId": 10000025, "itemName": "DevaStim 10mg"},
    {"itemId": 10000026, "itemName": "DevaStim 15mg"},
    {"itemId": 10000030, "itemName": "HyperStim 5mg"},
    {"itemId": 10000031, "itemName": "HyperStim 10mg"},
    {"itemId": 10000032, "itemName": "HyperStim 15mg"},
    {"itemId": 10000038, "itemName": "MediStim 5mg"},
    {"itemId": 10000039, "itemName": "MediStim 10mg"},
    {"itemId": 10000040, "itemName": "MediStim 15mg"},
    {"itemId": 10000072, "itemName": "NutriStim 5mg"},
    {"itemId": 10000073, "itemName": "NutriStim 10mg"},
    {"itemId": 10000074, "itemName": "NutriStim 15mg"},

    {"itemId": 10000044, "itemName": "Neurobiotic Booster A1 1mg"},
    {"itemId": 10000045, "itemName": "Neurobiotic Booster A1 5mg"},
    {"itemId": 10000059, "itemName": "Neurobiotic Booster A1 10mg"},
    {"itemId": 10000046, "itemName": "Neurobiotic Booster A2 1mg"},
    {"itemId": 10000047, "itemName": "Neurobiotic Booster A2 5mg"},
    {"itemId": 10000048, "itemName": "Neurobiotic Booster A3 1mg"},
    {"itemId": 10000049, "itemName": "Neurobiotic Booster A3 5mg"},
    {"itemId": 10000050, "itemName": "Neurobiotic Booster A4 1mg"},
    {"itemId": 10000060, "itemName": "Neurobiotic Booster A4 10mg"},
    {"itemId": 10000051, "itemName": "Neurobiotic Booster A5 1mg"},
    {"itemId": 10000052, "itemName": "Neurobiotic Booster A5 5mg"},
    {"itemId": 10000053, "itemName": "Neurobiotic Booster A6 1mg"},
    {"itemId": 10000054, "itemName": "Neurobiotic Booster A7 1mg"},
    {"itemId": 10000055, "itemName": "Neurobiotic Booster A8 1mg"},
    {"itemId": 10000056, "itemName": "Neurobiotic Booster A9 1mg"},
    {"itemId": 10000057, "itemName": "Neurobiotic Booster A10 1mg"},
    {"itemId": 10000058, "itemName": "Neurobiotic Booster A10 5mg"},
    {"itemId": 10000061, "itemName": "Neurobiotic Booster A10 10mg"},

    {"itemId": 8000674, "itemName": "Aeglic Ring (L)"},
    {"itemId": 8000675, "itemName": "Adjusted Aeglic Ring"},
    {"itemId": 8000676, "itemName": "Improved Aeglic Ring"},
    {"itemId": 8000677, "itemName": "Modified Aeglic Ring"},
    {"itemId": 8000678, "itemName": "Augmented Aeglic Ring"},
    {"itemId": 8000679, "itemName": "Perfected Aeglic Ring"},
    {"itemId": 8000680, "itemName": "Ares Ring (L)"},
    {"itemId": 8000681, "itemName": "Adjusted Ares Ring"},
    {"itemId": 8000682, "itemName": "Improved Ares Ring"},
    {"itemId": 8000683, "itemName": "Modified Ares Ring"},
    {"itemId": 8000684, "itemName": "Augmented Ares Ring"},
    {"itemId": 8000685, "itemName": "Perfected Ares Ring"},
    {"itemId": 8000686, "itemName": "Artemic Ring (L)"},
    {"itemId": 8000687, "itemName": "Adjusted Artemic Ring"},
    {"itemId": 8000688, "itemName": "Improved Artemic Ring"},
    {"itemId": 8000689, "itemName": "Modified Artemic Ring"},
    {"itemId": 8000690, "itemName": "Augmented Artemic Ring"},
    {"itemId": 8000691, "itemName": "Perfected Artemic Ring"},
    {"itemId": 8000692, "itemName": "Athenic Ring (L)"},
    {"itemId": 8000693, "itemName": "Adjusted Athenic Ring"},
    {"itemId": 8000694, "itemName": "Improved Athenic Ring"},
    {"itemId": 8000695, "itemName": "Modified Athenic Ring"},
    {"itemId": 8000696, "itemName": "Augmented Athenic Ring"},
    {"itemId": 8000697, "itemName": "Perfected Athenic Ring"},
    {"itemId": 8000698, "itemName": "Hermetic Ring (L)"},
    {"itemId": 8000699, "itemName": "Adjusted Hermetic Ring"},
    {"itemId": 8000700, "itemName": "Improved Hermetic Ring"},
    {"itemId": 8000701, "itemName": "Modified Hermetic Ring"},
    {"itemId": 8000702, "itemName": "Augmented Hermetic Ring"},
    {"itemId": 8000703, "itemName": "Perfected Hermetic Ring"}
  ]'::jsonb;

  -- Mork reward: just 1x Mutant Coinage
  _mork_reward_items := '[{"itemId": 1003201, "itemName": "Mutant Coinage", "quantity": 1}]'::jsonb;

  -- =========================================================================
  -- 3a. Calypso NPC Missions (AIKillCycle)
  -- =========================================================================

  -- Alice Laurent (empty mob pool)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Alice Laurent';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Alice Laurent (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": []}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Boris (empty mob pool)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Boris';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Boris (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": []}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Lauren Ashford (empty mob pool)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Lauren Ashford';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Lauren Ashford (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": []}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Hanna Hendrix (empty mob pool)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Hanna Hendrix';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Hanna Hendrix (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": []}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Hans Kaufman (Daspletor=29, Globster=55, Cornoanterion=23, Leviathan=73, Furor=53)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Hans Kaufman';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Hans Kaufman (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": [29, 55, 23, 73, 53]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Leia Cassidy (Primordial Longu=99)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Leia Cassidy';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Leia Cassidy (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": [99]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- Thorleif Schtoll (Primordial Longu=99)
  SELECT location_id INTO _loc_id FROM _npc_locations WHERE npc_name = 'Thorleif Schtoll';
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Thorleif Schtoll (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', _loc_id, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": [99]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _calypso_reward_items);

  -- =========================================================================
  -- 3b. Mork NPC Missions (existing locations)
  -- =========================================================================

  -- Borg Mork (AIKillCycle - Umbranoid Worker=303, Warrior=304, Faucervix=44, Mourner=87, Cornundos=25)
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Borg Mork (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', 5372, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": [303, 304, 44, 87, 25]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _mork_reward_items);

  -- Synt Mork (AIKillCycle - same pool as Borg Mork)
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Synt Mork (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', 5373, 'Hunting')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hunt Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIKillCycle', '{"pedToCycle": 50, "mobSpecies": [303, 304, 44, 87, 25]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _mork_reward_items);

  -- Lagg Mork (AIHandIn - Umbranoid "Medicine"=1003188, War Trophy=1003189, Dice=1003186)
  INSERT INTO "Missions" ("Name", "PlanetId", "MissionChainId", "Type", "CooldownDuration", "CooldownStartsOn", "StartLocationId", "Category")
  VALUES ('Lagg Mork (AI Daily)', 1, _chain_id, 'Recurring', '20 hours'::interval, 'Accept', 5374, 'HandIn')
  RETURNING "Id" INTO _mission_id;

  INSERT INTO "MissionSteps" ("MissionId", "Index", "Title")
  VALUES (_mission_id, 0, 'Hand In Assignment')
  RETURNING "Id" INTO _step_id;

  INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
  VALUES (_step_id, 'AIHandIn', '{"items": [{"itemId": 1003188, "minQuantity": 10, "maxQuantity": 100}, {"itemId": 1003189, "minQuantity": 50, "maxQuantity": 500}, {"itemId": 1003186, "minQuantity": 50, "maxQuantity": 500}]}'::jsonb);

  INSERT INTO "MissionRewards" ("MissionId", "Items")
  VALUES (_mission_id, _mork_reward_items);

END $$;

COMMIT;
