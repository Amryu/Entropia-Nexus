-- 071: Ingestion allowlist — only approved OAuth applications may submit data.
-- Distribution (GET) endpoints remain open to all verified users.

CREATE TABLE ingestion_allowed_clients (
    id          SERIAL PRIMARY KEY,
    client_id   TEXT NOT NULL REFERENCES oauth_clients(id) UNIQUE,
    allowed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    allowed_by  BIGINT NOT NULL REFERENCES users(id),
    notes       TEXT
);

CREATE INDEX idx_ingestion_allowed_client ON ingestion_allowed_clients(client_id);

GRANT SELECT, INSERT, DELETE ON ingestion_allowed_clients TO nexus_users;
GRANT USAGE ON SEQUENCE ingestion_allowed_clients_id_seq TO nexus_users;
