-- Route analytics: page view tracking, rollup tables, and bot pattern management.
-- Individual route_visits rows are pruned after 30 days; rollup tables are permanent.

BEGIN;

-- Raw per-request log (30-day retention, pruned by background job)
CREATE TABLE route_visits (
  id bigserial PRIMARY KEY,
  visited_at timestamptz NOT NULL DEFAULT now(),
  ip_address inet NOT NULL,
  country_code char(2),
  user_agent text,
  route_category text NOT NULL,
  route_pattern text NOT NULL,
  route_path text NOT NULL,
  method text NOT NULL DEFAULT 'GET',
  status_code smallint,
  referrer text,
  is_bot boolean NOT NULL DEFAULT false,
  is_api boolean NOT NULL DEFAULT false,
  oauth_client_id text,
  rate_limited boolean NOT NULL DEFAULT false,
  response_time_ms integer
);

CREATE INDEX idx_route_visits_visited_at ON route_visits (visited_at);
CREATE INDEX idx_route_visits_category ON route_visits (route_category, visited_at);
CREATE INDEX idx_route_visits_bot ON route_visits (is_bot, visited_at) WHERE is_bot = true;
CREATE INDEX idx_route_visits_rate_limited ON route_visits (rate_limited, visited_at) WHERE rate_limited = true;
CREATE INDEX idx_route_visits_oauth ON route_visits (oauth_client_id, visited_at) WHERE oauth_client_id IS NOT NULL;
CREATE INDEX idx_route_visits_live ON route_visits (visited_at DESC) WHERE is_bot = false AND is_api = false;

-- Aggregated route stats (permanent)
CREATE TABLE route_analytics_rollup (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  route_category text NOT NULL,
  route_pattern text NOT NULL,
  request_count integer NOT NULL DEFAULT 0,
  unique_ips integer NOT NULL DEFAULT 0,
  bot_count integer NOT NULL DEFAULT 0,
  rate_limited_count integer NOT NULL DEFAULT 0,
  error_count integer NOT NULL DEFAULT 0,
  avg_response_ms integer,
  PRIMARY KEY (granularity, period_start, route_category, route_pattern)
);

CREATE INDEX idx_route_rollup_period ON route_analytics_rollup (granularity, period_start);

-- Country breakdown (permanent)
CREATE TABLE route_analytics_geo_rollup (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  country_code char(2) NOT NULL,
  request_count integer NOT NULL DEFAULT 0,
  unique_ips integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, country_code)
);

-- OAuth client usage (permanent)
CREATE TABLE route_analytics_oauth_rollup (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  oauth_client_id text NOT NULL,
  route_pattern text NOT NULL,
  request_count integer NOT NULL DEFAULT 0,
  rate_limited_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, oauth_client_id, route_pattern)
);

-- External referrer stats (permanent)
CREATE TABLE route_analytics_referrer_rollup (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  referrer_domain text NOT NULL,
  request_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, referrer_domain)
);

-- Configurable bot/crawler user-agent patterns
CREATE TABLE bot_patterns (
  id serial PRIMARY KEY,
  pattern text NOT NULL UNIQUE,
  description text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed common bot/crawler/AI agent patterns
INSERT INTO bot_patterns (pattern, description) VALUES
  ('Googlebot', 'Google Search'),
  ('bingbot', 'Microsoft Bing'),
  ('Baiduspider', 'Baidu'),
  ('YandexBot', 'Yandex'),
  ('DuckDuckBot', 'DuckDuckGo'),
  ('Slurp', 'Yahoo'),
  ('facebookexternalhit', 'Facebook crawler'),
  ('Twitterbot', 'Twitter/X crawler'),
  ('LinkedInBot', 'LinkedIn'),
  ('Discordbot', 'Discord link preview'),
  ('WhatsApp', 'WhatsApp preview'),
  ('TelegramBot', 'Telegram preview'),
  ('Applebot', 'Apple'),
  ('SemrushBot', 'Semrush SEO'),
  ('AhrefsBot', 'Ahrefs SEO'),
  ('MJ12bot', 'Majestic SEO'),
  ('DotBot', 'Moz/DotBot'),
  ('PetalBot', 'Huawei Petal'),
  ('GPTBot', 'OpenAI GPTBot'),
  ('ClaudeBot', 'Anthropic Claude'),
  ('Claude-Web', 'Anthropic Claude Web'),
  ('CCBot', 'Common Crawl'),
  ('ChatGPT-User', 'ChatGPT browsing'),
  ('PerplexityBot', 'Perplexity AI'),
  ('Bytespider', 'ByteDance/TikTok'),
  ('Amazonbot', 'Amazon'),
  ('HeadlessChrome', 'Headless Chrome (scraper)'),
  ('PhantomJS', 'PhantomJS'),
  ('Scrapy', 'Scrapy framework'),
  ('python-requests', 'Python requests'),
  ('Go-http-client', 'Go HTTP client'),
  ('axios/', 'Axios HTTP client'),
  ('curl/', 'cURL'),
  ('wget/', 'wget');

-- Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON route_visits TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE route_visits_id_seq TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON route_analytics_rollup TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON route_analytics_geo_rollup TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON route_analytics_oauth_rollup TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON route_analytics_referrer_rollup TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON bot_patterns TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE bot_patterns_id_seq TO nexus_users;

COMMIT;
