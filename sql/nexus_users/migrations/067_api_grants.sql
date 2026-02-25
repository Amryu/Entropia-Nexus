-- =============================================
-- Migration 067: Granular API Grants
-- =============================================
-- Adds read/write grants for API endpoint groups,
-- assigns them to the 'user' role, and updates
-- OAuth scope grant_keys.
-- =============================================

-- Insert new grants
INSERT INTO grants (key, description) VALUES
  ('inventory.read',    'Read personal inventory data'),
  ('inventory.manage',  'Import, modify, and delete personal inventory'),
  ('loadouts.read',     'Read loadout data'),
  ('loadouts.manage',   'Create, edit, and delete loadouts'),
  ('itemsets.read',     'Read item set data'),
  ('itemsets.manage',   'Create, edit, and delete item sets'),
  ('skills.read',       'Read skill data'),
  ('skills.manage',     'Import and manage skill data'),
  ('exchange.read',     'Read exchange order data'),
  ('exchange.manage',   'Create, edit, and close exchange orders'),
  ('auction.read',      'Read auction and bid data'),
  ('auction.manage',    'Create auctions, place bids, and settle'),
  ('rental.manage',     'Create, edit, and delete rental offers'),
  ('services.manage',   'Create and manage service listings'),
  ('events.submit',     'Submit community events')
ON CONFLICT (key) DO NOTHING;

-- Add all new grants to the 'user' role
INSERT INTO role_grants (role_id, grant_id, granted)
SELECT r.id, g.id, true
FROM roles r
CROSS JOIN grants g
WHERE r.name = 'user'
  AND g.key IN (
    'inventory.read', 'inventory.manage',
    'loadouts.read', 'loadouts.manage',
    'itemsets.read', 'itemsets.manage',
    'skills.read', 'skills.manage',
    'exchange.read', 'exchange.manage',
    'auction.read', 'auction.manage',
    'rental.manage', 'services.manage', 'events.submit'
  )
ON CONFLICT DO NOTHING;

-- =============================================
-- Update OAuth scope grant_keys (requires 066_oauth.sql)
-- =============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'oauth_scopes') THEN
    -- Read scopes
    UPDATE oauth_scopes SET grant_keys = '{inventory.read}'  WHERE key = 'inventory:read';
    UPDATE oauth_scopes SET grant_keys = '{loadouts.read}'   WHERE key = 'loadouts:read';
    UPDATE oauth_scopes SET grant_keys = '{itemsets.read}'    WHERE key = 'itemsets:read';
    UPDATE oauth_scopes SET grant_keys = '{skills.read}'     WHERE key = 'skills:read';
    UPDATE oauth_scopes SET grant_keys = '{exchange.read}'   WHERE key = 'exchange:read';
    UPDATE oauth_scopes SET grant_keys = '{auction.read}'    WHERE key = 'auction:read';
    -- Write scopes
    UPDATE oauth_scopes SET grant_keys = '{inventory.manage}' WHERE key = 'inventory:write';
    UPDATE oauth_scopes SET grant_keys = '{loadouts.manage}'  WHERE key = 'loadouts:write';
    UPDATE oauth_scopes SET grant_keys = '{itemsets.manage}'  WHERE key = 'itemsets:write';
    UPDATE oauth_scopes SET grant_keys = '{skills.manage}'    WHERE key = 'skills:write';
    UPDATE oauth_scopes SET grant_keys = '{exchange.manage}'  WHERE key = 'exchange:write';
    UPDATE oauth_scopes SET grant_keys = '{auction.manage}'   WHERE key = 'auction:write';
    UPDATE oauth_scopes SET grant_keys = '{rental.manage}'    WHERE key = 'rental:write';
    UPDATE oauth_scopes SET grant_keys = '{services.manage}'  WHERE key = 'services:write';
  END IF;
END $$;
