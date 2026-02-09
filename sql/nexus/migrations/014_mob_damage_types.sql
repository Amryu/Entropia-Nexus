-- ============================================================================
-- Migration 014: Mob Damage Types and Descriptions
-- ============================================================================
-- This migration adds/fixes mob damage type distributions in the MobAttacks
-- table and adds descriptions for mobs where only damage types (no percentages)
-- are known.
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Cleanup broken data
-- ============================================================================

-- Mulmun Ascended Overlord: Delete duplicate rows violating PK
DELETE FROM ONLY "MobAttacks"
WHERE "MaturityId" IN (
  SELECT mm."Id"
  FROM ONLY "MobMaturities" mm
  JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
  WHERE m."Name" = 'Mulmun'
    AND mm."Name" = 'Ascended Overlord'
    AND m."PlanetId" = 1
);

-- Insert correct data for Mulmun Ascended Overlord
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mulmun'
  AND mm."Name" = 'Ascended Overlord'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Secondary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mulmun'
  AND mm."Name" = 'Ascended Overlord'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Oratan Prospector "Thug": Fix wrong damage types
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, NULL, 33, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Oratan Prospector'
  AND mm."Name" = 'Thug'
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 2: CONFIRMED mobs (exact percentages known)
-- ============================================================================

-- Shogghols (DSEC9): Impact=50, Cut=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 50, NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Shogghols'
  AND m."PlanetId" = 8
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Tegunestene (DSEC9): Impact=25, Penetration=35, Burn=40
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 25, NULL, NULL, 35, NULL, NULL, 40, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Tegunestene'
  AND m."PlanetId" = 8
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Shoggoth (Monria): Impact=50, Cut=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 50, NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Shoggoth'
  AND m."PlanetId" = 3
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Gallard (Arkadia): Stab=33, Cut=33, Impact=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Gallard'
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Oratan Prospector (Arkadia): Stab=33, Impact=33, Penetration=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, NULL, 33, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Oratan Prospector'
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Mutated Kamaldon (Arkadia): Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mutated Kamaldon'
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Prototype Droka (Calypso): Penetration=25, Burn=75
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, 25, NULL, NULL, 75, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Prototype Droka'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Jeef Zajer Host (Toulan): Penetration=40, Cut=30, Stab=30
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 30, 30, 40, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Jeef Zajer Host'
  AND m."PlanetId" = 5
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Storm Drake (Next Island): Electric=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Storm Drake'
  AND m."PlanetId" = 6
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Worn Spider Bomber (Setesh): Electric=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Worn Spider Bomber'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Thawr (Toulan) - Primary: Impact=60, Penetration=20, Electric=20
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 60, NULL, NULL, 20, NULL, NULL, NULL, NULL, 20, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Thawr'
  AND m."PlanetId" = 5
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Thawr (Toulan) - Secondary: Impact=80, Penetration=20
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Secondary', 80, NULL, NULL, 20, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Thawr'
  AND m."PlanetId" = 5
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 3: CONFIRMED instance mobs (Arkadia)
-- ============================================================================

