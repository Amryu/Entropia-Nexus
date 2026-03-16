-- Track requests with suspicious (non-browser) headers
ALTER TABLE route_visits ADD COLUMN IF NOT EXISTS suspect_headers boolean NOT NULL DEFAULT false;

-- Track IPs that executed the JS analytics beacon (proves real browser)
CREATE TABLE IF NOT EXISTS beacon_hits (
  ip_address inet PRIMARY KEY,
  last_seen timestamptz NOT NULL DEFAULT now()
);
