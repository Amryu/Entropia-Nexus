-- ============================================================================
-- Migration 016: Update Enhancers View Naming Scheme
-- ============================================================================
-- Changes enhancer names from "Weapon Damage Enhancer 2" format
-- to "T2 Weapon Damage Enhancer" format.
-- Also renames enhancer blueprints to match:
-- "Weapon Damage Enhancer 2 Blueprint" -> "T2 Weapon Damage Enhancer Blueprint"
-- ============================================================================

-- Rename enhancer blueprints
UPDATE ONLY "Blueprints"
SET "Name" = regexp_replace("Name", '^(.+) Enhancer (\d+) Blueprint( \(L\))?$', 'T\2 \1 Enhancer Blueprint\3')
WHERE "Name" ~ '^.+ Enhancer \d+ Blueprint( \(L\))?$';

-- Update the Enhancers view
CREATE OR REPLACE VIEW public."Enhancers" AS
WITH RECURSIVE cnt(x) AS (
    SELECT 1
    UNION ALL
    SELECT cnt_1.x + 1
    FROM cnt cnt_1
    WHERE cnt_1.x < 10
)
SELECT "EnhancerType"."Id" * 10 + cnt.x - 10 AS "Id",
    'T' || cnt.x || ' ' || "EnhancerType"."Tool" || ' ' || "EnhancerType"."Name" || ' Enhancer' AS "Name",
    "EnhancerType"."Id" AS "TypeId",
    cnt.x AS "Socket",
    0.01 AS "Weight",
    "EnhancerType"."Value"
FROM ONLY "EnhancerType"
JOIN cnt ON true;