-- Arkadia instance mobs with maturity-specific damage types
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary',
  CASE
    WHEN mm."Name" LIKE 'Dehera%' THEN 40
    WHEN mm."Name" LIKE 'Magurg Female%' THEN 33
    WHEN mm."Name" LIKE 'Rakta%' THEN 40
    WHEN mm."Name" LIKE 'Ubo%' THEN NULL
    WHEN mm."Name" LIKE 'Yarrijak%' THEN 33
    WHEN mm."Name" = 'Aakas Defender' THEN 20
    WHEN mm."Name" = 'Aakas Warden' THEN 20
    ELSE NULL
  END, -- Impact
  CASE
    WHEN mm."Name" LIKE 'Dehera%' THEN 10
    WHEN mm."Name" LIKE 'Magurg Female%' THEN 33
    WHEN mm."Name" LIKE 'Rakta%' THEN NULL
    WHEN mm."Name" LIKE 'Ubo%' THEN NULL
    WHEN mm."Name" LIKE 'Yarrijak%' THEN 33
    WHEN mm."Name" = 'Aakas Defender' THEN 10
    WHEN mm."Name" = 'Aakas Warden' THEN 10
    ELSE NULL
  END, -- Stab
  CASE
    WHEN mm."Name" LIKE 'Dehera%' THEN 10
    WHEN mm."Name" LIKE 'Magurg Female%' THEN 33
    WHEN mm."Name" LIKE 'Rakta%' THEN 40
    WHEN mm."Name" LIKE 'Ubo%' THEN NULL
    WHEN mm."Name" LIKE 'Yarrijak%' THEN 33
    WHEN mm."Name" = 'Aakas Defender' THEN 30
    WHEN mm."Name" = 'Aakas Warden' THEN 30
    ELSE NULL
  END, -- Cut
  NULL, -- Penetration
  NULL, -- Shrapnel
  NULL, -- Acid
  CASE
    WHEN mm."Name" LIKE 'Dehera%' THEN 40
    WHEN mm."Name" LIKE 'Magurg Female%' THEN NULL
    WHEN mm."Name" LIKE 'Rakta%' THEN 20
    WHEN mm."Name" LIKE 'Ubo%' THEN 100
    WHEN mm."Name" LIKE 'Yarrijak%' THEN NULL
    WHEN mm."Name" = 'Aakas Defender' THEN 40
    WHEN mm."Name" = 'Aakas Warden' THEN 40
    ELSE NULL
  END, -- Burn
  NULL, -- Cold
  NULL, -- Electric
  false -- IsAoE
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" IN ('Aakas 01', 'Aakas 02', 'Aakas 03', 'Sal''diresh''s Vault 1', 'Sal''diresh''s Vault 2', 'Sal''diresh''s Vault 3', 'Sal''diresh''s Vault 4', 'Sal''diresh''s Vault 5')
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 4: CONFIRMED instance mobs (Toulan)
-- ============================================================================

-- Toulan instance mobs with maturity-specific damage types
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary',
  CASE
    WHEN mm."Name" LIKE 'TabTab%' THEN NULL
    WHEN mm."Name" LIKE 'Qaffaz%' THEN 50
    WHEN mm."Name" LIKE 'Mokhat%' THEN 80
    WHEN mm."Name" LIKE 'Khaffash%' THEN 33
    WHEN mm."Name" LIKE 'Bahri%' THEN NULL
    WHEN mm."Name" LIKE 'Dahhar%' THEN NULL
    WHEN mm."Name" LIKE 'Jeef%' THEN NULL
    ELSE NULL
  END, -- Impact
  CASE
    WHEN mm."Name" LIKE 'TabTab%' THEN NULL
    WHEN mm."Name" LIKE 'Qaffaz%' THEN 10
    WHEN mm."Name" LIKE 'Mokhat%' THEN 10
    WHEN mm."Name" LIKE 'Khaffash%' THEN NULL
    WHEN mm."Name" LIKE 'Bahri%' THEN 50
    WHEN mm."Name" LIKE 'Dahhar%' THEN 10
    WHEN mm."Name" LIKE 'Jeef%' THEN 30
    ELSE NULL
  END, -- Stab
  CASE
    WHEN mm."Name" LIKE 'TabTab%' THEN 75
    WHEN mm."Name" LIKE 'Qaffaz%' THEN 40
    WHEN mm."Name" LIKE 'Mokhat%' THEN 10
    WHEN mm."Name" LIKE 'Khaffash%' THEN 33
    WHEN mm."Name" LIKE 'Bahri%' THEN 50
    WHEN mm."Name" LIKE 'Dahhar%' THEN NULL
    WHEN mm."Name" LIKE 'Jeef%' THEN 30
    ELSE NULL
  END, -- Cut
  CASE
    WHEN mm."Name" LIKE 'TabTab%' THEN 25
    WHEN mm."Name" LIKE 'Qaffaz%' THEN NULL
    WHEN mm."Name" LIKE 'Mokhat%' THEN NULL
    WHEN mm."Name" LIKE 'Khaffash%' THEN 33
    WHEN mm."Name" LIKE 'Bahri%' THEN NULL
    WHEN mm."Name" LIKE 'Dahhar%' THEN 90
    WHEN mm."Name" LIKE 'Jeef%' THEN 40
    ELSE NULL
  END, -- Penetration
  NULL, -- Shrapnel
  NULL, -- Acid
  NULL, -- Burn
  NULL, -- Cold
  NULL, -- Electric
  false -- IsAoE
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" IN ('CUHOF Beginner', 'CUHOF 01', 'CUHOF 02', 'CUHOF 03', 'CUHOF 04', 'Baydar', 'Qaydar', 'Shamsdar')
  AND m."PlanetId" = 5
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 5: INFERRED mobs (based on base mob data)
-- ============================================================================

