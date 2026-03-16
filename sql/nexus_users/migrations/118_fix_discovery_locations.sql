-- Fix discovery globals that have location embedded in target_name.
-- Extract "Item discovered in {Location}" into the location column.
-- Only update rows where the regex extraction succeeds (both parts non-null).

UPDATE ingested_globals
SET
  target_name = substring(target_name FROM '^(.+)\. Item discovered in .+$'),
  location = substring(target_name FROM '\. Item discovered in (.+)$')
WHERE global_type = 'discovery'
  AND target_name LIKE '%. Item discovered in %'
  AND substring(target_name FROM '^(.+)\. Item discovered in .+$') IS NOT NULL;
