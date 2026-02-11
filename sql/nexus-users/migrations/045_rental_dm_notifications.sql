CREATE TABLE rental_dm_notifications (
  id              SERIAL PRIMARY KEY,
  owner_id        BIGINT NOT NULL REFERENCES users(id),
  offer_id        INTEGER NOT NULL,
  offer_title     TEXT NOT NULL,
  requester_name  TEXT NOT NULL,
  start_date      DATE NOT NULL,
  end_date        DATE NOT NULL,
  total_days      INTEGER NOT NULL,
  total_price     NUMERIC(10,2) NOT NULL,
  deposit         NUMERIC(10,2) NOT NULL DEFAULT 0,
  sent            BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rental_dm_notifications_pending ON rental_dm_notifications(sent) WHERE sent = false;

GRANT SELECT, INSERT, UPDATE ON rental_dm_notifications TO "nexus-users";
GRANT USAGE, SELECT, UPDATE ON SEQUENCE rental_dm_notifications_id_seq TO "nexus-users";

GRANT SELECT, UPDATE ON rental_dm_notifications TO "nexus-bot";