-- Calypso mobs (PlanetId=1)

-- Defense Eviscerator: Stab=50, Electric=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, 50, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Defense Eviscerator'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Defense Eviscerator Elite: Stab=50, Electric=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, 50, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Defense Eviscerator Elite'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Highland Allophyl: Impact=33, Electric=67
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 67, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Highland Allophyl'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Highland Mourner: Impact=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Highland Mourner'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Swampland Allophyl: Impact=33, Electric=67
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 67, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Swampland Allophyl'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Mayhem Mulmun Ascended Alpha: Impact=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mayhem Mulmun Ascended Alpha'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Mayhem Mulmun Ascended Elite: Impact=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mayhem Mulmun Ascended Elite'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Mayhem Mulmun Ascended Warrior: Impact=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Mayhem Mulmun Ascended Warrior'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Merry Annihilation Hispidus: Impact=50, Cut=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 50, NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Merry Annihilation Hispidus'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Merry Hispidus: Impact=50, Cut=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 50, NULL, 50, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Merry Hispidus'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Merry Hogglo: Impact=47, Stab=35, Cut=18
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 47, 35, 18, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Merry Hogglo'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Proteron Divine: Impact=25, Stab=25, Acid=50
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 25, 25, NULL, NULL, NULL, 50, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Proteron Divine'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Prototype Defender: Penetration=40, Burn=60
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, 40, NULL, NULL, 60, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Prototype Defender'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Pygmy Chomper: Impact=70, Cold=30
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 70, NULL, NULL, NULL, NULL, NULL, NULL, 30, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Pygmy Chomper'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Spina Broodmother: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Spina Broodmother'
  AND m."PlanetId" = 1
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Next Island mobs (PlanetId=6)

-- Adaptable Brown Papoo: Stab=20, Cut=60, Penetration=20
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 20, 60, 20, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Adaptable Brown Papoo'
  AND m."PlanetId" = 6
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Great White Shark: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Great White Shark'
  AND m."PlanetId" = 6
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Setesh mobs (PlanetId=20)

-- Damaged Defender: Penetration=40, Burn=60
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, 40, NULL, NULL, 60, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Damaged Defender'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Estophyl: Impact=75, Electric=25
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 75, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 25, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Estophyl'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Frescoquda: Impact=40, Acid=60
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 40, NULL, NULL, NULL, NULL, 60, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Frescoquda'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Prancer: Stab=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Prancer'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Pupugi: Stab=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Pupugi'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Sabakuma: Stab=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 100, NULL, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Sabakuma'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Spina Worker: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Spina Worker'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Seteshian Tezlapod: Electric=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Seteshian Tezlapod'
  AND m."PlanetId" = 20
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- HELL mobs (PlanetId=18) - All Legionaires: Burn=65, Penetration=27, Impact=8

-- Asmodai's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Asmodai''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Astaroth's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Astaroth''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Baal's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Baal''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Beelzebub's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Beelzebub''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Belphegor's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Belphegor''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Berith's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Berith''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Lucifer's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Lucifer''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Satan's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Satan''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Thammuz's Legionaire
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 8, NULL, NULL, 27, NULL, NULL, 65, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Thammuz''s Legionaire'
  AND m."PlanetId" = 18
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Secret Island mobs (PlanetId=14)

