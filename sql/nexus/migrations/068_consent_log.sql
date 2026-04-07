CREATE TABLE IF NOT EXISTS consent_log (
  id SERIAL PRIMARY KEY,
  ip_address INET NOT NULL,
  ads_consent TEXT NOT NULL CHECK (ads_consent IN ('granted', 'denied')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_consent_log_ip ON consent_log (ip_address);
CREATE INDEX idx_consent_log_created ON consent_log (created_at);
