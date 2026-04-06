-- error-log.js updates rows via UPDATE error_log SET error_message = ... after
-- the initial INSERT. Migration 112 granted SELECT/INSERT/DELETE only; the
-- UPDATE grant is needed for the two-phase logging flow.
GRANT UPDATE ON error_log TO nexus_users;
