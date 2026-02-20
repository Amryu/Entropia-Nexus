-- Migration 035: Change effect name convention from prefix to suffix
-- "Increased X" → "X Increased", "Decreased X" → "X Decreased", etc.

UPDATE ONLY "Effects"
SET "Name" = REGEXP_REPLACE("Name", '^(Increased|Decreased|Added|Reduced) (.+)$', '\2 \1')
WHERE "Name" ~ '^(Increased|Decreased|Added|Reduced) ';
