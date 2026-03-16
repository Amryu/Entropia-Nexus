-- Force full rebuild of mining ATH data.
-- Mining category is now split into 'mining' (regular) and 'space_mining' (asteroids).
-- The globals-cache.js ATH rebuild process will repopulate both categories on next cycle.
DELETE FROM globals_ath_leaderboard WHERE category = 'mining';
