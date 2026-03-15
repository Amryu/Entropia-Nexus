-- Error log: keeps last 10 errors per route per status code.
-- Captures request headers, response body, and diagnostic info.

BEGIN;

CREATE TABLE error_log (
  id bigserial PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  route_pattern text NOT NULL,
  route_path text NOT NULL,
  method text NOT NULL,
  status_code smallint NOT NULL,
  ip_address inet,
  country_code char(2),
  user_agent text,
  request_headers jsonb,
  response_body text,
  error_message text,
  response_time_ms integer
);

CREATE INDEX idx_error_log_route_status ON error_log (route_pattern, status_code, created_at DESC);
CREATE INDEX idx_error_log_created ON error_log (created_at DESC);

GRANT SELECT, INSERT, DELETE ON error_log TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE error_log_id_seq TO nexus_users;

COMMIT;
