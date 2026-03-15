-- Store per-period IP sets for accurate unique visitor counts across rollup granularities.
-- Each row stores the distinct IPs for that period as an array (~8 bytes per IPv4).
-- A day with 2000 unique visitors = ~16 KB. A year of daily data = ~6 MB.

BEGIN;

CREATE TABLE route_analytics_ip_sets (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  ip_set inet[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (granularity, period_start)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON route_analytics_ip_sets TO nexus_users;

COMMIT;
