BEGIN;

-- shop_managers table - bot needs to manage shop managers
GRANT SELECT, INSERT, DELETE ON shop_managers TO nexus_bot;

GRANT SELECT, INSERT, UPDATE, DELETE ON service_tickets TO nexus_bot;

COMMIT;
