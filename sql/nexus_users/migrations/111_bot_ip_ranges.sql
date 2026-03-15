-- IP-range-based bot detection for known datacenter/cloud provider ranges.
-- Only ranges where traffic cannot be a regular consumer (no VPNs).

BEGIN;

CREATE TABLE bot_ip_ranges (
  id serial PRIMARY KEY,
  cidr cidr NOT NULL UNIQUE,
  description text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Tencent Cloud (AS132203, AS45090) — WeChat/QQ crawlers
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('43.128.0.0/10', 'Tencent Cloud (Asia)'),
  ('49.51.0.0/16', 'Tencent Cloud'),
  ('101.32.0.0/12', 'Tencent Cloud'),
  ('129.226.0.0/16', 'Tencent Cloud'),
  ('162.62.0.0/16', 'Tencent Cloud'),
  ('170.106.0.0/16', 'Tencent Cloud');

-- Alibaba Cloud (AS45102) — Chinese datacenter
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('47.74.0.0/15', 'Alibaba Cloud'),
  ('47.88.0.0/14', 'Alibaba Cloud'),
  ('47.254.0.0/16', 'Alibaba Cloud'),
  ('149.129.0.0/16', 'Alibaba Cloud'),
  ('161.117.0.0/16', 'Alibaba Cloud');

-- Baidu Cloud (AS38365)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('180.76.0.0/16', 'Baidu Cloud/Spider');

-- Yandex (AS13238)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('5.255.253.0/24', 'Yandex Bot'),
  ('77.88.55.0/24', 'Yandex Bot'),
  ('87.250.224.0/20', 'Yandex Bot/Cloud'),
  ('141.8.132.0/24', 'Yandex Bot'),
  ('178.154.128.0/17', 'Yandex Cloud');

-- SemrushBot (AS209110)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('185.191.171.0/24', 'SemrushBot');

-- AhrefsBot
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('51.222.253.0/24', 'AhrefsBot'),
  ('54.36.148.0/22', 'AhrefsBot');

-- Bytedance/TikTok (AS396986)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('16.162.0.0/16', 'ByteDance'),
  ('220.243.136.0/22', 'ByteDance/Bytespider');

-- Sogou Spider (Chinese search engine)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('106.120.173.0/24', 'Sogou Spider'),
  ('123.126.113.0/24', 'Sogou Spider');

-- MJ12bot / Majestic (AS60781)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('46.4.122.0/24', 'MJ12bot/Majestic');

-- DotBot / Moz
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('216.244.66.0/24', 'DotBot/Moz');

-- Petalsearch / Huawei (AS136907)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('114.119.128.0/18', 'PetalBot/Huawei'),
  ('159.138.0.0/16', 'Huawei Cloud');

-- Mail.ru Bot (AS47764)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('95.163.32.0/19', 'Mail.ru Cloud/Bot');

-- Naver (Korean search, AS23576)
INSERT INTO bot_ip_ranges (cidr, description) VALUES
  ('125.209.222.0/24', 'Naver Bot');

GRANT SELECT, INSERT, UPDATE, DELETE ON bot_ip_ranges TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE bot_ip_ranges_id_seq TO nexus_users;

COMMIT;