-- Brown Papoo: Stab=20, Cut=60, Penetration=20
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 20, 60, 20, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Brown Papoo'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Death Drake: Acid=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, 100, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Death Drake'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Great White Shark: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Great White Shark'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Island Shark: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Island Shark'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Petit Brown Papoo: Stab=20, Cut=60, Penetration=20
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, 20, 60, 20, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Petit Brown Papoo'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Petit Red Papoo: Impact=80, Stab=10, Cut=10
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 80, 10, 10, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Petit Red Papoo'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Red Papoo: Impact=80, Stab=10, Cut=10
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 80, 10, 10, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Red Papoo'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Shark: Impact=33, Stab=33, Cut=33
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 33, 33, 33, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Shark'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Snow Drake: Cold=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Snow Drake'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Storm Drake: Electric=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Storm Drake'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Vulcan Drake: Burn=100
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', NULL, NULL, NULL, NULL, NULL, NULL, 100, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Vulcan Drake'
  AND m."PlanetId" = 14
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 6: INFERRED Arkadia instance mob (IFN) and Magurg Patriarch
-- ============================================================================

-- IFN (Arkadia): Impact=30, Penetration=31, Burn=39
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 30, NULL, NULL, 31, NULL, NULL, 39, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'IFN'
  AND m."PlanetId" = 2
  AND mm."Name" LIKE 'IFN%'
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- Magurg Patriarch (Arkadia): Stab=35, Cut=34, Impact=31
INSERT INTO "MobAttacks" ("MaturityId", "Name", "Impact", "Stab", "Cut", "Penetration", "Shrapnel", "Acid", "Burn", "Cold", "Electric", "IsAoE")
SELECT mm."Id", 'Primary', 31, 35, 34, NULL, NULL, NULL, NULL, NULL, NULL, false
FROM ONLY "MobMaturities" mm
JOIN ONLY "Mobs" m ON m."Id" = mm."MobId"
WHERE m."Name" = 'Magurg Patriarch'
  AND m."PlanetId" = 2
ON CONFLICT ("Name", "MaturityId") DO UPDATE SET
  "Impact" = EXCLUDED."Impact",
  "Stab" = EXCLUDED."Stab",
  "Cut" = EXCLUDED."Cut",
  "Penetration" = EXCLUDED."Penetration",
  "Shrapnel" = EXCLUDED."Shrapnel",
  "Acid" = EXCLUDED."Acid",
  "Burn" = EXCLUDED."Burn",
  "Cold" = EXCLUDED."Cold",
  "Electric" = EXCLUDED."Electric";

-- ============================================================================
-- SECTION 7: Description updates for PARTIAL mobs (types known, no %)
-- ============================================================================

-- Calypso mobs (PlanetId=1)

-- Vanguard: Burn, Impact
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Impact</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Vanguard'
  AND "PlanetId" = 1
  AND ("Description" IS NULL OR "Description" = '');

-- Arkadia Underground mobs (PlanetId=12)

-- Smuggler Mech: Burn, Impact, Penetration
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Impact</strong>, <strong>Penetration</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Smuggler Mech'
  AND "PlanetId" = 12
  AND ("Description" IS NULL OR "Description" = '');

-- Cyrene mobs (PlanetId=7)

