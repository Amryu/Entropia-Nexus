-- Add fishing/cooking professions and skills.
--
-- All fishing action skills (visible and hidden) live under the existing
-- "General" skill category - there is no dedicated Fishing category.
-- Fish processing (Gutting/Filleting) lives under "Information". Gear
-- and food crafting skills live under "Construction", matching how
-- Chemistry and the weaponry-tech skills are filed today.
--
-- Professions are split between "Resource Collecting" (fishers) and
-- "Manufacturing" (gear engineers, food crafters), matching existing
-- precedent (Miner, Prospector, etc. vs. Armor Maker, Chef, etc.).
--
-- INTENTIONALLY LEFT EMPTY:
--   * ProfessionSkills rows for hidden skills (association unknown)
--   * ProfessionSkills.Weight values (unknown; fill in later when
--     in-game contribution data is available)
--   * Secondary visible skills per profession (unknown)
--
-- Only the 1:1 main-skill link per profession is inserted (weight NULL),
-- so the wiki pages show the primary association without committing to
-- guessed numbers.
--
-- Explicit Ids are used so client/data/skill_reference.json stays in
-- sync. Sequences are bumped at the end.

-- ---------------------------------------------------------------------------
-- Skills (General category, visible) - fishing actions.
-- General category (Id 4).
-- ---------------------------------------------------------------------------

INSERT INTO "Skills" ("Id", "Name", "CategoryId", "Hidden") VALUES
  (177, 'Fishing',              4, 0),
  (178, 'Casting',              4, 0),
  (179, 'Angling',              4, 0),
  (180, 'Fly Fishing',          4, 0),
  (181, 'Deep Ocean Fishing',   4, 0),
  (182, 'Baitfishing',          4, 0);

-- ---------------------------------------------------------------------------
-- Skills (General category, hidden) - fishing sub-skills.
-- ---------------------------------------------------------------------------

INSERT INTO "Skills" ("Id", "Name", "CategoryId", "Hidden") VALUES
  (183, 'Water Reading',        4, 1),
  (184, 'Fisherman''s Sense',   4, 1),
  (185, 'Lure Mastery',         4, 1),
  (186, 'Angler Intuition',     4, 1),
  (187, 'Matching the Hatch',   4, 1),
  (188, 'False Casting',        4, 1),
  (189, 'Sea Eyes',             4, 1);

-- ---------------------------------------------------------------------------
-- Skills (Information category) - fish processing. Gutting is the visible
-- main skill for Fish Looter; Filleting is the matching hidden skill.
-- Information category (Id 9).
-- ---------------------------------------------------------------------------

INSERT INTO "Skills" ("Id", "Name", "CategoryId", "Hidden") VALUES
  (176, 'Gutting',              9, 0),
  (190, 'Filleting',            9, 1);

-- ---------------------------------------------------------------------------
-- Skills (Construction category, visible) - gear crafting + food crafting.
-- Construction category (Id 6).
-- ---------------------------------------------------------------------------

INSERT INTO "Skills" ("Id", "Name", "CategoryId", "Hidden") VALUES
  (191, 'Fishing Rod Technology',        6, 0),
  (192, 'Fishing Attachment Technology', 6, 0),
  (193, 'Cooking',                        6, 0),
  (194, 'Provisioning',                   6, 0),
  (195, 'Nutrition',                      6, 0),
  (196, 'Gastronomy',                     6, 0);

-- ---------------------------------------------------------------------------
-- Professions (Resource Collecting)
-- ---------------------------------------------------------------------------

INSERT INTO "Professions" ("Id", "Name", "CategoryId") VALUES
  (98,  'Cast Fisher',       3),
  (99,  'Baiter',            3),
  (100, 'Fly Fisher',        3),
  (101, 'Deep Ocean Fisher', 3),
  (102, 'Baitfisher',        3),
  (103, 'Fish Looter',       3);

-- ---------------------------------------------------------------------------
-- Professions (Manufacturing)
-- ---------------------------------------------------------------------------

INSERT INTO "Professions" ("Id", "Name", "CategoryId") VALUES
  (104, 'Fishing Gear Engineer',       4),
  (105, 'Fishing Attachment Engineer', 4),
  (106, 'Gastronomer',                 4),
  (107, 'Nutritionist',                4),
  (108, 'Provisioner',                 4);

-- ---------------------------------------------------------------------------
-- ProfessionSkills - primary visible skill only, Weight left NULL.
-- Hidden-skill associations and weights are intentionally omitted.
-- ---------------------------------------------------------------------------

INSERT INTO "ProfessionSkills" ("ProfessionId", "SkillId", "Weight") VALUES
  (98,  178, NULL),  -- Cast Fisher              -> Casting
  (99,  179, NULL),  -- Baiter                   -> Angling
  (100, 180, NULL),  -- Fly Fisher               -> Fly Fishing
  (101, 181, NULL),  -- Deep Ocean Fisher        -> Deep Ocean Fishing
  (102, 182, NULL),  -- Baitfisher               -> Baitfishing
  (103, 176, NULL),  -- Fish Looter              -> Gutting
  (104, 191, NULL),  -- Fishing Gear Engineer    -> Fishing Rod Technology
  (105, 192, NULL),  -- Fishing Attachment Eng.  -> Fishing Attachment Technology
  (106, 196, NULL),  -- Gastronomer              -> Gastronomy
  (107, 195, NULL),  -- Nutritionist             -> Nutrition
  (108, 194, NULL);  -- Provisioner              -> Provisioning

-- ---------------------------------------------------------------------------
-- Bump sequences past the explicit Ids we just inserted.
-- ---------------------------------------------------------------------------

SELECT setval('"Skills_Id_seq"',      196, true);
SELECT setval('"Professions_Id_seq"', 108, true);
