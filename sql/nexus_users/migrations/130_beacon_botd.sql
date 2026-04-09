-- Store BotD (headless browser detection) results alongside beacon hits.
-- bot_detected: true = BotD flagged this IP as automated (Puppeteer, Playwright, etc.)
-- botd_type: the detection type string from BotD (e.g. 'notDetected', 'headlessChrome')
ALTER TABLE beacon_hits
  ADD COLUMN IF NOT EXISTS bot_detected boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS botd_type text;