-- Byg Byrd: Penetration, Impact
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Penetration</strong>, <strong>Impact</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Byg Byrd'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Divine Golem: Burn, Acid, Cold, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Acid</strong>, <strong>Cold</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Divine Golem'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Drill Bot 1001: Impact, Burn, Shrapnel
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Burn</strong>, <strong>Shrapnel</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Drill Bot 1001'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Drill Bot 251: Impact, Burn, Shrapnel
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Burn</strong>, <strong>Shrapnel</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Drill Bot 251'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Fenris: Impact, Penetration, Burn
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Penetration</strong>, <strong>Burn</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Fenris'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Golem: Burn, Acid, Cold, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Acid</strong>, <strong>Cold</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Golem'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Hackfin: Cut, Stab (low maturities), Cut, Impact (high maturities)
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Cut</strong>, <strong>Stab</strong> (low maturities); <strong>Cut</strong>, <strong>Impact</strong> (Provider and above). Exact percentages unknown.</p>'
WHERE "Name" = 'Hackfin'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Mecha Lupine: Impact, Cold, Electric, Acid (Gen 0-2), adds Stab (Gen 3+)
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Cold</strong>, <strong>Electric</strong>, <strong>Acid</strong> (Gen 0-2); adds <strong>Stab</strong> (Gen 3+). Exact percentages unknown.</p>'
WHERE "Name" = 'Mecha Lupine'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Merfolken Spearman: Cold
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Cold</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Merfolken Spearman'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Muckjaw: Penetration, Stab, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Penetration</strong>, <strong>Stab</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Muckjaw'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Pleak: Impact
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Pleak'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Rhino Beetle: Impact, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Rhino Beetle'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Skyshatter Drone: Burn, Impact
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Impact</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Skyshatter Drone'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Skyshatter Robot (Large): Burn, Impact
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Burn</strong>, <strong>Impact</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Skyshatter Robot (Large)'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Turrelion Crystal Pede: Electric, Cut, Stab
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Electric</strong>, <strong>Cut</strong>, <strong>Stab</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Turrelion Crystal Pede'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Turrelion Vlanwing: Cut, Stab
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Cut</strong>, <strong>Stab</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Turrelion Vlanwing'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Turrelion Zeladoth: Impact, Burn, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Burn</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Turrelion Zeladoth'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Undersea Folken: Cold, Cut
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Cold</strong>, <strong>Cut</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Undersea Folken'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Wiles: Impact, Penetration
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Penetration</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Wiles'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- Armored Whisker Fish: Impact, Penetration (or Cut)
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Impact</strong>, <strong>Penetration</strong> (or Cut). Exact percentages unknown.</p>'
WHERE "Name" = 'Armored Whisker Fish'
  AND "PlanetId" = 7
  AND ("Description" IS NULL OR "Description" = '');

-- DSEC9 mobs (PlanetId=8)

-- Caboria: Cold, Electric, Acid
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Cold</strong>, <strong>Electric</strong>, <strong>Acid</strong>. Exact percentages unknown. (NOTE: Different from Toulan Caboria)</p>'
WHERE "Name" = 'Caboria'
  AND "PlanetId" = 8
  AND ("Description" IS NULL OR "Description" = '');

-- DSEC FURY: Electric, Acid, Cold
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Electric</strong>, <strong>Acid</strong>, <strong>Cold</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'DSEC FURY'
  AND "PlanetId" = 8
  AND ("Description" IS NULL OR "Description" = '');

-- Lotus Invader: Electric, Cold, Penetration, Burn
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Electric</strong>, <strong>Cold</strong>, <strong>Penetration</strong>, <strong>Burn</strong>. Exact percentages unknown.</p>'
WHERE "Name" = 'Lotus Invader'
  AND "PlanetId" = 8
  AND ("Description" IS NULL OR "Description" = '');

-- Wahesh (DSEC9): Acid, Electric
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Acid</strong>, <strong>Electric</strong>. Exact percentages unknown. (NOTE: Different from Toulan Wahesh)</p>'
WHERE "Name" = 'Wahesh'
  AND "PlanetId" = 8
  AND ("Description" IS NULL OR "Description" = '');

-- Toulan mobs (PlanetId=5)

-- Wahesh: Electric, Impact, Burn, Cold (50% Electric + remaining split)
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Electric</strong> (50%), <strong>Impact</strong>, <strong>Burn</strong>, <strong>Cold</strong> (remaining 50% split). Exact percentages unknown.</p>'
WHERE "Name" = 'Wahesh'
  AND "PlanetId" = 5
  AND ("Description" IS NULL OR "Description" = '');

-- Evolved Wahesh: Electric, Impact, Burn, Cold (50% Electric + remaining split)
UPDATE ONLY "Mobs"
SET "Description" = '<p>Known damage types: <strong>Electric</strong> (50%), <strong>Impact</strong>, <strong>Burn</strong>, <strong>Cold</strong> (remaining 50% split). Exact percentages unknown.</p>'
WHERE "Name" = 'Evolved Wahesh'
  AND "PlanetId" = 5
  AND ("Description" IS NULL OR "Description" = '');

COMMIT;
