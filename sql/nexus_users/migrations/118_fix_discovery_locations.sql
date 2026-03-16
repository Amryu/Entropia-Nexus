-- Fix 314 discovery globals that have location embedded in target_name.
-- Extract "Item discovered in {Location}" into the location column.

UPDATE ingested_globals
SET
  target_name = substring(target_name FROM '^(.+?)\. Item discovered in '),
  location = substring(target_name FROM '\. Item discovered in (.+)$')
WHERE global_type = 'discovery'
  AND target_name LIKE '%. Item discovered in %';
